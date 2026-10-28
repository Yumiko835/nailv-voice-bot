"""Resident GPT6/SoVITS14 + CV3 Flow/HiFT-only worker. JSONL stdio, local files."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import sys,os,json,time,gc,contextlib,copy,itertools,re
from pathlib import Path
ROOT=Path(project_path(''))
G=ROOT/'voice/training/v2proplus-newsource-20261025'
R2=ROOT/'runtime/cosyvoice2';R3=ROOT/'runtime/cosyvoice3'
OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge'
OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(G/'scripts'),str(R2/'scripts')]
import common as gp
import cosy_chat_backend as coordination
def emit(data):
    sys.__stdout__.write(json.dumps(data,ensure_ascii=False,allow_nan=False)+'\n');sys.__stdout__.flush()
def write(p,d):gp.write(p,d)
def memory():
    import torch,subprocess
    return {'torch_MiB':torch.cuda.memory_allocated()/1024**2,'torch_peak_MiB':torch.cuda.max_memory_allocated()/1024**2,
        'total_GPU_MiB':int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).splitlines()[0])}

class Engine:
    def __init__(self):
        started=time.monotonic();self.bank=gp.read(G/'cross-engine-20261026/reference-manifest.json')['prompts']
        self.cbank=gp.read(ROOT/'voice/comparison/cosyvoice3-20261026/prompts/manifest.json')['prompts']
        # Reuse the exact tested source initialization/FP32 decode wrapper.
        source=(G/'scripts/synthesize.py').read_text(encoding='utf-8')
        prefix=source.split("for row in read(a.requests)['samples']:")[0]
        assert len(prefix)<len(source)
        lines=prefix.splitlines()
        parser=next(i for i,line in enumerate(lines) if line.startswith('p=argparse.ArgumentParser()'))
        loadout=OUT/'load/gpt';loadout.mkdir(parents=True,exist_ok=True)
        lines[parser]='a=__import__("types").SimpleNamespace(out=Path('+repr(str(loadout))+'),reference_manifest=Path('+repr(str(G/'cross-engine-20261026/reference-manifest.json'))+'))'
        self.ns={};exec(compile('\n'.join(lines),'tested-GPT-initialization','exec'),self.ns)
        self.tts=self.ns['tts'];self.torch=self.ns['torch']
        free,total=self.torch.cuda.mem_get_info();self.torch.cuda.set_per_process_memory_fraction(min(4.3*1024**3,free+self.torch.cuda.memory_reserved()-500*1024**2)/total)
        self.torch.cuda.reset_peak_memory_stats()
        self.gcache={};self.refs={};self.pcache={}
        sys.path[:0]=[str(R3/'packages'),str(R2/'src'),str(R2/'src/third_party/Matcha-TTS'),str(ROOT/'tools')]
        os.environ.pop('onnx_path',None)
        import torch,yaml,numpy as np,onnxruntime
        from hyperpyyaml import load_hyperpyyaml
        from cosyvoice.cli.model import CosyVoice3Model
        from cosyvoice.cli.frontend import CosyVoiceFrontEnd
        base=R3/'models/Fun-CosyVoice3-0.5B-2512';self.base=base
        node=yaml.compose((base/'cosyvoice3.yaml').read_text(encoding='utf-8'))
        keep={'flow','hift','feat_extractor','sample_rate','spk_embed_dim','token_frame_rate','token_mel_ratio','chunk_size','num_decoding_left_chunks'}
        node.value=[(k,v) for k,v in node.value if k.value in keep]
        conf=load_hyperpyyaml(yaml.serialize(node));assert conf['sample_rate']==24000
        for name in ['flow','hift']:
            module=conf[name];module.half() if name=='flow' else module.float()
            state=torch.load(base/(name+'.pt'),map_location='cpu',mmap=True,weights_only=True)
            if name=='hift':state={k.replace('generator.',''):v for k,v in state.items()}
            module.load_state_dict(state,strict=True);del state;module.to('cuda').eval();gc.collect();torch.cuda.empty_cache()
        self.cv=CosyVoice3Model(torch.nn.Identity(),conf['flow'],conf['hift'],fp16=True)
        # Native frontend audio methods need no text tokenizer/normalizer/LLM.
        self.front=CosyVoiceFrontEnd.__new__(CosyVoiceFrontEnd);self.front.device=torch.device('cpu');self.front.feat_extractor=conf['feat_extractor']
        options=onnxruntime.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        self.front.campplus_session=onnxruntime.InferenceSession(str(base/'campplus.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.front.speech_tokenizer_session=onnxruntime.InferenceSession(str(base/'speech_tokenizer_v3.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.load_seconds=time.monotonic()-started
        self.receipt={'load_seconds':self.load_seconds,'GPT':self.ns['selected'],'CV3_modules':['official Flow','official HiFT'],
            'CV3_LLM_loaded':False,'CV3_text_tokenizer_loaded':False,'fp16_flow':True,'HiFT_float32':True,
            'speaker_and_speech_tokenizer_CPU':True,'memory':memory()}
        write(OUT/'load/receipt.json',self.receipt)

    def generate(self,request):
        import torch,numpy as np,soundfile as sf
        sys.path.insert(0,str(ROOT/'tools'));import nailv_cosy_delivery as delivery
        folder=Path(request['folder']).resolve();assert folder.is_relative_to((OUT/'runs').resolve())
        folder.mkdir(parents=True,exist_ok=False)
        text=request['text'];assert isinstance(text,str) and 1<=len(text)<=600
        style=request['style'];assert style in self.bank and style in self.cbank
        chunks=delivery.chunks(text,'thought',limit=64);assert ''.join(chunks)==text
        started=time.monotonic();parts=[];source_parts=[];timings=[]
        prepare=self.ns['prepare_reference'];export=self.ns['export_native']
        prompt=self.bank[style];cprompt=self.cbank[style]
        assert gp.sha(prompt['path'])==prompt['sha256'] and gp.sha(cprompt['path'])==cprompt['sha256']
        if style not in self.refs:
            prepared=OUT/'reference-cache'/(style+'.wav');prepared.parent.mkdir(exist_ok=True)
            prepare(prompt['path'],prepared,gate_plan=prompt['micro_gate_plan']);self.refs[style]=str(prepared)
        if style in self.gcache:self.tts.prompt_cache=copy.copy(self.gcache[style])
        reference_started=time.monotonic()
        if style not in self.pcache:
            with torch.inference_mode():
                token,length=self.front._extract_speech_token(cprompt['path']);feat,featlen=self.front._extract_speech_feat(cprompt['path']);embedding=self.front._extract_spk_embedding(cprompt['path'])
            self.pcache[style]={'flow_prompt_speech_token':token,'flow_prompt_speech_token_len':length,'prompt_speech_feat':feat,'prompt_speech_feat_len':featlen,'flow_embedding':embedding}
        reference_seconds=time.monotonic()-reference_started
        for i,chunk in enumerate(chunks):
            sub=folder/f'part-{i+1:02d}';sub.mkdir();before=time.monotonic();seed=(request['seed']+i)%2**32
            settings={'text_lang':'zh','prompt_lang':'zh','top_k':5,'top_p':.9,'temperature':.85,'speed_factor':1.,'text_split_method':'cut0','seed':seed,'parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'repetition_penalty':1.35,'super_sampling':False}
            attempts=[]
            for attempt in range(3):
                settings['seed']=(seed+[0,95,104729][attempt])%2**32;self.ns['decode_events'].clear()
                with torch.inference_mode():out=list(self.tts.run(settings|{'text':chunk,'ref_audio_path':self.refs[style],'prompt_text':prompt['text']}))
                assert out and all(sr==32000 for sr,y in out)
                y=np.concatenate([v for sr,v in out]).astype(np.float32);assert np.isfinite(y).all()
                run=max((e['maximum_identical_token_run'] for e in self.ns['decode_events']),default=0)
                attempts.append({'seed':settings['seed'],'seconds':len(y)/32000,'max_identical_token_run':run})
                if len(y)>32000*.3 and len(y)<=32000*29 and run<16:break
                sf.write(sub/f'source-attempt-{attempt+1}.wav',y,32000,subtype='PCM_24')
            else:raise RuntimeError('本句出现异常长音或长度，原始尝试已保留；文字回复仍可阅读。')
            (sub/'source').mkdir()
            source=export(y,sub/'source');self.gcache[style]=copy.copy(self.tts.prompt_cache)
            source_parts.append(y);gpt_seconds=time.monotonic()-before;before=time.monotonic()
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            with torch.inference_mode():
                token,length=self.front._extract_speech_token(source['raw'])
                inputs=self.pcache[style]|{'source_speech_token':token,'source_speech_token_len':length}
                rendered=[v['tts_speech'].detach().float().cpu().numpy().flatten().copy() for v in self.cv.tts(**inputs,stream=False,speed=1.)]
            z=np.concatenate(rendered);assert np.isfinite(z).all() and len(z)>1200
            sf.write(sub/'cv3-native-float.wav',z,24000,subtype='FLOAT');parts.append(z)
            timings.append({'text':chunk,'GPT_seconds':gpt_seconds,'CV3_seconds':time.monotonic()-before,'attempts':attempts,'audio_seconds':len(z)/24000})
            gc.collect();torch.cuda.empty_cache()
        y=np.concatenate([np.r_[v,np.zeros(2880,np.float32)] if i<len(parts)-1 else v for i,v in enumerate(parts)])
        peak=float(abs(y).max());raw=folder/'raw.wav';sf.write(raw,y*min(1.,.999/max(peak,1e-9)),24000,subtype='PCM_24')
        gain=min(1.,.1/max(float(np.sqrt(np.mean(y*y))),1e-9),.89/max(peak,1e-9));playback=folder/'speech.wav'
        sf.write(playback,np.r_[np.zeros(3840,np.float32),y*gain,np.zeros(7680,np.float32)],24000,subtype='PCM_24')
        control=np.concatenate([np.r_[v,np.zeros(3840,np.float32)] if i<len(source_parts)-1 else v for i,v in enumerate(source_parts)])
        cgain=min(1.,.1/max(float(np.sqrt(np.mean(control*control))),1e-9),.89/max(float(abs(control).max()),1e-9))
        sf.write(folder/'source-control.wav',np.r_[np.zeros(5120,np.float32),control*cgain,np.zeros(10240,np.float32)],32000,subtype='PCM_24')
        row={'id':request['id'],'text':text,'tts_text':text,'style':style,'raw':str(raw),'playback':str(playback),
             'seconds':len(y)/24000,'generation_seconds':time.monotonic()-started,'reference':cprompt,'seed':request['seed'],
             'parts':timings,'reference_prepare_seconds':reference_seconds,'memory':memory(),
             'source_GPT_epoch':6,'source_SoVITS_epoch':14,'CV3_LLM_loaded':False,
             'inference':'GPT native waveform -> native CV3 tokenizer -> original Flow/HiFT',
             'no_acting_tags_requested':True,'postprocessing':'Attenuation/padding only, .12s gap only between bounded long-response chunks.'}
        write(folder/'manifest.json',{'samples':[row],'human_quality_verified':False})
        return row

try:
    with coordination.gpu_lease('GPT-CV3-resident-trial'),(OUT/'worker.log').open('a',encoding='utf-8') as log:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):engine=Engine()
        emit({'event':'ready','receipt':engine.receipt})
        for line in sys.stdin:
            request=json.loads(line)
            if request.get('op')=='quit':emit({'event':'stopped'});break
            try:
                with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):result=engine.generate(request)
                emit({'event':'result','result':result})
            except Exception as exc:
                import traceback;traceback.print_exc(file=log);log.flush();emit({'event':'error','error':str(exc)[:240]})
except Exception as exc:
    import traceback
    with (OUT/'worker-failure.log').open('a',encoding='utf-8') as log:traceback.print_exc(file=log)
    emit({'event':'error','error':str(exc)[:240]});sys.exit(1)
