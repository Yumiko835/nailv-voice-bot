
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
import os,sys,json,time,hashlib,subprocess,re,gc,contextlib,threading,argparse,uuid
ROOT=Path(project_path(''));R=ROOT/'runtime/cosyvoice2';O=ROOT/'voice/comparison/cosyvoice2-20261026'
for key,folder in {'HF_HOME':'hf','TORCH_HOME':'torch','NUMBA_CACHE_DIR':'numba','MPLCONFIGDIR':'matplotlib','MODELSCOPE_CACHE':'modelscope','TEMP':'tmp','TMP':'tmp'}.items():
    p=R/'cache'/folder;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONUTF8='1')
sys.path[:0]=[str(R/'src'),str(R/'src/third_party/Matcha-TTS')]
sys.path.insert(0,str(ROOT/'tools'))
import nailv_cosy_performance as performance
import nailv_cosy_delivery as delivery
p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,default=O/'active-requests.json');p.add_argument('--out',type=Path,default=O/'live-runs'/('run-'+uuid.uuid4().hex[:12]));p.add_argument('--limit',type=int);a=p.parse_args()
if not a.out.resolve().is_relative_to(O.resolve()):raise ValueError('语音输出必须留在本项目E盘试听目录。')
a.out.mkdir(parents=True,exist_ok=True)
if (a.out/'manifest.json').exists():raise RuntimeError('此输出目录已有试听，请用 --out 指定一个新的E盘输出目录，保留旧样本。')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def gpu_used():
    return int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),text=True).splitlines()[0].strip())
bank=performance.active_bank()
rows=read(a.requests)['samples'];rows=rows[:a.limit] if a.limit else rows
for row in rows:
    if row.get('mode')!='zero_shot' or row['style'] not in bank:raise ValueError('当前仅启用原味参考zero_shot；温柔低语及instruct2已停用。')
    planned=performance.parse_reply(row.get('tts_text',row['text']),force_emotion=row['style'],bank=bank)
    performance.validate_reference(planned['tts_payload'],bank)
    if row.get('spoken_text') and row['spoken_text']!=planned['clean_text']:raise ValueError('标签处理改变了应读正文。')
    row['text']=planned['clean_text'];row['tts_text']=planned['tts_payload']['tts_text'];row['performance_events']=planned['tts_payload']['events']
import torch,numpy as np,soundfile as sf
assert torch.cuda.is_available(),'CosyVoice2 must use CUDA, not CPU fallback'
torch.set_num_threads(2);torch.cuda.init()
free,total=torch.cuda.mem_get_info();limit=min(4*1024**3,free-512*1024**2)
assert limit>=2*1024**3,'Insufficient free VRAM; no other applications are terminated'
torch.cuda.set_per_process_memory_fraction(limit/total)
telemetry={'baseline_total_gpu_used_MiB':gpu_used(),'allocator_limit_MiB':limit/1024**2,'total_MiB':total/1024**2,'observed_total_gpu_used_MiB':[]}
stop=threading.Event()
def monitor():
    while not stop.is_set():
        try:telemetry['observed_total_gpu_used_MiB'].append({'seconds':time.monotonic(),'used':gpu_used()})
        except Exception:pass
        stop.wait(.5)
thread=threading.Thread(target=monitor,daemon=True);thread.start()
torch.cuda.reset_peak_memory_stats()
from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.cli.model import CosyVoice2Model
import cosyvoice.cli.cosyvoice as cosy_cli
import yaml
# The distributed YAML also instantiates training-only discriminators/data
# processors. Keep the identical three inference networks and frontend while
# omitting those unused objects; retain the original downloaded YAML untouched.
original_hyperyaml=cosy_cli.load_hyperpyyaml
def inference_hyperyaml(stream,*args,**kwargs):
    node=yaml.compose(stream)
    names={'sample_rate','llm_input_size','llm_output_size','spk_embed_dim','qwen_pretrain_path',
        'token_frame_rate','token_mel_ratio','chunk_size','num_decoding_left_chunks',
        'llm','flow','hift','get_tokenizer','feat_extractor','allowed_special'}
    node.value=[(k,v) for k,v in node.value if k.value in names or k.value.startswith('__set_seed')]
    text=yaml.serialize(node)
    (a.out/'inference-only-derived.yaml').write_text(text,encoding='utf-8')
    return original_hyperyaml(text,*args,**kwargs)
cosy_cli.load_hyperpyyaml=inference_hyperyaml
load_receipt=[]
def low_peak_load(self,llm_model,flow_model,hift_model):
    for name,file in [('llm',llm_model),('flow',flow_model),('hift',hift_model)]:
        module=getattr(self,name)
        # Large LLM and flow weights stay half; official HiFT path operates
        # outside flow autocast, so preserve its small full-precision module.
        module.half() if name!='hift' else module.float()
        state=torch.load(file,map_location='cpu',weights_only=True,mmap=True)
        if name=='hift':state={k.replace('generator.',''):v for k,v in state.items()}
        module.load_state_dict(state,strict=True);del state;gc.collect()
        module.to(self.device).eval();torch.cuda.empty_cache()
        load_receipt.append({'module':name,'dtype':str(next(module.parameters()).dtype),'device':str(next(module.parameters()).device),'parameter_count':sum(v.numel() for v in module.parameters()),'checkpoint_loaded_on':'CPU','strict_keys':True})
CosyVoice2Model.load=low_peak_load
started=time.monotonic();model=None
try:
    with (a.out/'model-load.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        model=CosyVoice2(str(R/'models/CosyVoice2-0.5B'),fp16=True,load_jit=False,load_trt=False,load_vllm=False)
    assert model.fp16 and model.model.fp16 and model.sample_rate==24000
    assert not hasattr(model.model.llm,'vllm')
    assert all(v['device']=='cuda:0' for v in load_receipt)
    token_ids={token:model.frontend.tokenizer.encode(token) for token in performance.ALLOWED_TOKENS}
    assert all(len(ids)==1 for ids in token_ids.values()),'Unsupported control token; stop before synthesizing literal tags'
    write(a.out/'control-token-verification.json',{'registered_token_ids':token_ids,'perceptual_effect_verified':False})
    # Keep the full-precision HiFT interface intact even when flow parameters
    # are half; do not alter its weights or use a custom denoising stage.
    hift_inference=model.model.hift.inference
    def float_hift(*args,**kwargs):
        args=[v.float() if isinstance(v,torch.Tensor) and v.is_floating_point() else v for v in args]
        kwargs={k:v.float() if isinstance(v,torch.Tensor) and v.is_floating_point() else v for k,v in kwargs.items()}
        return hift_inference(*args,**kwargs)
    model.model.hift.inference=float_hift
    write(a.out/'load-receipt.json',{'initialization':{'fp16':True,'load_jit':False,'load_trt':False,'load_vllm':False},'modules':load_receipt,
        'native_sample_rate':model.sample_rate,'speaker_frontend_providers':model.frontend.campplus_session.get_providers(),
        'speech_tokenizer_providers':model.frontend.speech_tokenizer_session.get_providers(),'load_seconds':time.monotonic()-started})
    print(json.dumps({'loaded':True,'seconds':time.monotonic()-started,'allocated_MiB':torch.cuda.memory_allocated()/1024**2,'modules':load_receipt}),flush=True)
    result={'version':'cosyvoice2-thought-groups-v3','model':'FunAudioLLM/CosyVoice2-0.5B','model_revision':read(R/'required-model-files.json')['revision'],
        'source_code':read(O/'source-code.json'),'no_training':True,'no_post_synthesis_denoising':True,'samples':[],'human_quality_verified':False}
    compiled=set();active_variant='base'
    variant_config=read(O/'model-variants.json') if (O/'model-variants.json').is_file() else {'variants':{},'default_variant':'base'}
    variants=variant_config['variants']
    result['model_variants']=variants
    for row in rows:
        variant=row.get('model_variant') or variant_config.get('default_variant','base')
        row['model_variant']=variant
        if variant!=active_variant:
            if variant not in variants:raise ValueError('专属模型版本不存在。')
            checkpoint=Path(variants[variant]['checkpoint']).resolve()
            permitted=[ROOT/'voice/training/cosyvoice2-lora-20261026/checkpoints',ROOT/'voice/training/cosyvoice2-curated-v2-20261026/checkpoints']
            if variant!='base' and not any(checkpoint.is_relative_to(p.resolve()) for p in permitted):raise ValueError('模型不在本项目训练输出目录中。')
            if sha(checkpoint)!=variants[variant]['sha256']:raise ValueError('模型文件校验不匹配。')
            state=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
            model.model.llm.load_state_dict(state,strict=True);del state;model.model.llm.eval()
            gc.collect();torch.cuda.empty_cache();active_variant=variant
        prompt=bank[row['style']];assert sha(prompt['path'])==prompt['sha256']
        key='milkgreen-'+row['style']
        if row['mode']=='zero_shot' and key not in compiled:
            with (a.out/'reference-load.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),torch.inference_mode():
                cached=model.frontend.frontend_zero_shot('',prompt['text'],prompt['path'],model.sample_rate,'')
            cached.pop('text');cached.pop('text_len');model.frontend.spk2info[key]=cached;compiled.add(key)
            gc.collect();torch.cuda.empty_cache()
        # Preserve local reaction/continuation context. Long utterances remain
        # bounded; never add or remove words to manufacture colloquial speech.
        chunks=delivery.chunks(row['tts_text'],row.get('chunk_mode','legacy'))
        assert ''.join(chunks)==row['tts_text'] and all(len(performance.strip_markup(c))<=80 for c in chunks)
        folder=a.out/row['id'];folder.mkdir(parents=True,exist_ok=True);parts=[];measurements=[]
        for index,text in enumerate(chunks):
            torch.manual_seed(row['seed']+index);torch.cuda.manual_seed_all(row['seed']+index)
            before=time.monotonic()
            with (folder/'inference.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),torch.inference_mode():
                generator=model.inference_zero_shot(text,prompt['text'],prompt['path'],zero_shot_spk_id=key,stream=False,text_frontend=False)
                utterances=[]
                for output in generator:
                    utterances.append(output['tts_speech'].detach().float().cpu().numpy().flatten().copy());del output
                del generator
            assert utterances,'No speech generated'
            y=np.concatenate(utterances);assert np.isfinite(y).all() and len(y)>1200
            sf.write(folder/f'part-{index+1:02d}-native.wav',y,24000,subtype='FLOAT');parts.append(y)
            del utterances;gc.collect();torch.cuda.empty_cache();torch.cuda.synchronize()
            measurements.append({'text':text,'seconds':len(y)/24000,'generation_seconds':time.monotonic()-before,'allocated_MiB_after_cache_clear':torch.cuda.memory_allocated()/1024**2,'reserved_MiB_after_cache_clear':torch.cuda.memory_reserved()/1024**2})
            if torch.cuda.mem_get_info()[0]<256*1024**2:raise RuntimeError('VRAM headroom below256MiB; stopping own inference safely')
        gap=float(row.get('fragment_interval',.18));assert 0<=gap<=.3
        y=np.concatenate([part if i==len(parts)-1 else np.r_[part,np.zeros(round(gap*24000),np.float32)] for i,part in enumerate(parts)])
        sf.write(folder/'native-float.wav',y,24000,subtype='FLOAT')
        peak=float(np.abs(y).max());raw=folder/'raw.wav';sf.write(raw,y*min(1,.999/max(peak,1e-12)),24000,subtype='PCM_24')
        rms=float(np.sqrt(np.mean(y*y)));gain=min(1.,.1/max(rms,1e-12),.89/max(peak,1e-12))
        playback=folder/'speech.wav';sf.write(playback,np.r_[np.zeros(3840,np.float32),y*gain,np.zeros(7680,np.float32)],24000,subtype='PCM_24')
        item=row|{'seconds':len(y)/24000,'reference':prompt,'reference_id':prompt['reference_id'],'sample_rate':24000,'native_output_rate':True,'output_resampling':False,
            'loaded_llm_sha256':variants.get(variant,{}).get('sha256'),
            'raw':str(raw),'raw_sha256':sha(raw),'playback':str(playback),'playback_sha256':sha(playback),'native_float':str(folder/'native-float.wav'),
            'native_peak':peak,'playback_gain_db':float(20*np.log10(gain)),'measurements':measurements,'postprocessing':'Only attenuation and playback buffering; no denoising, EQ, breath filters, tempo or pitch edits.'}
        write(folder/'result.json',item);result['samples'].append(item);write(a.out/'manifest.json',result)
        print(json.dumps({'generated':row['id'],'seconds':item['seconds'],'allocated_MiB':torch.cuda.memory_allocated()/1024**2,'peak_MiB':torch.cuda.max_memory_allocated()/1024**2}),flush=True)
    result['peak_allocated_MiB']=torch.cuda.max_memory_allocated()/1024**2;result['peak_reserved_MiB']=torch.cuda.max_memory_reserved()/1024**2
    write(a.out/'manifest.json',result)
finally:
    stop.set();thread.join(timeout=2)
    telemetry.update(peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,peak_reserved_MiB=torch.cuda.max_memory_reserved()/1024**2,
        observed_total_peak_MiB=max((v['used'] for v in telemetry['observed_total_gpu_used_MiB']),default=telemetry['baseline_total_gpu_used_MiB']))
    write(a.out/'memory-telemetry.json',telemetry)
    if model is not None:del model
    gc.collect();torch.cuda.empty_cache()
