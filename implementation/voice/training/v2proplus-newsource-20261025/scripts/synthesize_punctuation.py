"""Three requested inference patches; fixed ProPlus GPT6 + original SoVITS14."""

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
import argparse,contextlib,types,re,itertools
import numpy as np,soundfile as sf,yaml
from emotion_routing import route
from nailv_audio_export import prepare_reference,float_audio_postprocess,export_native
from punctuation_audio_patch import cut_punc,tail_token_plan,process_clause

p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reference-manifest',type=Path);a=p.parse_args()
torch=runtime()
from nailv_connected_frontend import install
install()
import GPT_SoVITS.TTS_infer_pack.TTS as engine
import TTS_infer_pack.text_segmentation_method as segmentation
from low_peak_loading import install as low_peak
segmentation.METHODS['cut_punc']=lambda text:'\n'.join(c['inference_text'] for c in cut_punc(text))
low_peak(engine);engine.now_dir=str(M.parent.parent)
selected=read(T/'selected-models.json')
assert selected['gpt']['epoch']==6 and selected['sovits_epoch']==14
for key in ['gpt','sovits']:assert sha(selected[key]['path'])==selected[key]['sha256']
bankpath=a.reference_manifest or T/'prompts/manifest.json';assert bankpath.resolve().is_relative_to(T.resolve())
bank=read(bankpath);a.out.mkdir(parents=True,exist_ok=True)
config=a.out/'tts-config.yaml';config.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':selected['gpt']['path'],'vits_weights_path':selected['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (a.out/'model-load.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):tts=engine.TTS(engine.TTS_Config(str(config)))
assert tts.configs.version=='v2ProPlus' and not tts.configs.use_vocoder
tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts)
native_decode=tts.vits_model.decode;events=[]

def floating(v):
 if isinstance(v,torch.Tensor) and v.is_floating_point():return v.float()
 if isinstance(v,list):return [floating(x) for x in v]
 return v

def precise_decode(*args,**kwargs):
 args=list(args);original=args[0].flatten().detach().cpu().tolist();plan=tail_token_plan(original)
 if plan['removed_tokens']:args[0]=args[0][...,:plan['retained_tokens']]
 retained=args[0].flatten().detach().cpu().tolist()
 runs=[len(list(g)) for _,g in itertools.groupby(retained)]
 previous=next(tts.vits_model.parameters()).dtype
 try:
  tts.vits_model.float();kwargs={k:floating(v) for k,v in kwargs.items()};kwargs['noise_scale']=.5
  y=native_decode(*[floating(v) for v in args],**kwargs)
  events.append({'token_tail_cap':plan,'maximum_identical_token_run_after':max(runs,default=0),
    'semantic_ids_before':original,'semantic_ids_after':retained,
    'acoustic_model_dtype':str(next(tts.vits_model.parameters()).dtype),'noise_scale':.5})
  return y
 finally:
  if previous==torch.float16:tts.vits_model.half()
tts.vits_model.decode=precise_decode

result={'version':'proplus-punctuation-tail-v1','models':selected,'reference_manifest_sha256':sha(bankpath),
 'patches':['independent punctuation clauses + 0.25s clean inserted gaps','predecoder suffix repeated-ID cap','100ms cosine fade + dynamic5kHz lowpass','4500-9000Hz de-esser,5dB cap'],
 'samples':[],'human_quality_verified':False,'source_audio_uploaded':False}
for row in read(a.requests)['samples']:
 r=route(row['text'],row.get('style','auto'),row.get('context',''));prompt=bank['prompts'][r['style']]
 assert prompt.get('enabled',True) and sha(prompt['path'])==prompt['sha256']
 out=a.out/row['id'];out.mkdir(exist_ok=True);prep=out/'reference-prepared.wav'
 preparation=prepare_reference(prompt['path'],prep,gate_plan=prompt['micro_gate_plan'])
 tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None
 chunks=cut_punc(r['text']);raw_parts=[];processed_parts=[];segments=[]
 initial_seed=int(row.get('seed',42));gap_samples=8000
 settings={'text_lang':'zh','prompt_lang':'zh','top_k':15,'top_p':.9,'temperature':float(row.get('temperature',.8)),
  'speed_factor':1.,'text_split_method':'cut_punc','parallel_infer':False,'batch_size':1,'split_bucket':False,
  'streaming_mode':False,'return_fragment':False,'fragment_interval':.25,'use_cuda_graph':False,
  'use_flash_attention':False,'repetition_penalty':1.35,'super_sampling':False}
 for index,chunk in enumerate(chunks):
  if len(chunk['inference_text'])>480:raise ValueError('单个无标点片段过长，请增加标点后再生成。')
  folder=out/f'clause-{index+1:02d}';folder.mkdir(exist_ok=True)
  attempts=[];units=max(1,len(re.sub(r'[^\w\u3400-\u9fff]','',chunk['spoken'])))
  for attempt,offset in enumerate([0,95,104729]):
   events.clear();seed=(initial_seed+index*1009+offset)%2**32
   with (folder/'inference.log').open('w' if attempt==0 else 'a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    parts=list(tts.run(settings|{'text':chunk['inference_text'],'ref_audio_path':str(prep),'prompt_text':prompt['text'],'seed':seed}))
   assert len(parts)==1 and parts[0][0]==32000,'Independent clause must decode once at32k'
   with_pad=np.asarray(parts[0][1],np.float32)
   assert len(with_pad)>gap_samples and np.all(with_pad[-gap_samples:]==0),'Known engine fragment pad changed'
   raw=with_pad[:-gap_samples].copy();seconds=len(raw)/32000
   maximum=max(e['maximum_identical_token_run_after'] for e in events)
   valid=max(.12,units/22.)<=seconds<=max(6.,units/1.5+2.) and maximum<16
   attempts.append({'seed':seed,'seconds':seconds,'valid':valid,'maximum_identical_token_run':maximum,'decode_events':events.copy()})
   if valid:break
   sf.write(folder/f'rejected-attempt-{attempt+1}.wav',raw,32000,subtype='PCM_24')
  else:raise RuntimeError('独立短句三次生成仍出现过早结束、长音或内部循环；日志已保留。')
  sf.write(folder/'native-before-acoustic-effects.wav',raw,32000,subtype='FLOAT')
  processed,breath,processing=process_clause(raw)
  sf.write(folder/'deesser-only.wav',breath,32000,subtype='FLOAT')
  sf.write(folder/'all-effects.wav',processed,32000,subtype='FLOAT')
  raw_parts.append(raw);processed_parts.append(processed)
  item=chunk|{'number':index+1,'seconds_before_effects':seconds,'seconds_after_effects':len(processed)/32000,
   'attempts':attempts,'postprocessing':processing,'engine_padding_removed_samples':gap_samples}
  write(folder/'clause.json',item);segments.append(item)
 def stitch(values):
  arranged=[];positions=[];position=0
  for i,v in enumerate(values):
   arranged.append(v);position+=len(v)
   if i+1<len(values):positions.append([position,position+gap_samples]);arranged.append(np.zeros(gap_samples,np.float32));position+=gap_samples
  return np.concatenate(arranged).astype(np.float32),positions
 untreated,positions=stitch(raw_parts);final,positions2=stitch(processed_parts)
 assert positions==positions2 and len(untreated)==len(final)
 for start,end in positions:assert np.all(final[start:end]==0)
 control_dir=out/'split-only';control_dir.mkdir(exist_ok=True)
 control=export_native(untreated,control_dir);exports=export_native(final,out)
 # Same gain across before/after so a quieter playback is not mistaken for
 # spectral improvement. Never amplify either comparison.
 gain=min(10**(control['playback_gain_db']/20),10**(exports['playback_gain_db']/20))
 for v,meta in [(untreated,control),(final,exports)]:
  sf.write(meta['playback'],np.r_[np.zeros(5120,np.float32),v*gain,np.zeros(10240,np.float32)],32000,subtype='PCM_24')
  meta.update(playback_gain_db=float(20*np.log10(gain)),playback_sha256=sha(meta['playback']))
 item=row|{'text':r['text'],'style':r['style'],'label':r['label'],'routing':r,'reference_id':prompt['id'],
  'reference_preparation':preparation,'settings':settings,'segments':segments,'inserted_silence_regions_samples':positions,
  'inserted_gap_seconds':.25,'no_output_denoising':False,'postprocessing_before_stitching':True,
  'same_sample_count_across_acoustic_effects':True,'control':control,**exports}
 write(out/'result.json',item);result['samples'].append(item);write(a.out/'manifest.json',result)
 print(json.dumps({'generated':row['id'],'clauses':len(chunks),'seconds':item['seconds'],
  'tail_tokens_removed':sum(e['token_tail_cap']['removed_tokens'] for s in segments for e in s['attempts'][-1]['decode_events']),
  'deesser_candidate_fraction':[s['postprocessing']['deesser']['candidate_frame_fraction'] for s in segments]},ensure_ascii=False),flush=True)
verify_protected();write(a.out/'manifest.json',result)
