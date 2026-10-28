"""Supervise a shared resident runtime; leave accepted serial fallback intact."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import os,sys,json,time,uuid,subprocess,shutil,threading
from pathlib import Path
ROOT=Path(project_path(''));R2=ROOT/'runtime/cosyvoice2';R3=ROOT/'runtime/cosyvoice3'
OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge';HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)
class Worker:
    def __init__(self,role,parent):self.role=role;self.parent=parent;self.p=None;self.ready=None;self.state=None
    def start(self):
        if self.p and self.p.poll() is None:return
        self.state=self.parent/self.role;self.state.mkdir(parents=True,exist_ok=True)
        gpy=ROOT.parent.parent/dependency_path("gpt_sovits",'.venv/Scripts/python.exe')
        py=gpy if self.role=='gpt' else R2/'.venv/Scripts/python.exe'
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1');env.pop('CUDA_VISIBLE_DEVICES',None)
        script=Path(__file__).parent/'fast_voice_worker.py'
        self.log=(self.state/'worker.log').open('w',encoding='utf-8')
        self.p=subprocess.Popen([str(py),'-B','-X','faulthandler',str(script),'--role',self.role,'--state',str(self.state)],
            stdout=self.log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,cwd=str(ROOT),env=env,creationflags=HIDDEN)
        self.wait(self.state/'ready.json',180);self.ready=read(self.state/'ready.json')
    def wait(self,path,timeout):
        start=time.monotonic()
        while not path.exists():
            if self.p.poll() is not None:raise RuntimeError(f'{self.role}工作进程退出：{hex(self.p.returncode&0xffffffff)}；日志：{self.state}')
            if (self.state/'failed.json').exists():raise RuntimeError(read(self.state/'failed.json')['error'])
            if time.monotonic()-start>timeout:raise RuntimeError(self.role+'工作进程超时。')
            time.sleep(.1)
    def call(self,row,timeout=180):
        key=uuid.uuid4().hex;request=self.state/(key+'.request.json');reply=self.state/(key+'.reply.json')
        write(request,row);self.wait(reply,timeout);result=read(reply)
        if 'error' in result:raise RuntimeError(result['error'])
        return result.get('result',result)
    def stop(self):
        if self.p and self.p.poll() is None:
            try:self.call({'op':'quit'},20);self.p.wait(timeout=20)
            except Exception:
                # Only this worker's exact state path may be terminated.
                if self.ready:
                    import psutil
                    try:
                        p=psutil.Process(self.ready['pid'])
                        if str(self.state) in ' '.join(p.cmdline()) and 'fast_voice_worker.py' in ' '.join(p.cmdline()):p.terminate();p.wait(timeout=10)
                    except psutil.NoSuchProcess:pass
                if self.p.poll() is None:self.p.kill();self.p.wait(timeout=10)
        if hasattr(self,'log'):self.log.close()
        self.p=None
class FastEngine:
    def __init__(self):self.gpt=None;self.cv3=None;self.lease=None;self.ready=None;self.p=None;self.state=None
    def start(self):
        if self.gpt and self.cv3 and self.gpt.p.poll() is None and self.cv3.p.poll() is None:return 0.
        self.stop();sys.path.insert(0,str(R2/'scripts'));import cosy_chat_backend as coordination
        self.lease=coordination.gpu_lease('resident-GPT-CV3');self.lease.__enter__();start=time.monotonic()
        self.state=OUT/'fast-state'/uuid.uuid4().hex
        try:
            self.gpt=Worker('pair',self.state);self.gpt.start()
            self.cv3=self.gpt
            self.p=self.gpt.p;self.ready={'mode':'shared resident runtime','load_seconds':time.monotonic()-start,
                'GPT':self.gpt.ready,'CV3':self.cv3.ready,'CV3_LLM_loaded':False}
            write(self.state/'pair-ready.json',self.ready);return time.monotonic()-start
        except Exception:self.stop();raise
    def call(self,data):
        cold=self.start();start=time.monotonic();folder=Path(data['folder']).resolve();assert folder.is_relative_to((OUT/'runs').resolve())
        # Pack complete short sentences together; only bound genuinely long replies.
        sys.path.insert(0,str(ROOT/'tools'));import nailv_cosy_delivery as delivery
        chunks=delivery.chunks(data['text'],'thought',limit=64);assert ''.join(chunks)==data['text']
        parts=[];sources=[];timings=[]
        for i,text in enumerate(chunks):
            sub=folder if len(chunks)==1 else folder/f'chunk-{i+1}'
            row=data|{'folder':str(sub),'text':text,'id':data['id'] if len(chunks)==1 else data['id']+f'-{i+1}','seed':(data['seed']+i)%2**32}
            a=time.monotonic();source=self.gpt.call(row|{'op':'gpt'});b=time.monotonic()
            result=self.cv3.call(row|{'source_audio':source['raw'],'source_sha256':source['raw_sha256'],'source_pause_guard':source.get('pause_guard',{}),'render_path':'hift_only','flow_variant':'official'});c=time.monotonic()
            timings.append({'text':text,'GPT_seconds':b-a,'CV3_seconds':c-b,'GPT_native_seconds':source['generation_seconds'],'CV3_native_seconds':result['generation_seconds'],'source_attempts':len(source['attempts']),'pause_guard':source.get('pause_guard',{}),'confirmation_hmm':result['confirmation_hmm']})
            parts.append(result);sources.append(source)
        if len(parts)==1:
            result=parts[0];shutil.copy2(sources[0]['playback'],folder/'source-control.wav')
        else:
            # Native-rate concatenation only; no pitch/tempo/reconstruction edits.
            import numpy as np,soundfile as sf
            def join(rows,rate,dest):
                waves=[]
                for i,r in enumerate(rows):
                    y,sr=sf.read(r['raw'],dtype='float32');assert sr==rate
                    waves.append(y)
                    if i<len(rows)-1:waves.append(np.zeros(round(.12*rate),np.float32))
                y=np.concatenate(waves);gain=min(1.,.1/max(float(np.sqrt(np.mean(y*y))),1e-9),.89/max(float(abs(y).max()),1e-9))
                sf.write(dest,y,rate,subtype='PCM_24');return y,gain
            y,gain=join(parts,24000,folder/'raw.wav');sf.write(folder/'speech.wav',np.r_[np.zeros(3840),y*gain,np.zeros(7680)],24000,subtype='PCM_24')
            sy,sg=join(sources,32000,folder/'source-raw.wav');sf.write(folder/'source-control.wav',np.r_[np.zeros(5120),sy*sg,np.zeros(10240)],32000,subtype='PCM_24')
            result=parts[0]|{'id':data['id'],'text':data['text'],'tts_text':data['text'],'raw':str(folder/'raw.wav'),'playback':str(folder/'speech.wav'),'seconds':len(y)/24000,
                'confirmation_hmm':{'policy':'calm-complete-hum313-v1','applied':any(p['confirmation_hmm']['applied'] for p in parts),'parts':[p['confirmation_hmm'] for p in parts]}}
        import psutil
        processes={}
        for name,worker in [('voice_worker',self.gpt)]:
            info=psutil.Process(worker.ready['pid']).memory_info()
            processes[name]={'pid':worker.ready['pid'],'RSS_MiB':info.rss/1024**2,'private_MiB':info.private/1024**2}
        result.update(generation_seconds=time.monotonic()-start,parts=timings,serial_mode=False,memory={'total_GPU_MiB':None,'processes':processes},workers=self.ready)
        write(folder/'manifest.json',{'samples':[result],'human_quality_verified':False});return result,cold
    def critic(self,folder):return self.cv3.call({'op':'critic','folder':str(folder)})
    def stop(self):
        try:
            if self.cv3:self.cv3.stop()
            if self.gpt:self.gpt.stop()
        finally:
            self.cv3=None;self.gpt=None;self.p=None;self.ready=None
            if self.lease:
                lease=self.lease;self.lease=None;lease.__exit__(None,None,None)
