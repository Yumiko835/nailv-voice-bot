"""Loopback chat bridge; each local GPU worker exits after the utterance."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from pathlib import Path
from contextlib import contextmanager
import json,os,sys,time,threading,uuid,subprocess

ROOT=Path(project_path(''))
O=ROOT/'voice/comparison/cosyvoice2-20261026'
R=ROOT/'runtime/cosyvoice2'
sys.path.insert(0,str(ROOT/'tools'))
import nailv_cosy_performance as performance
import nailv_cosy_delivery as delivery
LOCK=threading.Lock()
JOBS={}
MAX_JOBS=80
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def default_profile():
    path=O/'voice-delivery.json'
    return read(path)['default_profile'] if path.is_file() else 'baseline'

def model_variants():
    path=O/'model-variants.json'
    return read(path)['variants'] if path.is_file() else {'base':{'label':'官方原版'}}

def default_model_variant():
    path=O/'model-variants.json'
    if not path.is_file():return 'base'
    config=read(path);key=config.get('default_variant','base')
    if key not in config['variants']:raise RuntimeError('默认声音版本配置无效。')
    return key

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

@contextmanager
def gpu_lease(name):
    """Coordinate with the old project's generation button; never stop foreign jobs."""
    lock=O/'gpu.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('本项目还有语音任务在运行，请稍候。') from None
    os.write(fd,json.dumps({'pid':os.getpid(),'job':name}).encode());os.close(fd)
    status=ROOT/'voice/training/v2proplus-newsource-20261025/status.json'
    previous=None;activity='cosyvoice2-character-'+name
    try:
        if status.exists():
            previous=read(status)
            if previous.get('stage','') not in ('proplus-ready','ready','complete','completed','proplus-finished'):
                raise RuntimeError('旧语音工程仍显示正在使用显卡，先等该任务完成。')
            write(status,previous|{'stage':'proplus-comparing-continuation','activity':activity,
                'message':'本项目CosyVoice 2正在生成；暂时保留显卡给当前任务。'})
        yield
    finally:
        if previous is not None and status.exists() and read(status).get('activity')==activity:
            write(status,previous)
        lock.unlink(missing_ok=True)

def run_inference(request_path,out,name):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with gpu_lease(name),(out/'worker.out.log').open('w',encoding='utf-8') as stdout,(out/'worker.err.log').open('w',encoding='utf-8') as stderr:
        process=subprocess.Popen([str(R/'.venv/Scripts/python.exe'),'-B','-X','utf8',str(R/'scripts/infer.py'),
             '--requests',str(request_path),'--out',str(out)],cwd=str(R/'src'),stdout=stdout,stderr=stderr,creationflags=HIDDEN)
        try:code=process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=20)
            raise RuntimeError('本次本地语音超时，已停止这一个生成进程；文字仍可阅读。') from None
        write(out/'worker-exit.json',{'exit_code':code,'exit_code_hex':hex(code & 0xffffffff)})
        if code!=0:
            raise RuntimeError('本次语音未生成成功，文字已保留。可查看当前任务的worker.err.log。')
    data=read(out/'manifest.json')
    if not data.get('samples'):raise RuntimeError('本次没有有效音频，保留文字回复。')
    return data

def _generate(payload,job,enable_tags=True):
    performance.validate_reference(payload)
    folder=O/'live-runs'/job['id'];folder.mkdir(parents=True,exist_ok=False)
    tts=payload['tts_text'] if enable_tags else payload['spoken_text']
    row={'id':job['id'],'label':'本地聊天语音','style':payload['style'],'mode':'zero_shot',
         'text':payload['spoken_text'],'spoken_text':payload['spoken_text'],'tts_text':tts,
         'seed':731,'route_source':payload['route_source'],'fragment_interval':payload.get('fragment_interval',.18),
         'chunk_mode':payload.get('chunk_mode','legacy'),'delivery_profile':payload.get('delivery_profile','baseline'),
         'delivery_notes':payload.get('delivery_notes',[]),'model_variant':payload.get('model_variant') or default_model_variant()}
    request=folder/'request.json';write(request,{'samples':[row]})
    data=run_inference(request,folder/'generated',job['id'])
    result=data['samples'][0]
    job.update(audio='/live/'+job['id']+'.wav',state='done',seconds=result['seconds'])

def _work(job,data,chat):
    try:
        text=data['message'] if chat else data['text']
        if chat:
            import nailv_text_core as core
            result=core.chat(text,data.get('history',[]),semantic=False,performance=True,cache=False)
            payload=result['speech']
            parsed=performance.parse_reply('<emotion:'+payload['emotion']+'>'+payload['tts_text'],
                question=text,history=data.get('history',[]),force_emotion=data['emotion']) if data.get('emotion') else {
                    'clean_text':payload['spoken_text'],'tts_payload':payload,'warnings':result.get('speech_warnings',[])}
        else:
            parsed=performance.parse_reply(text,force_emotion=data.get('emotion'))
        parsed['tts_payload']=delivery.plan(parsed['tts_payload'],data.get('delivery_profile') or default_profile(),data.get('history',[]))
        if not data.get('enable_tags',True):
            parsed['tts_payload']['tts_text']=parsed['clean_text'];parsed['tts_payload']['events']=[]
        parsed['tts_payload']['model_variant']=data.get('model_variant') or default_model_variant()
        job.update(state='text_ready',clean_text=parsed['clean_text'],emotion=parsed['tts_payload']['emotion'],
                   route_source=parsed['tts_payload']['route_source'],warnings=parsed['warnings'],
                   voice_events=parsed['tts_payload']['events'],delivery_profile=parsed['tts_payload']['delivery_profile'],
                   model_variant=parsed['tts_payload']['model_variant'])
        _generate(parsed['tts_payload'],job,data.get('enable_tags',True))
    except Exception as exc:
        job.update(state='error',error=str(exc)[:220] if isinstance(exc,(RuntimeError,ValueError)) else '生成未完成：'+type(exc).__name__)
    finally:
        LOCK.release()

def start(data,chat=True):
    if not isinstance(data,dict):raise ValueError('请求格式错误。')
    field='message' if chat else 'text';text=data.get(field)
    if not isinstance(text,str) or not 1<=len(text.strip())<=(2000 if chat else 600):raise ValueError('请先输入合适长度的文字。')
    history=data.get('history',[])
    if not isinstance(history,list) or len(history)>12 or any(not isinstance(x,dict) or x.get('role') not in ('user','assistant') or not isinstance(x.get('content'),str) or len(x['content'])>2000 for x in history):raise ValueError('对话历史格式错误。')
    emotion=data.get('emotion')
    if emotion and emotion not in performance.ALIASES and emotion not in performance.DISABLED:raise ValueError('情绪不在当前参考池中。')
    if data.get('delivery_profile') and data['delivery_profile'] not in delivery.PROFILES:raise ValueError('语音表达方案不存在。')
    data=dict(data);data['model_variant']=data.get('model_variant') or default_model_variant()
    if data['model_variant'] not in model_variants():raise ValueError('专属模型版本不存在。')
    if len(JOBS)>=MAX_JOBS:raise RuntimeError('本次页面服务已达到任务上限，请重启试听页后继续。')
    if not LOCK.acquire(False):raise RuntimeError('上一条聊天或语音仍在生成，请稍等。')
    job={'id':uuid.uuid4().hex,'state':'chatting' if chat else 'preparing'};JOBS[job['id']]=job
    threading.Thread(target=_work,args=(job,data,chat),daemon=True).start()
    return {'id':job['id'],'state':job['state']}

def get_job(key):
    if key not in JOBS:raise ValueError('任务不存在或页面服务已重启。')
    return dict(JOBS[key])

def live_audio(key):
    if key not in JOBS or JOBS[key].get('state')!='done':return None
    folder=O/'live-runs'/key/'generated'
    result=read(folder/'manifest.json')['samples'][0]
    path=Path(result['playback']).resolve()
    return path if path.is_relative_to(folder.resolve()) and path.is_file() else None
