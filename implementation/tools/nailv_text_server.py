"""Loopback-only text pilot. Private free chat is transient; only explicit ratings are saved."""
from __future__ import annotations

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import argparse,hashlib,json,os,re,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import nailv_text_core as core
import nailv_voice_preview as voice_preview
import nailv_voice_upgrade as voice_upgrade
import nailv_voice_round3 as voice_round3
import nailv_voice_trial as voice_trial
import nailv_voice_cadence as voice_cadence
import nailv_voice_materials as voice_materials
import nailv_voice_backends as voice_backends
import nailv_voice_v5 as voice_v5
import nailv_hybrid_voice as hybrid_voice
import nailv_newsource_voice as newsource_voice
import nailv_proplus_voice as proplus_voice

PAGE=r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新奶绿 · 文字试聊</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f7f5;color:#243d34;font:15px/1.7 "Microsoft YaHei",system-ui,sans-serif}main{max-width:1000px;margin:28px auto;padding:0 22px}h1{font-size:28px;margin-bottom:6px}h2{font-size:20px}p{margin:8px 0}.note{background:#e7f0eb;border:1px solid #cbdcd1;padding:15px;border-radius:9px}.muted{font-size:13px;color:#61776d}nav{display:flex;gap:10px;margin:22px 0}button,input,textarea{font:inherit}button{border:1px solid #acc8b8;border-radius:7px;background:white;color:#254d3c;padding:9px 18px;cursor:pointer}button.active,button.primary{background:#275e49;color:white}button:disabled{opacity:.5;cursor:wait}#messages{min-height:180px}.message{max-width:86%;padding:15px 19px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;background:white;border:1px solid #d8e4dc;margin:14px 0}.message.user{margin-left:auto;background:#dcece2}.detail{max-width:86%;margin:0 0 20px;font-size:13px;color:#60746a}.detail pre{white-space:pre-wrap}textarea{width:100%;min-height:90px;border:1px solid #b2cabb;border-radius:8px;padding:12px;resize:vertical}.controls{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:10px 0}.controls label{font-size:13px}article{background:white;border:1px solid #d6e3db;border-radius:9px;padding:20px;margin:22px 0}.option{display:block;padding:12px;background:#f1f6f2;border-radius:7px;margin:9px 0;cursor:pointer}.option p{white-space:pre-wrap;margin:7px 0 0 24px}.error{color:#a43a2d}#status{margin:10px 0}.selection{font-weight:600}footer{margin:28px 0;color:#657b6e;font-size:13px}[hidden]{display:none!important}@media(max-width:620px){.message,.detail{max-width:96%}main{padding:0 14px}h1{font-size:24px}}
</style></head><body><main><h1>新奶绿 · 文字试聊</h1><p>明前奶绿 · 角色文字试聊（非本人联络渠道）</p><div class="note">本轮细化原声里的接话、短重复和停连。<a href="/prosody">查看原声节奏与试听片段</a>。<a href="/voice">使用V5 Dev混合语音</a>。保留互怼语气与措辞变化。<a href="/community">查看称呼、梗和原文</a>。<a href="/preferences">查看偏好原话与出处</a>。<a href="/improvements">查看本轮方法、对比和出处</a>。<a href="/knowledge">查看本轮资料与出处</a>。当前为文字试聊，更像与否仍按你的实际感受调整。<div class="muted">实时回复由 DeepSeek 生成，会发送本条消息与最近对话。自由聊天不写入本地聊天记录文件，刷新后清空。</div></div><nav><button id="chat-tab" class="active">自由试聊</button><button id="compare-tab">盲选对照</button></nav>
<section id="chat"><div id="messages"><p class="muted">可以聊日常、讲一件开心或烦心的事，也可以试试调侃、追问和话题切换。</p></div><form id="chat-form"><textarea id="message" aria-label="输入聊天内容" maxlength="2000" placeholder="输入你想聊的话题，Enter发送，Shift+Enter换行"></textarea><div class="controls"><label><input type="checkbox" id="semantic">按意思检索：问题也会发给智谱</label><span class="muted">已覆盖 10,934 条资料条目；含 24 条称呼与社区梗、78 条偏好卡</span><button class="primary" id="send">发送</button></div></form><div id="status" role="status" class="muted"></div><div class="controls"><button id="clear">清空本页对话</button></div></section>
<section id="compare" hidden><h2>哪种说法更像奶绿？</h2><p class="muted">本轮是同题表达对照；这里比较旧版Flash、新版Flash与新版Pro，顺序已打乱；人物相似度由你的实际选择判断。</p><p>每题三个版本，顺序已打乱。也可以选“差不多，选不出”或“都不像”。</p><p class="muted">对照回复已预先生成，浏览不会再次调用模型。你的选择只在点击“记录我的选择”后保存到本地。</p><form id="review-form"><div id="cases"></div><label>补充意见（可选）<textarea id="review-notes" maxlength="2000" placeholder="例如：太温柔、太爱反问、哈哈太多，或哪句话很像"></textarea></label><button class="primary">记录我的选择</button></form><p id="review-status" role="status"></p></section><footer>人物资料、原始字幕和你的本页对话分别处理。声音的轻笑、叹气和轻重仍需原声采样与试听。</footer></main><script>
const $=id=>document.getElementById(id);let history=[],pending=false,loaded=false;const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const names={neutral:'平常',warm:'温和',playful:'轻松调侃',serious:'认真',firm:'明确',normal:'正常',slower:'稍缓',soft:'柔和',steady:'平稳',none:'无',chuckle_candidate:'轻笑候选（尚未合成）',sigh_candidate:'叹气候选（尚未合成）'};
async function api(path,data){const res=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const out=await res.json();if(!res.ok)throw Error(out.error||'请求失败');return out}
function add(role,text,result){const box=el('div',text,'message '+role);$('messages').append(box);if(result){const details=el('details',undefined,'detail');details.append(el('summary','语气建议与本轮参考（尚无声音）'));const d=result.content.delivery;details.append(el('p','态度：'+names[d.tone]+'；节奏：'+names[d.pace]+'；力度：'+names[d.intensity]+'；小动作：'+names[d.nonverbal]));if(result.performance_plan){const p=result.performance_plan;details.append(el('p','原声节奏参考：'+(p.profile_titles.join('、')||'自然短回应')+'；以下只为表现建议，尚未生成声音。'));details.append(el('pre',p.units.map(u=>u.text+(u.pause_after==='short'?'〈短停〉':u.pause_after==='medium'?'〈停一下〉':'')).join('')));details.append(el('p',p.dynamic_contrast_hint));if(p.requested_delivery?.explicit_request)details.append(el('p','本句声音请求：'+({normal:'正常声音',quiet_requested:'轻声',whisper_requested:'悄悄说／耳语'}[p.requested_delivery.mode]||'正常声音')+'（尚未合成）'));if(p.tail_acknowledgement?.explicitly_requested)details.append(el('p','句尾轻嗯：本句请求已记录；候选原声尚待试听，未自动拼接声音。'))}for(const r of result.references||[])details.append(el('pre',r.text+'\n来源：'+r.source_refs.map(x=>x.source_id+(x.start_seconds!==undefined?' @ '+x.start_seconds+'秒':'')).join('、')));$('messages').append(details)}box.scrollIntoView({block:'nearest'})}
async function send(e){e.preventDefault();const question=$('message').value.trim();if(!question||pending)return;pending=true;$('send').disabled=true;$('status').className='muted';$('status').textContent='正在组织回复…';add('user',question);$('message').value='';try{const result=await api('/api/chat',{message:question,history:history.slice(-12),semantic:$('semantic').checked});add('assistant',result.content.reply,result);history.push({role:'user',content:question},{role:'assistant',content:result.content.reply});$('status').textContent=(result.notices||[]).join(' ')||(result.context_metadata?.retrieval==='semantic_opt_in+self_aliases'?'本轮已按意思检索。':'')}catch(err){$('status').textContent=err.message;$('status').className='error'}finally{pending=false;$('send').disabled=false}}
$('chat-form').onsubmit=send;$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();$('chat-form').requestSubmit()}};$('clear').onclick=()=>{if(pending)return;history=[];$('messages').replaceChildren();$('status').textContent='本页对话已清空。'};
function tab(name){$('chat').hidden=name!=='chat';$('compare').hidden=name!=='compare';$('chat-tab').classList.toggle('active',name==='chat');$('compare-tab').classList.toggle('active',name==='compare');if(name==='compare'&&!loaded)loadComparison().catch(e=>$('review-status').textContent=e.message)}$('chat-tab').onclick=()=>tab('chat');$('compare-tab').onclick=()=>tab('compare');
async function loadComparison(){const data=await api('/api/comparison');for(const c of data.cases){const card=el('article');card.append(el('h2',c.title),el('p',c.input));if(c.history?.length)card.append(el('p','前文：'+c.history.map(x=>(x.role==='user'?'你：':'对方：')+x.content).join(' / '),'muted'));for(const option of [...c.options,{label:'tie',reply:'差不多，选不出'},{label:'none',reply:'都不像'}]){const label=el('label',undefined,'option');const radio=el('input');radio.type='radio';radio.name=c.id;radio.value=option.label;radio.required=true;label.append(radio,el('span',' '+(option.label==='none'?'都不像':option.label==='tie'?'差不多，选不出':option.label),'selection'));if(!['none','tie'].includes(option.label))label.append(el('p',option.reply));card.append(label)}$('cases').append(card)}loaded=true}
$('review-form').onsubmit=async e=>{e.preventDefault();const form=new FormData(e.target);const selections=[...form.entries()].map(([case_id,choice])=>({case_id,choice}));try{const result=await api('/api/review',{selections,notes:$('review-notes').value});$('review-status').textContent='已保存你的实际选择，记录号：'+result.id+'。可以把补充意见继续告诉制作助手。'}catch(err){$('review-status').textContent=err.message}};

</script></body></html>'''

LOCK=threading.Lock()


def handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data,status=200,html=False):
            raw=(data if html else json.dumps(data,ensure_ascii=False)).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
        def send_media(self,prefix='/prosody-media/',files=None):
            name=self.path.removeprefix(prefix)
            path=(core.prosody.media_files() if files is None else files).get(name)
            if path is None:self.send({'error':'Not found'},404);return
            size=path.stat().st_size;start=0;end=size-1;status=200
            header=self.headers.get('Range')
            if header:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
                if not match or not any(match.groups()):self.send({'error':'Invalid range'},416);return
                left,right=match.groups()
                if left:start=int(left);end=min(size-1,int(right)) if right else size-1
                else:start=max(0,size-int(right))
                if start>=size or end<start:self.send({'error':'Invalid range'},416);return
                status=206
            self.send_response(status);self.send_header('Content-Type','image/png' if path.suffix=='.png' else 'audio/wav');self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            with path.open('rb') as stream:stream.seek(start);self.wfile.write(stream.read(end-start+1))
        def do_GET(self):
            if self.path=='/':self.send(PAGE,html=True)
            elif self.path=='/api/health':self.send({'project':'new-milkgreen-text-pilot','root':str(core.ROOT),'pid':os.getpid(),'bind':'127.0.0.1','voice':False,'qq':False})
            elif self.path=='/api/status':self.send({'semantic_items':10934,'community_items':24,'preference_items':78,'relationship_items':13,'supplement_semantic_items':3198,'semantic_retrieval':'query-stop-aligned-with-text-pilot','semantic_failure_fallback':'local_keywords','private_chat_saved':False,'expression_version':'lexical-v3.3','audio_detail_version':'audio-rhythm-v2.1','audio_detail_samples':32,'audio_detail_sampled_minutes':40,'full_timeline_event_screen_seconds':33654.288,'tail_hmm_default':'habitual_target_pending_canonical_example','new_breathy_references_enabled':False,'additional_hmm_search_minutes':24,'voice_preview_version':hybrid_voice.VERSION,'voice_preview_samples':30,'voice_preview_main_samples':10,'voice_preview_new_samples':30,'selected_voice_backend':'v5dev-stage1-hybrid','live_voice_enabled':False,'knowledge_version':'self-supplement-20261024','knowledge_review':'conditional user acceptance applied; source/audio verification scope recorded','candidate_acceptance':'conditional-candidate-acceptance-20261024'})
            elif self.path=='/knowledge':self.send((core.ROOT/'outputs/人物资料补充核对.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-materials':self.send((core.ROOT/'outputs/奶绿原声素材校对.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/api/voice-materials':self.send(voice_materials.summary())
            elif self.path.startswith('/voice-material-media/'):self.send_media('/voice-material-media/',voice_materials.media_files())
            elif self.path=='/voice-proplus':self.send((core.ROOT/'outputs/奶绿V2ProPlus双阶段语音.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/api/voice-proplus/status':self.send(proplus_voice.status())
            elif self.path.startswith('/api/voice-proplus/job/'):
                try:self.send(proplus_voice.job(self.path.rsplit('/',1)[-1]))
                except ValueError as exc:self.send({'error':str(exc)},404)
            elif self.path.startswith('/voice-proplus-media/'):self.send_media('/voice-proplus-media/',proplus_voice.media_files())
            elif self.path=='/voice-newsource':self.send((core.ROOT/'outputs/新素材V5Dev训练与试听.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-e6-archive':self.send((core.ROOT/'outputs/奶绿V5Dev混合语音.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/api/voice-newsource/status':self.send(newsource_voice.status())
            elif self.path.startswith('/api/voice-newsource/job/'):
                try:self.send(newsource_voice.job(self.path.rsplit('/',1)[-1]))
                except ValueError as exc:self.send({'error':str(exc)},404)
            elif self.path.startswith('/voice-newsource-media/'):self.send_media('/voice-newsource-media/',newsource_voice.media_files())
            elif self.path=='/voice':self.send((core.ROOT/'outputs'/('奶绿V2ProPlus双阶段语音.html' if proplus_voice.status()['ready'] else '新素材V5Dev训练与试听.html' if newsource_voice.status()['active_default'] else '奶绿V5Dev混合语音.html')).read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-v5-v2pro':self.send((core.ROOT/'outputs/奶绿V5与v2Pro对照.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-rescue':self.send((core.ROOT/'outputs/新参考Dev与Turbo对照.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-connected':self.send((core.ROOT/'outputs/参考降噪与连读修正.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/voice-gentle':self.send((core.ROOT/'outputs/温和去混响Dev与Turbo对照.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/api/voice-hybrid/status':self.send(hybrid_voice.status())
            elif self.path.startswith('/api/voice-hybrid/job/'):
                try:self.send(hybrid_voice.job(self.path.rsplit('/',1)[-1]))
                except ValueError as exc:self.send({'error':str(exc)},404)
            elif self.path.startswith('/voice-hybrid-media/'):self.send_media('/voice-hybrid-media/',hybrid_voice.media_files())
            elif self.path=='/voice-f5-v2pro':self.send((core.ROOT/'outputs/奶绿两种模型同原声对照.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-v5-media/'):self.send_media('/voice-v5-media/',voice_v5.media_files())
            elif self.path=='/voice-cadence':self.send((core.ROOT/'outputs/奶绿停连与自然度对照.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-backend-media/'):self.send_media('/voice-backend-media/',voice_backends.media_files())
            elif self.path=='/voice-trained':self.send((core.ROOT/'outputs/奶绿固定参考训练试音.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-cadence-media/'):self.send_media('/voice-cadence-media/',voice_cadence.media_files())
            elif self.path=='/voice-round3':self.send((core.ROOT/'outputs/奶绿v2Pro多参考试音.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-trial-media/'):self.send_media('/voice-trial-media/',voice_trial.media_files())
            elif self.path=='/voice-v2':self.send((core.ROOT/'outputs/奶绿v2Pro试音.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-round3-media/'):self.send_media('/voice-round3-media/',voice_round3.media_files())
            elif self.path=='/voice-v1':self.send((core.ROOT/'outputs/奶绿语音试音.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/voice-upgrade-media/'):self.send_media('/voice-upgrade-media/',voice_upgrade.media_files())
            elif self.path.startswith('/voice-media/'):self.send_media('/voice-media/',voice_preview.media_files())
            elif self.path=='/prosody':self.send((core.ROOT/'outputs/原声说话细节.html').read_text(encoding='utf-8'),html=True)
            elif self.path.startswith('/prosody-media/'):self.send_media()
            elif self.path=='/community':self.send((core.ROOT/'outputs/称呼与社区梗.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/preferences':self.send((core.ROOT/'outputs/偏好补充与措辞微调.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/improvements':self.send((core.ROOT/'outputs/表达优化与星瞳补充.html').read_text(encoding='utf-8'),html=True)
            elif self.path=='/api/comparison':
                path=core.ROOT/'eval/style-v3/blind.json'
                if not path.exists():self.send({'error':'对照回复还未生成。'},404);return
                data=json.loads(path.read_text(encoding='utf-8'))
                cases=[{k:c[k] for k in ['id','title','input','history','options']} for c in data['cases']]
                self.send({'cases':cases,'human_review':'pending until actual choices submitted'})
            else:self.send({'error':'Not found'},404)
        def do_POST(self):
            origin='http://127.0.0.1:'+str(self.server.server_port)
            if self.headers.get('Origin')!=origin or self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):self.send({'error':'只接受本页发起的请求。'},403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Content-Type','').split(';')[0]!='application/json' or not 1<=length<=65536:raise ValueError('请求格式或长度不合适。')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('JSON对象格式错误。')
                if self.path=='/api/chat':
                    if not LOCK.acquire(blocking=False):self.send({'error':'上一条回复仍在生成，请稍等。'},409);return
                    try:
                        if not isinstance(data.get('history',[]),list):raise ValueError('对话历史格式错误。')
                        result=core.chat(data.get('message'),data.get('history',[]),data.get('semantic') is True)
                        self.send(result)
                    finally:LOCK.release()
                elif self.path=='/api/voice-proplus/generate':self.send(proplus_voice.start_job(data))
                elif self.path=='/api/voice-newsource/generate':self.send(newsource_voice.start_job(data))
                elif self.path=='/api/voice-newsource/review':self.send({'id':newsource_voice.save_review(data)})
                elif self.path=='/api/voice-hybrid/generate':self.send(hybrid_voice.start_job(data))
                elif self.path=='/api/voice-hybrid/review':self.send({'id':hybrid_voice.save_review(data)})
                elif self.path=='/api/voice-v5/review':self.send({'id':voice_v5.save_review(data)})
                elif self.path=='/api/voice-backends/review':self.send({'id':voice_backends.save_review(data)})
                elif self.path=='/api/voice-materials/review':self.send(voice_materials.save_review(data))
                elif self.path=='/api/voice-cadence/review':self.send({'id':voice_cadence.save_review(data)})
                elif self.path=='/api/voice-trial/review':self.send({'id':voice_trial.save_review(data)})
                elif self.path=='/api/voice-round3/review':self.send({'id':voice_round3.save_review(data)})
                elif self.path=='/api/voice-round3/reference-review':self.send({'id':voice_round3.save_reference(data)})
                elif self.path=='/api/voice-upgrade/review':self.send({'id':voice_upgrade.save_review(data)})
                elif self.path=='/api/voice-preview/review':self.send({'id':voice_preview.save_review(data)})
                elif self.path=='/api/review':
                    blind=core.pub.load('eval/style-v3/blind.json');ids={x['id'] for x in blind['cases']};votes=data.get('selections',[])
                    if not isinstance(votes,list) or {x.get('case_id') for x in votes if isinstance(x,dict)}!=ids or len(votes)!=len(ids) or any(x.get('choice') not in ['A','B','C','none','tie'] for x in votes):raise ValueError('请为每一题选择一个版本或“都不像”。')
                    record={'id':uuid.uuid4().hex[:12],'submitted_at':core.pub.now(),'source':'explicit browser form submission','comparison_file_sha256':hashlib.sha256((core.ROOT/'eval/style-v3/blind.json').read_bytes()).hexdigest(),'selections':votes,'notes':str(data.get('notes',''))[:2000],'human_similarity_verdict':'individual choices; no automatic overall pass'}
                    folder=core.ROOT/'review/text-pilot';folder.mkdir(parents=True,exist_ok=True)
                    (folder/(record['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');self.send({'id':record['id']})
                else:self.send({'error':'Not found'},404)
            except (ValueError,KeyError,TypeError) as exc:self.send({'error':str(exc)[:200]},400)
            except Exception as exc:self.send({'error':str(exc)[:220] if isinstance(exc,RuntimeError) else '本次调用未完成：'+type(exc).__name__},502)
    return Handler


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=core.ROOT);parser.add_argument('--port',type=int,default=0);args=parser.parse_args();core.ROOT=args.root.resolve();core.engine.ROOT=core.ROOT;core.pub.ROOT=core.ROOT;core.self_knowledge.ROOT=core.ROOT;core.style3.ROOT=core.ROOT;core.relationships.ROOT=core.ROOT;core.call_limits.ROOT=core.ROOT;core.preferences.ROOT=core.ROOT;core.community.ROOT=core.ROOT;core.prosody.ROOT=core.ROOT;voice_preview.ROOT=core.ROOT;voice_upgrade.ROOT=core.ROOT;voice_round3.ROOT=core.ROOT;voice_trial.ROOT=core.ROOT;voice_cadence.ROOT=core.ROOT;voice_materials.ROOT=core.ROOT;voice_backends.ROOT=core.ROOT;voice_v5.ROOT=core.ROOT;hybrid_voice.ROOT=core.ROOT
    if core.pub.load('project.json')['character_id']!='new-milkgreen':raise ValueError('Wrong character project')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler());server.daemon_threads=True
    state={'project':'new-milkgreen-text-pilot','root':str(core.ROOT),'pid':os.getpid(),'port':server.server_port,'url':'http://127.0.0.1:'+str(server.server_port)+'/'}
    core.pub.save('logs/text-chat.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
    try:server.serve_forever()
    finally:server.server_close()


if __name__=='__main__':main()
