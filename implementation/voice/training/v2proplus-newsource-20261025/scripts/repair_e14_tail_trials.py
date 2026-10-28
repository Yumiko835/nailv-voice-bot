"""Controlled tail/length investigation; never modifies weights or defaults."""

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
import contextlib, types, itertools
import numpy as np, soundfile as sf, yaml
from nailv_audio_export import prepare_reference, float_audio_postprocess, export_native

O=T/'e14-tail-repair-20261025';O.mkdir(parents=True,exist_ok=True)
assert not (O/'generation.json').exists(), 'Preserve prior trials.'
sel=read(T/'selected-models.json');bank=read(T/'prompts/manifest.json')
assert sel['gpt']['epoch']==6 and sel['sovits_epoch']==14
for k in ['gpt','sovits']:assert sha(sel[k]['path'])==sel[k]['sha256']
write(O/'selected-models-before.json',sel);write(O/'reference-manifest.json',bank)
write(O/'feedback.json',{'user':'慢慢来的来拖了好长的音，电流音主要存在于吸气呼气，与每个停顿前一个字的尾音，能不能改善一下','source_manifest':str(T/'e14-more-sentences-20261025/manifest.json'),'no_new_training':True})
status('proplus-comparing-continuation',activity='e14-tail-repair',completed=0,total=6)
torch=runtime()
from nailv_connected_frontend import install
install()
import GPT_SoVITS.TTS_infer_pack.TTS as engine
from low_peak_loading import install as low_peak
low_peak(engine);engine.now_dir=str(M.parent.parent)
cfg=O/'tts.yaml';cfg.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':sel['gpt']['path'],'vits_weights_path':sel['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (O/'model-load.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):tts=engine.TTS(engine.TTS_Config(str(cfg)))
tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts)
original=tts.vits_model.decode;codes=[]
def floating(v):
 if isinstance(v,torch.Tensor) and v.is_floating_point():return v.float()
 if isinstance(v,list):return [floating(z) for z in v]
 return v
def capture(*args,**kwargs):
 codes.extend(args[0].flatten().detach().cpu().tolist())
 previous=next(tts.vits_model.parameters()).dtype
 try:
  tts.vits_model.float();kwargs={k:floating(v) for k,v in kwargs.items()};kwargs['noise_scale']=.5
  return original(*[floating(v) for v in args],**kwargs)
 finally:
  if previous==torch.float16:tts.vits_model.half()
tts.vits_model.decode=capture
rows=[]
cases=[
 ('slow-original','温柔原参数复现','gentle',1.35,42),
 ('slow-seed73','温柔语气 · 仅重新采样','gentle',1.35,73),
 ('slow-rp140','温柔语气 · 重复惩罚1.40','gentle',1.40,42),
 ('slow-rp150','温柔语气 · 重复惩罚1.50','gentle',1.50,42),
 ('slow-seed137','温柔语气 · 另一采样','gentle',1.35,137),
 ('slow-daily','同文改用日常参考（仅供归因）','daily',1.35,42),
]
for name,label,style,rp,seed in cases:
 d=O/'generated'/name;d.mkdir(parents=True,exist_ok=True);prompt=bank['prompts'][style]
 prep=d/'reference.wav';preparation=prepare_reference(prompt['path'],prep,gate_plan=prompt['micro_gate_plan'])
 tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None;codes.clear()
 text='慢慢来，慢慢来，先把这句话说清楚。'
 settings={'text_lang':'zh','prompt_lang':'zh','top_k':5,'top_p':.9,'temperature':.85,'speed_factor':1.,'text_split_method':'cut0','seed':seed,'parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'repetition_penalty':rp,'super_sampling':False}
 with (d/'inference.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):parts=list(tts.run(settings|{'text':text,'ref_audio_path':str(prep),'prompt_text':prompt['text']}))
 assert parts and all(sr==32000 for sr,_ in parts)
 y=np.concatenate([v for _,v in parts]).astype(np.float32)
 runs=[{'token':int(k),'frames':len(list(g))} for k,g in itertools.groupby(codes)]
 row={'id':'e14-tail-'+name,'label':label,'text':text,'style':style,'reference_id':prompt['id'],'reference_preparation':preparation,'settings':settings,'gpt_epoch':6,'acoustic_epoch':14,'semantic_tokens':len(codes),'maximum_identical_token_run':max(v['frames'] for v in runs),'long_token_runs':[v for v in runs if v['frames']>=5],'semantic_ids':codes.copy(),'no_time_stretch':True,'no_output_denoising':True,**export_native(y,d)}
 rows.append(row);write(d/'result.json',row);write(O/'generation.json',{'models':sel,'samples':rows,'human_quality_verified':False})
 print(json.dumps({'id':name,'seconds':row['seconds'],'tokens':len(codes),'max_run':row['maximum_identical_token_run']},ensure_ascii=False),flush=True)
 status('proplus-comparing-continuation',activity='e14-tail-repair',completed=len(rows),total=len(cases))
verify_protected()
