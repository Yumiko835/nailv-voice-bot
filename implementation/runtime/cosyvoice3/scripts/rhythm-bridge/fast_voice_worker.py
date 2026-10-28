"""Native-runtime voice worker. Local file RPC, no text LLM/network calls."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import sys,os,json,time,contextlib,traceback,faulthandler,argparse,gc,copy,re
from pathlib import Path
faulthandler.enable(all_threads=True)
p=argparse.ArgumentParser();p.add_argument('--role',choices=['gpt','cv3','pair'],required=True);p.add_argument('--state',type=Path,required=True);args=p.parse_args()
ROOT=Path(project_path(''));R2=ROOT/'runtime/cosyvoice2';R3=ROOT/'runtime/cosyvoice3'
OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge';G=ROOT/'voice/training/v2proplus-newsource-20261025'
assert args.state.resolve().is_relative_to((OUT/'fast-state').resolve());args.state.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    p=Path(p);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)
def valid_folder(p):
    p=Path(p).resolve();assert p.is_relative_to((OUT/'runs').resolve());p.mkdir(parents=True,exist_ok=True);return p
class GPT:
    def __init__(self):
        sys.path[:0]=[str(G/'scripts'),str(R2/'scripts')]
        import common as gp
        self.gp=gp
        source=(G/'scripts/synthesize.py').read_text(encoding='utf-8');prefix=source.split("for row in read(a.requests)['samples']:")[0];assert len(prefix)<len(source)
        lines=prefix.splitlines();n=next(i for i,l in enumerate(lines) if l.startswith('p=argparse.ArgumentParser()'))
        folder=args.state/'load';folder.mkdir(exist_ok=True)
        lines[n]='a=__import__("types").SimpleNamespace(out=Path('+repr(str(folder))+'),reference_manifest=Path('+repr(str(G/'cross-engine-20261026/reference-manifest.json'))+'))'
        ns={'__file__':str(G/'scripts/synthesize.py')};exec(compile('\n'.join(lines),'original-tested-GPT-init','exec'),ns);self.ns=ns;self.tts=ns['tts'];self.torch=ns['torch']
        self.torch.cuda.set_per_process_memory_fraction(.8 if args.role=='pair' else .52);self.torch.cuda.reset_peak_memory_stats()
        self.bank=gp.read(G/'cross-engine-20261026/reference-manifest.json')['prompts'];self.cache={};self.prepared={}
        import psutil
        self.receipt={'sampling_default':{'repetition_penalty':1.2,'temperature':.85,'top_k':5,'top_p':.9},'semantic_repeat_retry_at':24,'confirmation_duration_editing':'conditional complete terminal hum313ms / no text or reference rewrite','GPT_epoch':6,'SoVITS_epoch':14,'protected_selection':ns['selected'],'acoustic_FP32':True,'modules_loaded':'GPT-SoVITS only','host_private_MiB':psutil.Process().memory_info().private/1024**2,'RSS_MiB':psutil.Process().memory_info().rss/1024**2}
    def run(self,row):
        import numpy as np,soundfile as sf
        folder=valid_folder(row['folder']);target=folder/'gpt';target.mkdir(exist_ok=False)
        from pause_guard import inspect as inspect_pause,repair as repair_pause
        text=row['text'];assert 0<len(text)<=80;style=row['style'];prompt=self.bank[style]
        profile=row.get('reference_profile')
        if profile:
            if profile!='pet_loss':raise ValueError('Unknown reference profile')
            # No clean, human-verified sad reference yet. Use the accepted
            # restrained reference, never the accusatory sigh recording.
            prompt=self.bank['serious']
        cache_key=profile or style
        assert self.gp.sha(prompt['path'])==prompt['sha256']
        if cache_key not in self.prepared:
            ref=args.state/(cache_key+'-prepared.wav');self.ns['prepare_reference'](prompt['path'],ref,gate_plan=prompt['micro_gate_plan']);self.prepared[cache_key]=str(ref)
        if cache_key in self.cache:self.tts.prompt_cache=copy.deepcopy(self.cache[cache_key])
        settings={'text_lang':'zh','prompt_lang':'zh','top_k':5,'top_p':.9,'temperature':.85,'speed_factor':1.,'text_split_method':'cut0','seed':row['seed'],'parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'repetition_penalty':1.2,'super_sampling':False}
        if row.get('sampling')=='expressive':settings.update(top_k=20,top_p=.95,temperature=1.)
        begin=time.monotonic();attempts=[];candidates=[]
        for attempt in range(3):
            settings['seed']=(row['seed']+[0,95,104729][attempt])%2**32;self.ns['decode_events'].clear()
            with self.torch.inference_mode():out=list(self.tts.run(settings|{'text':text,'ref_audio_path':self.prepared[cache_key],'prompt_text':prompt['text']}))
            assert out and all(sr==32000 for sr,y in out)
            y=np.concatenate([v for sr,v in out]).astype(np.float32);assert np.isfinite(y).all()
            run=max((x['maximum_identical_token_run'] for x in self.ns['decode_events']),default=0)
            pause=inspect_pause(y,32000,text,profile)
            valid=.3<len(y)/32000<=29 and (row.get('preserve_stress_attempt',False) or run<24)
            attempts.append({'seed':settings['seed'],'seconds':len(y)/32000,'max_token_run':run,'interior_pause':pause})
            if valid and not pause['retry_recommended']:break
            sf.write(target/f'failed-{attempt}.wav',y,32000,subtype='PCM_24')
            if valid:candidates.append((sum(r['seconds'] for r in pause['regions'] if not r['safe_to_shorten']),y.copy(),settings.copy(),self.ns['decode_events'].copy()))
        else:
            if not candidates:raise RuntimeError('源语音出现异常长音或时长，已保留尝试与文字。')
            # All attempts contain ambiguous weak voice: retain the least affected
            # attempt rather than deleting potentially meaningful quiet words.
            _,y,chosen,events=min(candidates,key=lambda item:item[0]);settings.update(chosen)
            self.ns['decode_events'][:]=events
        sf.write(target/'before-pause-guard.wav',y,32000,subtype='PCM_24')
        y,pause_receipt=repair_pause(y,32000,text,profile)
        write(target/'pause-guard.json',pause_receipt)
        self.cache[cache_key]=copy.deepcopy(self.tts.prompt_cache);result=self.ns['export_native'](y,target)
        self.torch.cuda.synchronize();result.update(generation_seconds=time.monotonic()-begin,attempts=attempts,settings=settings.copy(),reference=prompt,reference_profile=profile,pause_guard=pause_receipt,stress_repeat_guard_advisory=bool(row.get('preserve_stress_attempt',False)),decode_events=self.ns['decode_events'].copy(),torch_peak_MiB=self.torch.cuda.max_memory_allocated()/1024**2)
        result['semantic_repeat_guard']={'retry_at':24,'advisory_at':16,'maximum_run':run,'policy':'Retry only; never truncate semantic tokens or waveform. Human-approved16-run sample is retained.'}
        write(target/'result.json',result)
        gc.collect();self.torch.cuda.empty_cache();return result
class CV3:
    @contextlib.contextmanager
    def flow_variant(self,name):
        if name not in ('official','personal_half'):raise ValueError('Unrecognized private-study Flow')
        if not hasattr(self,'official_flow_sha'):self.official_flow_sha=self.cv.sha(self.base/'flow.pt')
        receipt={'name':name,'path':str(self.base/'flow.pt'),'sha256':self.official_flow_sha}
        def load(path):
            state=self.torch.load(path,map_location='cpu',mmap=True,weights_only=True)
            self.model.flow.load_state_dict(state,strict=True);del state;gc.collect()
        if name=='personal_half':
            manifest=read(ROOT/'voice/training/cosyvoice3-personal-20261026/flow-rhythm-trial/checkpoints.json')
            item=next(v for v in manifest['models'] if v['fraction']==.5)
            path=Path(item['path']).resolve()
            assert path==(ROOT/'voice/training/cosyvoice3-personal-20261026/flow-rhythm-trial/checkpoints/flow-0.5.pt').resolve()
            assert self.cv.sha(path)==item['sha256']=='d1642be0c5d8004289653abd50099c0aa9ffb0029f12d2d528cba42781dcab91'
            load(path);receipt={'name':name,'path':str(path),'sha256':item['sha256']}
        try:yield receipt
        finally:
            if name=='personal_half':load(self.base/'flow.pt')
    @contextlib.contextmanager
    def guidance(self,rate):
        if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not .5<=rate<=1.1:raise ValueError('Experimental guidance rate outside bounded range')
        old=self.model.flow.decoder.inference_cfg_rate
        try:
            self.model.flow.decoder.inference_cfg_rate=float(rate);yield
        finally:self.model.flow.decoder.inference_cfg_rate=old
    def __init__(self):
        sys.path.insert(0,str(R3/'scripts'))
        import importlib.util
        spec=importlib.util.spec_from_file_location('common',R3/'scripts/common.py');cv=importlib.util.module_from_spec(spec);spec.loader.exec_module(cv);sys.modules['common']=cv
        cv.setup();self.cv=cv
        import torch,yaml,onnxruntime
        from hyperpyyaml import load_hyperpyyaml
        from cosyvoice.cli.model import CosyVoice3Model
        from cosyvoice.cli.frontend import CosyVoiceFrontEnd
        torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.8 if args.role=='pair' else .28);torch.cuda.reset_peak_memory_stats();self.torch=torch
        base=cv.BASE;self.bank=read(cv.O/'prompts/manifest.json')['prompts']
        node=yaml.compose((base/'cosyvoice3.yaml').read_text(encoding='utf-8'))
        keep={'flow','hift','feat_extractor','sample_rate','spk_embed_dim','token_frame_rate','token_mel_ratio','chunk_size','num_decoding_left_chunks'}
        node.value=[(k,v) for k,v in node.value if k.value in keep]
        conf=load_hyperpyyaml(yaml.serialize(node));assert conf['sample_rate']==24000
        for name in ['flow','hift']:
            module=conf[name];module.half() if name=='flow' else module.float()
            state=torch.load(base/(name+'.pt'),map_location='cpu',mmap=True,weights_only=True)
            if name=='hift':state={k.replace('generator.',''):v for k,v in state.items()}
            module.load_state_dict(state,strict=True);del state;module.to('cuda').eval();gc.collect();torch.cuda.empty_cache()
        self.model=CosyVoice3Model(torch.nn.Identity(),conf['flow'],conf['hift'],fp16=True)
        self.front=CosyVoiceFrontEnd.__new__(CosyVoiceFrontEnd);self.front.device=torch.device('cpu');self.front.feat_extractor=conf['feat_extractor']
        options=onnxruntime.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.enable_cpu_mem_arena=False
        options.enable_mem_pattern=False
        options.add_session_config_entry('session.disable_prepacking','1')
        self.options=options;self.base=base;self.ort=onnxruntime
        self.front.campplus_session=onnxruntime.InferenceSession(str(base/'campplus.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.front.speech_tokenizer_session=None
        import psutil
        self.keep_tokenizer=os.getenv('NAILV_KEEP_TOKENIZER','0')=='1'
        self.cache={};self.critic=None;self.receipt={'modules_loaded':['official CV3 Flow','official CV3 HiFT'],'CV3_LLM_loaded':False,'Flow_sha256':cv.sha(base/'flow.pt'),'HiFT_sha256':cv.sha(base/'hift.pt'),'flow_fp16':True,'HiFT_FP32':True,'ONNX_CPU':True,'large_ONNX_released_between_jobs':not self.keep_tokenizer,'host_private_MiB':psutil.Process().memory_info().private/1024**2,'RSS_MiB':psutil.Process().memory_info().rss/1024**2}
    def reference_features(self):
        for name,prompt_ref in self.bank.items():
            if name in self.cache:continue
            assert self.cv.sha(prompt_ref['path'])==prompt_ref['sha256']
            token,n=self.front._extract_speech_token(prompt_ref['path']);feat,flen=self.front._extract_speech_feat(prompt_ref['path']);embedding=self.front._extract_spk_embedding(prompt_ref['path'])
            self.cache[name]={'flow_prompt_speech_token':token,'flow_prompt_speech_token_len':n,'prompt_speech_feat':feat,'prompt_speech_feat_len':flen,'flow_embedding':embedding}
    def warm(self):
        begin=time.monotonic()
        with self.torch.inference_mode():
            self.front.speech_tokenizer_session=self.ort.InferenceSession(str(self.base/'speech_tokenizer_v3.onnx'),sess_options=self.options,providers=['CPUExecutionProvider'])
            self.reference_features()
        if not self.keep_tokenizer:self.front.speech_tokenizer_session=None
        gc.collect();self.receipt['reference_features_cached']=list(self.cache);self.receipt['reference_warm_seconds']=time.monotonic()-begin
    def check(self,row):
        # Reuse this process's torch libraries, but all critic operations use CPU.
        # Avoid a third Python/torch DLL image and FunASR's three weight copies.
        import audio_critic as ac
        if self.critic is None:
            import lean_sensevoice
            lean_sensevoice.install()
            self.critic=ac.Critic()
            self.anchors=[ac.np.asarray(self.critic.file(r['path'],r['text'])['embedding']) for r in self.bank.values()]
            within=[]
            for i,a in enumerate(self.anchors):
                c=ac.np.mean([v for j,v in enumerate(self.anchors) if j!=i],axis=0);c/=ac.np.linalg.norm(c);within.append(float(a@c))
            self.threshold=max(-1.,float(ac.np.percentile(within,5))-.12)
        folder=valid_folder(row['folder']);sample=read(folder/'manifest.json')['samples'][0]
        result=ac.assess(self.critic,sample,self.bank[sample['style']],self.anchors,self.threshold)
        target=folder/'critic';target.mkdir(exist_ok=True)
        write(target/'details.json',{sample['id']:[result]})
        write(target/'calibration.json',{'conservative_threshold':self.threshold,'references':list(self.bank),'not_a_validated_personality_threshold':True})
        write(target/'ranking.json',{'ranking':ac.rank_results({sample['id']:[result]}),'device':'CPU','unvalidated_proxies':True,'weights_unchanged':True})
        write(folder/'critic.json',{'device':'CPU only, reused CV3 process','assessment':result,'flags_advisory':True,'human_quality_verified':False})
        import psutil
        return {'scores':result['scores'],'flags':result['review_flags'],'recognized':result['content']['recognized'],'RSS_MiB':psutil.Process().memory_info().rss/1024**2}
    def run(self,row):
        import numpy as np,soundfile as sf
        folder=valid_folder(row['folder']);prompt=self.bank[row['style']];assert self.cv.sha(prompt['path'])==prompt['sha256']
        source=Path(row['source_audio']).resolve();assert source.is_relative_to(OUT.resolve()) and self.cv.sha(source)==row['source_sha256']
        assert .2<sf.info(source).duration<=30
        begin=time.monotonic();torch=self.torch;torch.manual_seed(row['seed']);torch.cuda.manual_seed_all(row['seed'])
        mode=row.get('conditioning','gold');assert mode=='gold'
        route=row.get('render_path','vc');assert route in ('vc','hift_only')
        flow_name=row.get('flow_variant','official');assert route=='vc' or flow_name=='official'
        cfg=float(row.get('cfg_rate',.7))
        with torch.inference_mode(),self.guidance(cfg),self.flow_variant(flow_name) as flow_receipt:
            if route=='vc' and self.front.speech_tokenizer_session is None:self.front.speech_tokenizer_session=self.ort.InferenceSession(str(self.base/'speech_tokenizer_v3.onnx'),sess_options=self.options,providers=['CPUExecutionProvider'])
            session_loaded=time.monotonic()
            style=row['style']
            if route=='vc':
                self.reference_features()
                token,n=self.front._extract_speech_token(str(source));inputs=self.cache[style]|{'source_speech_token':token,'source_speech_token_len':n}
            else:
                feat,flen=self.front._extract_speech_feat(str(source))
            if not self.keep_tokenizer:self.front.speech_tokenizer_session=None
            gc.collect()
            tokens_done=time.monotonic()
            if route=='vc':out=[v['tts_speech'].detach().float().cpu().numpy().flatten().copy() for v in self.model.tts(**inputs,stream=False,speed=1.)]
            else:
                with torch.autocast('cuda',enabled=self.model.fp16):
                    wave,_=self.model.hift.inference(speech_feat=feat.transpose(1,2).to('cuda').float(),finalize=True)
                out=[wave.detach().float().cpu().numpy().flatten().copy()]
                del feat,wave
        rendered=time.monotonic()
        y=np.concatenate(out);assert np.isfinite(y).all() and len(y)>1200
        pause_receipt=row.get('source_pause_guard',{})
        known=pause_receipt.get('known_silences',[]) if route=='hift_only' else []
        if known:
            from pause_guard import silence_known_intervals
            y=silence_known_intervals(y,24000,known)
        sf.write(folder/'cv3-native-float.wav',y,24000,subtype='FLOAT')
        from confirmation_hmm import apply as confirmation_hmm
        y,hmm_receipt=confirmation_hmm(y,24000,row['text'],row['style'])
        peak=float(abs(y).max())
        raw=folder/'raw.wav';sf.write(raw,y*min(1.,.999/max(peak,1e-9)),24000,subtype='PCM_24')
        gain=min(1.,.1/max(float(np.sqrt(np.mean(y*y))),1e-9),.89/max(peak,1e-9));playback=folder/'speech.wav'
        sf.write(playback,np.r_[np.zeros(3840,np.float32),y*gain,np.zeros(7680,np.float32)],24000,subtype='PCM_24')
        torch.cuda.synchronize();result={'id':row['id'],'text':row['text'],'tts_text':row['text'],'style':row['style'],'seed':row['seed'],
          'raw':str(raw),'playback':str(playback),'reference':prompt,'seconds':len(y)/24000,'sample_rate':24000,
          'generation_seconds':time.monotonic()-begin,'torch_peak_MiB':torch.cuda.max_memory_allocated()/1024**2,
          'source_audio':str(source),'source_sha256':row['source_sha256'],'CV3_LLM_loaded':False,
          'experimental_conditioning':mode,'render_path':route,'flow_variant':flow_receipt,'inference_cfg_rate':cfg,'gold_speaker_embedding_used':route=='vc',
          'native_official_HiFT':True,'Flow_used':route=='vc','confirmation_hmm':hmm_receipt,
          'reference_profile':row.get('reference_profile'),'source_pause_guard':pause_receipt,
          'postprocessing':'Conservative interior-gap guard; conditional human-accepted complete313ms terminal hum only. Original punctuation/reference preserved; no EQ, denoise, word timestamps or added pause.'}
        import psutil
        result['host_private_MiB']=psutil.Process().memory_info().private/1024**2
        result['RSS_MiB']=psutil.Process().memory_info().rss/1024**2
        result['reference_features_cached']=list(self.cache)
        result['profile_seconds']={'tokenizer_session_load':session_loaded-begin,'tokenize_and_reference_features':tokens_done-session_loaded,'Flow_HiFT':rendered-tokens_done,'export':time.monotonic()-rendered}
        write(folder/'manifest.json',{'samples':[result],'human_quality_verified':False});gc.collect();torch.cuda.empty_cache();return result
def main():
    before=time.monotonic()
    if args.role=='pair':
        gpt=GPT();engine=CV3();engine.warm();engine.receipt={'GPT':gpt.receipt,'CV3':engine.receipt,'same_torch_runtime':True}
    else:engine=GPT() if args.role=='gpt' else CV3()
    write(args.state/'ready.json',{'pid':os.getpid(),'role':args.role,'load_seconds':time.monotonic()-before,'receipt':engine.receipt})
    while True:
        requests=sorted(args.state.glob('*.request.json'),key=lambda p:p.name)
        for path in requests:
            reply=path.with_name(path.name.replace('.request.json','.reply.json'))
            if reply.exists():continue
            row=read(path)
            if row.get('op')=='quit':write(reply,{'stopped':True});return
            try:
                result=engine.check(row) if row.get('op')=='critic' else gpt.run(row) if args.role=='pair' and row.get('op')=='gpt' else engine.run(row)
                write(reply,{'result':result})
            except Exception as exc:traceback.print_exc();write(reply,{'error':str(exc)[:300]})
        time.sleep(.05)
if __name__=='__main__':
    try:main()
    except Exception as exc:traceback.print_exc();write(args.state/'failed.json',{'error':str(exc),'pid':os.getpid()});raise
