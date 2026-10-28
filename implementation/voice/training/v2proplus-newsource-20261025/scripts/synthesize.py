
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
import argparse,contextlib,types,gc,re,itertools
p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reference-manifest',type=Path);a=p.parse_args()
import numpy as np,soundfile as sf,yaml
from emotion_routing import route
from nailv_audio_export import prepare_reference,float_audio_postprocess,export_native
torch=runtime();from nailv_connected_frontend import install
install();import GPT_SoVITS.TTS_infer_pack.TTS as engine
from low_peak_loading import install as low_peak
low_peak(engine);engine.now_dir=str(M.parent.parent)
selected=read(T/'selected-models.json');assert selected['sovits'] is not None
for key in ['gpt','sovits']:assert sha(selected[key]['path'])==selected[key]['sha256']
bankpath=a.reference_manifest or T/'prompts/manifest.json';assert bankpath.resolve().is_relative_to(T.resolve());bank=read(bankpath);a.out.mkdir(parents=True,exist_ok=True);config=a.out/'tts-config.yaml';config.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':selected['gpt']['path'],'vits_weights_path':selected['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (a.out/'model-load.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):tts=engine.TTS(engine.TTS_Config(str(config)))
inference=selected.get('inference',{});decode_events=[]
if inference.get('acoustic_precision')=='float32':
 # Match the FP32 acoustic inference used for the user's chosen e14 audition.
 # Keep feature extraction and GPT half precision; convert only during decode.
 native_decode=tts.vits_model.decode
 def floating(v):
  if isinstance(v,torch.Tensor) and v.is_floating_point():return v.float()
  if isinstance(v,list):return [floating(x) for x in v]
  return v
 def precise_decode(*args,**kwargs):
  previous=next(tts.vits_model.parameters()).dtype
  try:
   tts.vits_model.float();kwargs={k:floating(v) for k,v in kwargs.items()};kwargs['noise_scale']=float(inference.get('noise_scale',.5));y=native_decode(*[floating(x) for x in args],**kwargs);codes=args[0].flatten().detach().cpu().tolist();runs=[len(list(g)) for _,g in itertools.groupby(codes)];decode_events.append({'acoustic_model_dtype':str(next(tts.vits_model.parameters()).dtype),'output_dtype':str(y.dtype),'noise_scale':kwargs['noise_scale'],'semantic_tokens':len(codes),'maximum_identical_token_run':max(runs,default=0)});return y
  finally:
   if previous==torch.float16:tts.vits_model.half()
 tts.vits_model.decode=precise_decode
assert tts.configs.version=='v2ProPlus' and not tts.configs.use_vocoder;tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts);result={'version':'proplus-dualstage-test-v1','models':selected,'reference_manifest_sha256':sha(bankpath),'samples':[],'human_quality_verified':False,'source_audio_uploaded':False}
for row in read(a.requests)['samples']:
 decode_events.clear()
 r=route(row['text'],row.get('style','auto'),row.get('context',''));prompt=bank['alternates'][row['reference_key']] if row.get('reference_key') else bank['prompts'][r['style']];assert prompt.get('enabled',True),'Reference temporarily disabled due to repeated early EOS';assert prompt['style']==r['style'] and sha(prompt['path'])==prompt['sha256'];out=a.out/row['id'];out.mkdir(exist_ok=True);prep=out/'reference-prepared.wav';preparation=prepare_reference(prompt['path'],prep,gate_plan=prompt['micro_gate_plan']);tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None
 # Repetition penalty acts on acoustic semantic IDs, not repeated written words.
 # Lowering it for "妈妈妈妈" caused a 16-token identical run and sung vowels.
 settings={'text_lang':'zh','prompt_lang':'zh','top_k':5,'top_p':.9,'temperature':float(row.get('temperature',.85)),'speed_factor':1.,'text_split_method':'cut0','seed':int(row.get('seed',42)),'parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'repetition_penalty':float(row.get('repetition_penalty',1.35)),'super_sampling':False}
 attempts=[];units=max(1,len(re.sub(r'[^\u3400-\u9fffA-Za-z0-9]','',r['text'])));lower=max(.3,units/16.);upper=min(60.,max(14.,units/1.5+5.))
 # A duration-only guard allowed B03's 27 consecutive identical semantic IDs
 # (a >1s frozen sound). Retry sampling instead of cutting/stretching its vowel.
 # Explicit written elongation keeps its normal duration-only behavior.
 intentional_hold=bool(re.search(r'[…~～—]{2,}|[啊嗯哦唔诶哎]{3,}',r['text']))
 initial_seed=settings['seed']
 for attempt in range(3):
  if attempt:settings['seed']=(initial_seed+[0,95,104729][attempt])%2**32;tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None
  decode_events.clear()
  with (out/'inference.log').open('w' if attempt==0 else 'a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):parts=list(tts.run(settings|{'text':r['text'],'ref_audio_path':str(prep),'prompt_text':prompt['text']}))
  assert parts and all(sr==32000 for sr,_ in parts);y=np.concatenate([x for _,x in parts]).astype(np.float32);assert np.isfinite(y).all();seconds=len(y)/32000;duration_valid=lower<=seconds<=upper;max_run=max((e.get('maximum_identical_token_run',0) for e in decode_events),default=0);loop_valid=intentional_hold or max_run<16;valid=duration_valid and loop_valid;attempts.append({'seed':settings['seed'],'seconds':seconds,'duration_guard_passed':duration_valid,'semantic_loop_guard_passed':loop_valid,'maximum_identical_token_run':max_run,'intentional_written_elongation':intentional_hold})
  if valid:break
  sf.write(out/('failed-quality-attempt'+str(attempt+1)+'.wav'),y,32000,subtype='PCM_24')
 else:raise RuntimeError('三次生成均出现异常循环、长音或过早结束，已保留日志，请换一种情绪或缩短句子。')
 item=row|{'text':r['text'],'style':r['style'],'label':r['label'],'routing':r,'reference_id':prompt['id'],'reference_preparation':preparation,'settings':settings.copy(),'generation_attempts':attempts,'acoustic_decode_events':decode_events.copy(),'no_output_denoising':True,**export_native(y,out)};write(out/'result.json',item);result['samples'].append(item);write(a.out/'manifest.json',result);print(json.dumps({'generated':row['id'],'seconds':item['seconds']},ensure_ascii=False),flush=True)
 if a.requests.resolve()==(T/'generated/test-requests.json').resolve():status('proplus-generating-tests',completed=len(result['samples']),total=12)
verify_protected();write(a.out/'manifest.json',result)
