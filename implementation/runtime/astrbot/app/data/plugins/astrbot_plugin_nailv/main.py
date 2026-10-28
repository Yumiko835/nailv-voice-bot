"""AstrBot hooks: existing persona/RAG, hidden delivery routing and local TTS."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import asyncio
import json
import re
import sys
import time
import os
import urllib.request
from pathlib import Path
import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Star, Context, register
from astrbot.api.message_components import At, Plain, Record

ROOT = Path(project_path(''))
sys.path.insert(0, str(ROOT / 'tools'))
import nailv_text_core as core
import nailv_cosy_performance as perf
import nailv_voice_intent as intent
import nailv_affect_context as affect

BOT, GROUP, OWNER = setting("bot_qq",""), setting("test_group",""), setting("owner_qq","")
VOICE_BASE = setting("voice_url","http://127.0.0.1:49856")
VOICE_ROOT = ROOT / 'voice/comparison/cosyvoice3-20261026/live-bridge/runs'
VOICE_LOCK = asyncio.Lock()


def allowed(event):
    if event.get_platform_name() != 'aiocqhttp' or str(event.get_self_id()) != BOT:
        return False
    group = str(event.get_group_id() or '')
    if group:
        return group == GROUP and any(isinstance(c, At) and str(c.qq) == BOT for c in event.get_messages())
    return str(event.get_sender_id()) == OWNER


def parse_response(raw):
    raw = raw.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw).removesuffix('```').strip()
    try:
        data = json.loads(raw)
    except ValueError:
        if raw.startswith(('{', '[')) or '"delivery"' in raw or '"used_fact_ids"' in raw:
            raise ValueError('Unparseable internal response')
        return perf.strip_markup(raw), {}, []
    if not isinstance(data, dict) or not isinstance(data.get('reply'), str) or not data['reply'].strip():
        raise ValueError('Missing reply')
    delivery = data.get('delivery') if isinstance(data.get('delivery'), dict) else {}
    delivery = {k:v for k,v in delivery.items() if k in ('tone','pace','intensity','nonverbal','emotion') and isinstance(v,str)}
    if 'emotion' in delivery:
        emotion = intent.normalize(delivery['emotion'],data['reply'])
        if emotion: delivery['emotion'] = emotion
        else: delivery.pop('emotion')
    ids = data.get('used_fact_ids', [])
    return perf.strip_markup(data['reply']).strip(), delivery, ids if isinstance(ids,list) else []


class RoutingClient:
    """Same selected model and route format, without the retired API budget cap."""
    def __init__(self):
        self.key=(os.environ.get('CHAT_API_KEY') or (ROOT.parent.parent/secret_path("CHAT_API_KEY_FILE")).read_text(encoding='utf-8-sig')).strip()
        if not self.key:raise RuntimeError('Missing chat API key')
    def call(self,messages,job,cache=False,selection=False):
        if not selection:raise ValueError('Routing client is only for context selection')
        body={'model':core.MODEL,'messages':messages,'temperature':.85,'max_tokens':1024,
              'thinking':{'type':'disabled'},'response_format':{'type':'json_object'}}
        request=urllib.request.Request(setting("chat_endpoint","https://api.deepseek.com/v1/chat/completions"),data=json.dumps(body,ensure_ascii=False).encode(),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=60) as response:data=json.load(response)
        choice=data['choices'][0]
        if choice.get('finish_reason')!='stop':raise ValueError('Incomplete context selection')
        raw=choice['message']['content'].strip()
        if raw.startswith('```'):raw=re.sub(r'^```(?:json)?\s*','',raw).removesuffix('```').strip()
        obj=json.loads(raw)
        if not isinstance(obj,dict) or not isinstance(obj.get('style_ids'),list) or not isinstance(obj.get('behavior_ids'),list):
            raise ValueError('Invalid context selection')
        return {'content':obj}

def prepare(question, history, semantic):
    client = RoutingClient()
    routing = core.choose_routing(question, history, client, 'astrbot-route-'+str(time.time_ns()), False)
    messages, context = core.messages_for(question, history, semantic=semantic, routing=routing,
                                         performance=False, voice_routing=True)
    return messages[0]['content'], context


@register('astrbot_plugin_nailv', 'local', '奶绿人设资料库与 D/N1 本地语音适配', '0.1.0')
class NailvBridge(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

    @filter.event_message_type(filter.EventMessageType.ALL, priority=10000)
    async def scope_gate(self, event: AstrMessageEvent):
        if not allowed(event):
            event.stop_event()

    @filter.on_llm_request(priority=10000)
    async def inject_character(self, event, req):
        if not allowed(event):
            event.stop_event(); return
        try:
            question = (req.prompt or event.get_message_str()).strip()
            if not 1 <= len(question) <= 2000:
                raise ValueError('Message length outside supported range')
            history = [dict(x) for x in req.contexts if isinstance(x,dict) and x.get('role') in ('user','assistant') and isinstance(x.get('content'),str)][-12:]
            system, ctx = await asyncio.to_thread(prepare, question, history, bool(self.config.get('semantic_retrieval',True)))
            # Preserve plugin tools, multimodal inputs, tool-result pairs and
            # conversation ownership. Only add the character's per-turn context.
            req.system_prompt = (req.system_prompt or '')+'\n\nNAILV_CONTEXT_V1\n'+system
            event.set_extra('nailv_question', question)
            event.set_extra('nailv_history', history)
            event.set_extra('nailv_context_ids', [x['id'] for x in ctx['facts']])
        except Exception as exc:
            logger.error('奶绿人设准备失败，已阻止无角色请求：%s', type(exc).__name__)
            event.stop_event()

    @filter.on_llm_response(priority=10000)
    async def unpack_character(self, event, resp):
        if not allowed(event) or resp is None or resp.role != 'assistant' or resp.tools_call_name:
            return
        try:
            text, delivery, ids = parse_response(resp.completion_text)
            question=event.get_extra('nailv_question','');history=event.get_extra('nailv_history',[])
            text,temporal_repair=affect.guard_reply(text,question,history,ids)
            if affect.pet_loss_context(text,question,history):
                delivery.update(emotion='serious',intensity='soft',nonverbal='none')
            if temporal_repair:
                ids=['fact-self-manager-loss']
                logger.info('奶绿宠物往事时间边界已校正，未延伸为当前状态。')
            resp.completion_text = text
            event.set_extra('nailv_clean_reply', text)
            event.set_extra('nailv_delivery', delivery)
            event.set_extra('nailv_used_ids', [x for x in ids if x in event.get_extra('nailv_context_ids',[])])
        except ValueError:
            resp.completion_text = '这句刚才没说清楚，你再问我一下。'
            logger.warning('奶绿内部回复格式异常，未展示内部字段。')

    @filter.after_message_sent()
    async def local_voice(self, event):
        text = event.get_extra('nailv_clean_reply')
        result = event.get_result()
        if not allowed(event) or not text or event.get_extra('nailv_voice_attempted') or not result or not result.is_llm_result():
            return
        if not self.config.get('voice_enabled',True): return
        event.set_extra('nailv_voice_attempted', True)
        try:
            async with VOICE_LOCK, aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=420)) as session:
                payload = {'text':text[:600], 'message':event.get_extra('nailv_question',''),
                           'history':event.get_extra('nailv_history',[]), 'delivery':event.get_extra('nailv_delivery',{}),
                           'evaluate':False}
                deadline = time.monotonic()+360
                while True:
                    async with session.post(VOICE_BASE+'/api/speak',json=payload,headers={'Origin':VOICE_BASE}) as response:
                        data = await response.json()
                        if response.status == 202: break
                        if response.status != 409 or time.monotonic()>deadline:
                            raise RuntimeError('Local voice service unavailable')
                    await asyncio.sleep(1)
                job_id = data['id']
                if not re.fullmatch('[a-f0-9]{32}',job_id):raise ValueError('Invalid job id')
                while time.monotonic()<deadline:
                    async with session.get(VOICE_BASE+'/api/job',params={'id':job_id}) as response:
                        job = await response.json()
                    if job.get('state') == 'done':
                        audio = (VOICE_ROOT/job_id/'speech.wav').resolve()
                        if not audio.is_relative_to(VOICE_ROOT.resolve()) or not audio.is_file():raise ValueError('Missing audio')
                        # Preserve the PCM master; bypass NapCat's unavailable
                        # WAV decoder with AstrBot's own Tencent SILK encoder.
                        from astrbot.core.utils.tencent_record_helper import wav_to_tencent_silk
                        encoded=audio.with_name('qq-voice.silk')
                        duration=await wav_to_tencent_silk(str(audio),str(encoded))
                        if duration<=.2 or not encoded.read_bytes().startswith(b'\x02#!SILK_V3'):
                            raise ValueError('Invalid Tencent SILK output')
                        logger.info('奶绿语音已编码：job=%s, %.2fs, %d bytes',job_id,duration,encoded.stat().st_size)
                        await event.send(MessageChain([Record.fromFileSystem(str(encoded))]))
                        logger.info('奶绿语音已发送：job=%s',job_id)
                        return
                    if job.get('state') == 'error':raise RuntimeError('Local synthesis failed')
                    await asyncio.sleep(.5)
                raise TimeoutError('Local voice timeout')
        except Exception as exc:
            # Text is already delivered. Failed synthesis never blocks chat.
            detail=getattr(exc,'result',{})
            safe={'type':type(exc).__name__,'retcode':detail.get('retcode'),
                  'message':str(detail.get('message',''))[:240]} if isinstance(detail,dict) else {'type':type(exc).__name__}
            logger.warning('奶绿语音未发送，文字已保留：%s',safe)
