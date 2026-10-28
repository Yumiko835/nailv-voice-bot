"""Loopback-only integrated character chat, switchable trial with original CV2 untouched."""

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
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import os,sys,json,threading,subprocess,queue,time,uuid,re,urllib.parse,argparse,atexit
ROOT=Path(project_path(''));R2=ROOT/'runtime/cosyvoice2';R3=ROOT/'runtime/cosyvoice3'
OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'));import nailv_cosy_performance as perf
import nailv_live_emotions as live_emotions
live_emotions.configure(perf)
import nailv_voice_router as voice_router
PARSER=argparse.ArgumentParser();PARSER.add_argument('--port',type=int,default=49856);args=PARSER.parse_args()
SCRIPTS=Path(__file__).parent;HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0);JOBS={};LOCK=threading.Lock()
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)
class Process:
    def __init__(self,script):self.script=script;self.p=None;self.q=None;self.ready=None
    def start(self):
        if self.p and self.p.poll() is None:return 0.
        start=time.monotonic();self.q=queue.Queue()
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1');env.pop('CUDA_VISIBLE_DEVICES',None)
        self.log=(OUT/(self.script+'.stderr.log')).open('a',encoding='utf-8')
        self.p=subprocess.Popen([str(R2/'.venv/Scripts/python.exe'),'-B','-X','utf8',str(SCRIPTS/self.script)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',env=env,creationflags=HIDDEN,cwd=str(SCRIPTS))
        process=self.p;messages=self.q
        def pump():
            for line in process.stdout:
                try:messages.put(json.loads(line))
                except ValueError:continue
            code=process.wait();write(OUT/(self.script+'.exit.json'),{'code':code,'hex':hex(code&0xffffffff)})
            messages.put({'event':'error','error':'本地工作进程已退出（'+hex(code&0xffffffff)+'）。'})
        threading.Thread(target=pump,daemon=True).start()
        result=self.receive(240)
        if result.get('event')!='ready':raise RuntimeError(result.get('error','工作进程未准备好'))
        self.ready=result;return time.monotonic()-start
    def receive(self,timeout=240):
        try:return self.q.get(timeout=timeout)
        except queue.Empty:self.stop();raise RuntimeError('本地工作进程超时，文字回复已保留。') from None
    def call(self,data):
        cold=self.start();self.p.stdin.write(json.dumps(data,ensure_ascii=False)+'\n');self.p.stdin.flush();result=self.receive()
        if result.get('event')!='result':raise RuntimeError(result.get('error','本地生成未完成。'))
        return result['result'],cold
    def stop(self):
        process=self.p
        if not process:return
        if process.poll() is None:
            try:process.stdin.write('{"op":"quit"}\n');process.stdin.flush();process.wait(timeout=20)
            except Exception:process.kill();process.wait(timeout=20)
        lock=ROOT/'voice/comparison/cosyvoice2-20261026/gpu.lock'
        if lock.exists():
            try:
                if json.loads(lock.read_text(encoding='utf-8')).get('pid')==process.pid:lock.unlink()
            except (ValueError,OSError):pass
        self.p=None;self.ready=None
        if hasattr(self,'log'):self.log.close()
class SerialEngine:
    p=None;ready={'mode':'stable serial trial; resident optimization disabled'}
    def start(self):return 0.
    def stop(self):pass
    def call(self,data):
        import shutil
        sys.path.insert(0,str(R2/'scripts'));import cosy_chat_backend as coord
        g=ROOT/'voice/training/v2proplus-newsource-20261025';o=Path(data['folder']);job=data['id']
        source=g/'live-bridge'/job;source.mkdir(parents=True,exist_ok=True)
        req=source/'requests.json';write(req,{'samples':[{'id':job,'text':data['text'],'style':data['style'],'seed':data['seed'],'temperature':.85,'repetition_penalty':1.2}]})
        py=R2/'.venv/Scripts/python.exe';gpy=ROOT.parent.parent/dependency_path("gpt_sovits",'.venv/Scripts/python.exe')
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1');env.pop('CUDA_VISIBLE_DEVICES',None)
        begin=time.monotonic()
        with coord.gpu_lease('integrated-serial-GPT'),(source/'generate.log').open('w',encoding='utf-8') as log:
            subprocess.run([str(gpy),'-B',str(g/'scripts/synthesize.py'),'--requests',str(req),'--reference-manifest',str(g/'cross-engine-20261026/reference-manifest.json'),'--out',str(source/'generated')],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=240,check=True,creationflags=HIDDEN)
        first=time.monotonic();row=json.loads((source/'generated/manifest.json').read_text(encoding='utf-8'))['samples'][0]
        from hashlib import file_digest
        with Path(row['raw']).open('rb') as f:digest=file_digest(f,'sha256').hexdigest()
        request=OUT/'requests'/(job+'.json');write(request,{'samples':[{'id':job,'text':data['text'],'tts_text':data['text'],'style':data['style'],'seed':data['seed'],'mode':'voice_conversion','source_audio':row['raw'],'source_sha256':digest}]})
        checkpoints=json.loads((ROOT/'voice/training/cosyvoice3-personal-20261026/checkpoints.json').read_text(encoding='utf-8'))['models']
        checkpoint=next(x['merged'] for x in checkpoints if x.get('dataset_pass_fraction')==.5)
        with (source/'render.log').open('w',encoding='utf-8') as log:
            subprocess.run([str(py),'-B',str(SCRIPTS/'infer_cv3_trial.py'),'--requests',str(request),'--out',str(o),'--checkpoint',checkpoint],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=300,check=True,creationflags=HIDDEN)
        result=json.loads((o/'manifest.json').read_text(encoding='utf-8'))['samples'][0]
        shutil.copy2(result['playback'],o/'speech.wav');shutil.copy2(row['playback'],o/'source-control.wav')
        result.update(generation_seconds=time.monotonic()-begin,parts=[{'GPT_with_load_seconds':first-begin,'CV3_with_load_and_check_seconds':time.monotonic()-first}],memory={'total_GPU_MiB':None},serial_mode=True)
        return result,0.
from fast_bridge_runtime import FastEngine
FAST=os.environ.get('NAILV_BRIDGE_MODE','resident')=='resident'
GPU=FastEngine() if FAST else SerialEngine();CPU=Process('isolated_critic_worker.py')
atexit.register(GPU.stop);atexit.register(CPU.stop)
def execute(job,data,mode):
    started=time.monotonic()
    try:
        if mode=='warm':
            job['state']='loading'
            if data.get('evaluate',False):CPU.start()
            load=GPU.start();job.update(state='done',load_seconds=load);return
        if mode=='chat':
            import nailv_text_core as core
            result=core.chat(data['message'],data.get('history',[]),semantic=data.get('semantic',True),performance=False,voice_routing=True,cache=False)
            raw=result['content']['reply']
            chat_delivery=result['content'].get('delivery',{})
            context=result.get('context_metadata',{})
            job.update(chat_delivery=chat_delivery,retrieval={'mode':context.get('retrieval'),'provided_fact_ids':context.get('provided_fact_ids',[]),'used_fact_ids':result['content'].get('used_fact_ids',[]),'notices':result.get('notices',[])})
        else:raw=data['text'];chat_delivery=data.get('delivery',{})
        text_seconds=time.monotonic()-started
        routing=voice_router.route(perf.strip_markup(raw),question=data.get('message',''),history=data.get('history',[]),
            manual=perf.ALIASES.get(data.get('emotion')) if data.get('emotion') else None,allowed=perf.active_bank(),delivery=chat_delivery)
        parsed=perf.parse_reply(raw,question=data.get('message',''),history=data.get('history',[]),force_emotion=routing['style'])
        parsed['tts_payload']['route_source']=routing['source']
        text=parsed['clean_text'];payload=parsed['tts_payload']
        job.update(state='generating',clean_text=text,emotion=payload['emotion'],style=payload['style'],
            route_source=payload['route_source'],routing=routing,text_seconds=text_seconds,warnings=parsed['warnings'])
        if routing.get('affect'):job['emotion']=routing['affect']
        folder=OUT/'runs'/job['id']
        if data.get('evaluate',False):CPU.start()
        result,cold=GPU.call({'id':job['id'],'folder':str(folder),'text':text,'style':payload['style'],'reference_profile':routing.get('reference_profile'),'seed':int(job['id'][:8],16)})
        job.update(state='checking',synthesis_seconds=result['generation_seconds'],load_seconds=cold)
        before=time.monotonic()
        import wave,audioop
        with wave.open(str(folder/'speech.wav'),'rb') as audio:
            rate=audio.getframerate();width=audio.getsampwidth();frames=audio.getnframes()
            pcm=audio.readframes(frames)
        if rate not in (24000,32000,44100,48000) or width not in (2,3,4) or not .2<frames/rate<90 or audioop.rms(pcm,width)<2:
            raise RuntimeError('本地音频文件为空、静音或格式异常。')
        basic={'valid_PCM_WAV':True,'sample_rate':rate,'sample_width':width,'seconds':frames/rate}
        if data.get('evaluate',False):
            crit,cpu_cold=CPU.call({'folder':str(folder)})
            crit.update(performed=True,basic_audio_check=basic)
        else:
            crit={'performed':False,'reason':'Full acoustic critic is for training/test auditions, not live QQ replies.',
                  'basic_audio_check':basic,'flags':[],'recognized':None};cpu_cold=0.
        job.update(state='done',audio='/live/'+job['id']+'.wav',source_audio='/source/'+job['id']+'.wav',
            seconds=result['seconds'],critic=crit,memory=result['memory'],parts=result['parts'],
            critic_seconds=time.monotonic()-before,total_seconds=time.monotonic()-started,
            cpu_first_load_seconds=cpu_cold)
        write(folder/'delivery.json',{'job':job,'no_performance_tags_requested_from_chat_LLM':True,
            'same_character_RAG_chat_pipeline':True,'human_listening_pass':False})
    except Exception as exc:
        import traceback
        with (OUT/'server-errors.log').open('a',encoding='utf-8') as log:traceback.print_exc(file=log)
        job.update(state='error',error=str(exc)[:240],total_seconds=time.monotonic()-started)
        if FAST:GPU.stop()
    finally:LOCK.release()
def start(data,mode):
    if not isinstance(data,dict):raise ValueError('请求格式不对。')
    if mode!='warm':
        field='message' if mode=='chat' else 'text'
        if not isinstance(data.get(field),str) or not 1<=len(data[field].strip())<=(2000 if mode=='chat' else 600):raise ValueError('请输入合适长度的文字。')
        history=data.get('history',[])
        if not isinstance(history,list) or len(history)>12 or any(not isinstance(x,dict) or x.get('role') not in ('user','assistant') or not isinstance(x.get('content'),str) or len(x['content'])>2000 for x in history):raise ValueError('历史对话格式不对。')
        if data.get('emotion') and data['emotion'] not in perf.ALIASES:raise ValueError('参考语气不存在或已停用。')
        if 'semantic' in data and not isinstance(data['semantic'],bool):raise ValueError('语义检索开关必须是布尔值。')
        if 'evaluate' in data and not isinstance(data['evaluate'],bool):raise ValueError('评测开关必须是布尔值。')
        if 'delivery' in data and (not isinstance(data['delivery'],dict) or len(data['delivery'])>8 or any(not isinstance(k,str) or not isinstance(v,str) or len(v)>80 for k,v in data['delivery'].items())):raise ValueError('后台情绪字段格式不对。')
    if not LOCK.acquire(False):raise RuntimeError('上一条还在处理中，请稍等。')
    job={'id':uuid.uuid4().hex,'state':'chatting' if mode=='chat' else 'preparing','mode':mode};JOBS[job['id']]=job
    threading.Thread(target=execute,args=(job,data,mode),daemon=True).start();return dict(job)

class Handler(BaseHTTPRequestHandler):
    def valid(self):return self.headers.get('Host')=='127.0.0.1:'+str(args.port)
    def send_json(self,d,status=200):
        b=json.dumps(d,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
    def do_POST(self):
        if not self.valid() or self.headers.get('Origin')!='http://127.0.0.1:'+str(args.port):self.send_error(403);return
        try:
            n=int(self.headers.get('Content-Length','0'));assert 1<=n<=65536
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('请求必须是JSON。')
            data=json.loads(self.rfile.read(n));name=urllib.parse.urlsplit(self.path).path
            if name in ['/api/chat','/api/speak','/api/warm']:self.send_json(start(data,name.split('/')[-1]),202)
            elif name=='/api/route-preview':
                if not isinstance(data.get('text'),str) or not 1<=len(data['text'])<=600:raise ValueError('请输入回复文本。')
                self.send_json(voice_router.route(perf.strip_markup(data['text']),question=data.get('message',''),history=data.get('history',[]),delivery=data.get('delivery'),manual=perf.ALIASES.get(data.get('emotion')),allowed=perf.active_bank()))
            elif name=='/api/release':
                if not LOCK.acquire(False):raise RuntimeError('当前仍在生成，结束后再释放。')
                try:GPU.stop();CPU.stop();self.send_json({'released':True})
                finally:LOCK.release()
            else:self.send_error(404)
        except RuntimeError as exc:self.send_json({'error':str(exc)},409)
        except Exception as exc:self.send_json({'error':str(exc)[:240]},400)
    def do_HEAD(self):self.respond(False)
    def do_GET(self):self.respond(True)
    def respond(self,body):
        if not self.valid():self.send_error(403);return
        parsed=urllib.parse.urlsplit(self.path);name=parsed.path
        if name=='/api/status':self.send_json({'engine':'GPT6 / SoVITS14 → D official HiFT / RP1.20 + accepted calm confirmation','busy':LOCK.locked(),
            'resident':bool(GPU.p and GPU.p.poll() is None),'receipt':GPU.ready,'serial_mode':not FAST,'router_version':voice_router.VERSION,
            'emotions':[{'id':k,'label':perf.LABELS[k]} for k in perf.active_bank()],
            'emotion_taxonomy':live_emotions.VERSION,
            'LLM_performance_tags':False,'background_emotion_metadata':True,'semantic_retrieval_available':True,'critic_flags_advisory':True,'full_critic_default':False,'evaluation_process':'isolated CPU','old_default_unchanged':False,'sampling_default':{'repetition_penalty':1.2,'temperature':.85,'top_k':5,'top_p':.9},'confirmation_duration_editing':True,
            'confirmation_policy':{'version':'calm-complete-hum313-v1','target_ms':313,'conditional':True,'keep_original_punctuation':True,'keep_original_reference':True,'no_character_timestamps':True,'already_short_or_connected':'leave native'}});return
        if name=='/api/job':
            key=urllib.parse.parse_qs(parsed.query).get('id',[''])[0]
            self.send_json(dict(JOBS[key]) if key in JOBS else {'error':'任务不存在。'},200 if key in JOBS else 404);return
        target=OUT/'index.html' if name in ['/','/index.html'] else None
        match=re.fullmatch(r'/(live|source)/([a-f0-9]{32})\.wav',name)
        if match and match[2] in JOBS and JOBS[match[2]]['state']=='done':target=OUT/'runs'/match[2]/('speech.wav' if match[1]=='live' else 'source-control.wav')
        if not target or not target.is_file():self.send_error(404);return
        size=target.stat().st_size;lo=0;hi=size-1;partial=False
        if self.headers.get('Range'):
            m=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers['Range'])
            if not m:self.send_error(416);return
            lo=int(m[1]);hi=min(hi,int(m[2])) if m[2] else hi
            if lo>hi or lo>=size:self.send_error(416);return
            partial=True
        self.send_response(206 if partial else 200);self.send_header('Content-Type','text/html; charset=utf-8' if target.suffix=='.html' else 'audio/wav');self.send_header('Content-Length',str(hi-lo+1));self.send_header('Cache-Control','no-store');self.send_header('Accept-Ranges','bytes')
        if partial:self.send_header('Content-Range',f'bytes {lo}-{hi}/{size}')
        self.end_headers()
        if body:
            with target.open('rb') as f:
                f.seek(lo)
                try:self.wfile.write(f.read(hi-lo+1))
                except (BrokenPipeError,ConnectionResetError):pass
    def log_message(self,*args):pass
# Preserve already generated local audio links across a controlled service reload.
for saved in (OUT/'runs').glob('*/delivery.json'):
    try:
        previous=json.loads(saved.read_text(encoding='utf-8'))['job']
        if previous.get('state')=='done':JOBS[previous['id']]=previous
    except (ValueError,KeyError,OSError):pass
write(OUT/'server.json',{'pid':os.getpid(),'port':args.port,'script':str(Path(__file__).resolve()),'url':f'http://127.0.0.1:{args.port}/','router_version':voice_router.VERSION})
server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.daemon_threads=True
try:server.serve_forever()
finally:GPU.stop();CPU.stop()
