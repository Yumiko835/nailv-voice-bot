"""Controlled diagnosis. Never changes weights, dataset, references or deployment."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from common import *
import contextlib,types,gc,collections,inspect
import numpy as np,soundfile as sf,yaml
from nailv_audio_export import prepare_reference,float_audio_postprocess,export_native
O=T/'inference-diagnosis-20261025';O.mkdir(exist_ok=True)
torch=runtime()
from nailv_connected_frontend import install
install()
import GPT_SoVITS.TTS_infer_pack.TTS as engine
from low_peak_loading import install as low_peak
low_peak(engine);engine.now_dir=str(M.parent.parent)
sel=read(T/'selected-models.json');bank=read(T/'prompts/manifest.json')
write(O/'user-feedback.json',{'text':'Strong electronic/metallic sound; repeated mama and endings are drawn out/almost sung; some sentences too slow.','failed_text':'妈妈妈妈，这么喜欢叫妈妈吗','listening_sha256':sha(T/'listening.json'),'models':sel,'human_accepted':False})
cfg=O/'config.yaml';cfg.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':sel['gpt']['path'],'vits_weights_path':sel['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (O/'load.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):tts=engine.TTS(engine.TTS_Config(str(cfg)))
tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts)
original_decode=tts.vits_model.decode
captures=[]
def cpu(v):
 if isinstance(v,torch.Tensor):return v.detach().cpu().clone()
 if isinstance(v,list):return [cpu(z) for z in v]
 return v
def capture(*args,**kwargs):
 captures.append({'args':cpu(list(args)),'kwargs':{k:cpu(v) for k,v in kwargs.items()},'cuda_rng':torch.cuda.get_rng_state().cpu()})
 return original_decode(*args,**kwargs)
tts.vits_model.decode=capture
rows=[('mama-rp110','妈妈妈妈，这么喜欢叫妈妈吗','daily',1.1),('mama-rp135','妈妈妈妈，这么喜欢叫妈妈吗','daily',1.35),('gentle-rp135','嗯，别着急，我先听你把话说完。','gentle',1.35)]
results=[]
for name,text,style,rp in rows:
 out=O/name;out.mkdir(exist_ok=True);prompt=bank['prompts'][style];prepare_reference(prompt['path'],out/'reference.wav',gate_plan=prompt['micro_gate_plan']);tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None;captures.clear()
 settings={'text':text,'text_lang':'zh','prompt_text':prompt['text'],'prompt_lang':'zh','ref_audio_path':str(out/'reference.wav'),'top_k':5,'top_p':.9,'temperature':.85,'repetition_penalty':rp,'seed':42,'speed_factor':1.,'text_split_method':'cut0','parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'super_sampling':False}
 with (out/'inference.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):parts=list(tts.run(settings))
 assert len(captures)==1
 y=np.concatenate([x for _,x in parts]);meta=export_native(y,out);cap=captures[0];cap.update(text=text,style=style,reference_id=prompt['id']);save_tensor(cap,out/'decode-inputs.pt');codes=cap['args'][0].flatten().tolist();runs=[]
 for k,group in __import__('itertools').groupby(codes):runs.append((k,len(list(group))))
 item={'id':name,'text':text,'style':style,'rp':rp,'semantic_tokens':len(codes),'semantic_unique':len(set(codes)),'maximum_identical_run':max(n for _,n in runs),'long_runs':[(k,n) for k,n in runs if n>=5],**meta};results.append(item);write(O/'generation.json',results);print(json.dumps({'id':name,'seconds':meta['seconds'],'tokens':len(codes),'max_repeat':item['maximum_identical_run']},ensure_ascii=False),flush=True)
tts.vits_model.decode=original_decode
# Hold semantic tokens, text, reference features and random seed constant. Only
# change acoustic checkpoint or numerical precision. Do not sample GPT again.
from process_ckpt import load_sovits_new
decoder_results=[]
def to_device(v,dtype):
 if isinstance(v,torch.Tensor):return v.cuda().to(dtype=dtype if v.is_floating_point() else v.dtype)
 if isinstance(v,list):return [to_device(z,dtype) for z in v]
 return v
checkpoints=[('official',M/'v2Pro/s2Gv2ProPlus.pth'),('e2',T/'checkpoints/sovits/milkgreen-proplus-e2.pth'),('e6',T/'checkpoints/sovits/milkgreen-proplus-e6.pth'),('e10',Path(sel['sovits']['path']))]
for label,path in checkpoints:
 state=load_sovits_new(str(path));match=tts.vits_model.load_state_dict(state['weight'],strict=False);assert not match.unexpected_keys;del state;gc.collect()
 for precision in (['fp16','fp32'] if label in ['official','e10'] else ['fp32']):
  dtype=torch.float16 if precision=='fp16' else torch.float32;tts.vits_model.to(dtype=dtype)
  for name in ['mama-rp135','gentle-rp135']:
   cap=torch.load(O/name/'decode-inputs.pt',map_location='cpu',weights_only=False);args=to_device(cap['args'],dtype);kwargs={k:to_device(v,dtype) for k,v in cap['kwargs'].items()};torch.manual_seed(777);torch.cuda.manual_seed_all(777)
   with torch.inference_mode():y=original_decode(*args,**kwargs).detach().float().cpu().numpy()[0,0]
   out=O/'fixed-semantic'/(name+'-'+label+'-'+precision);out.mkdir(parents=True,exist_ok=True);item={'id':name+'-'+label+'-'+precision,'text':cap['text'],'style':cap['style'],'acoustic_model':label,'acoustic_sha256':sha(path),'precision':precision,'semantic_source':name,'random_seed':777,'noise_scale':.5,**export_native(y,out)};decoder_results.append(item);write(O/'decoder-matrix.json',decoder_results);print(json.dumps({'decoded':item['id'],'seconds':item['seconds'],'peak':item['native_peak']},ensure_ascii=False),flush=True)
verify_protected();write(O/'diagnosis-inputs-complete.json',{'generation':len(results),'fixed_semantic_decodes':len(decoder_results),'weights_unchanged':True,'human_sound_quality_verified':False})
