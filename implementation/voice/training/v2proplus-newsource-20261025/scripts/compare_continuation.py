"""Fixed GPT-e6 semantic inputs; change only acoustic epoch or latent noise."""

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
import gc
import numpy as np,soundfile as sf
C=T/'continuation-e10to14-20261025';O=T/'inference-diagnosis-20261025';torch=runtime()
assert read(C/'training-receipt.json')['epochs_completed']==14
sel=read(T/'selected-models.json');assert sel['gpt']['epoch']==6 and sel['gpt_user_locked'];assert sha(sel['gpt']['path'])==sel['gpt']['sha256']
from module.models import SynthesizerTrn
from process_ckpt import load_sovits_new
config=read(C/'configs/stage2-train.json');net=SynthesizerTrn(config['data']['filter_length']//2+1,config['train']['segment_size']//config['data']['hop_length'],n_speakers=config['data']['n_speakers'],**config['model']).cuda().float().eval().requires_grad_(False)
from nailv_audio_export import export_native
rows=[]
def convert(v):
 if isinstance(v,torch.Tensor):return v.cuda().to(torch.float32 if v.is_floating_point() else v.dtype)
 if isinstance(v,list):return [convert(x) for x in v]
 return v
models=[(10,Path(sel['sovits']['path'])),(12,C/'checkpoints/milkgreen-proplus-continued-e12.pth'),(14,C/'checkpoints/milkgreen-proplus-continued-e14.pth')]
frozen=load_sovits_new(str(models[0][1]))['weight'];frozen={k:v for k,v in frozen.items() if k.startswith(('ssl_proj.','quantizer.'))}
for epoch,path in models:
 state=load_sovits_new(str(path));assert all(torch.equal(v,state['weight'][k]) for k,v in frozen.items());match=net.load_state_dict(state['weight'],strict=False);assert not match.unexpected_keys and all(k.startswith('enc_q.') for k in match.missing_keys);del state;gc.collect()
 for scale in ([.5,.25,0.] if epoch==10 else [.5]):
  for name,source in [('mama','mama-rp135'),('calm','gentle-rp135')]:
   cap=torch.load(O/source/'decode-inputs.pt',map_location='cpu',weights_only=False);args=convert(cap['args']);kwargs={k:convert(v) for k,v in cap['kwargs'].items()};kwargs['noise_scale']=scale;torch.manual_seed(777);torch.cuda.manual_seed_all(777)
   with torch.inference_mode():y=net.decode(*args,**kwargs).detach().float().cpu().numpy()[0,0]
   key=f'acoustic{epoch}-{name}' if scale==.5 else f'noise{int(scale*100):02d}-{name}';out=C/'generated'/key;out.mkdir(exist_ok=True);row={'id':key,'group':'acoustic' if scale==.5 else 'noise','label':f'音色第{epoch}轮 · '+('重复词' if name=='mama' else '正常接话') if scale==.5 else f'音色第10轮 · 随机噪声量{scale:g} · '+('重复词' if name=='mama' else '正常接话'),'text':cap['text'],'reference_id':cap['reference_id'],'GPT_epoch':6,'GPT_sha256':sel['gpt']['sha256'],'sovits_epoch':epoch,'sovits_sha256':sha(path),'noise_scale':scale,'decoder_precision':'FP32','decoder_seed':777,'semantic_input_sha256':sha(O/source/'decode-inputs.pt'),'reference_reselected':False,'repetition_penalty':1.35,'speed_factor':1.,'audio_denoising':False,**export_native(y,out)};rows.append(row);write(C/'comparison.json',{'samples':rows,'human_quality_verified':False,'GPT_user_locked_epoch':6,'default_acoustic_not_auto_changed':True});print(json.dumps({'generated':key,'seconds':row['seconds'],'peak':row['native_peak']},ensure_ascii=True),flush=True)
# Equalize each sentence using attenuation only across all variants.
for text in set(r['text'] for r in rows):
 group=[r for r in rows if r['text']==text];rmses=[]
 for r in group:
  y,sr=sf.read(r['native_float'],dtype='float32');frame=np.pad(y,(0,(-len(y))%640)).reshape(-1,640);rms=np.sqrt(np.mean(frame**2,axis=1));active=rms>max(.001,rms.max()*.1);rmses.append(float(np.sqrt(np.mean(rms[active]**2))))
 target=min(rmses)*.9
 for r,rms in zip(group,rmses):
  y,sr=sf.read(r['native_float'],dtype='float32');gain=min(1.,target/rms);out=Path(r['native_float']).parent/'listen-equalized.wav';sf.write(out,np.r_[np.zeros(5120,dtype='float32'),y*gain,np.zeros(10240,dtype='float32')],sr,subtype='PCM_24');r.update(playback=str(out),playback_sha256=sha(out),audition_gain_db=float(20*np.log10(gain)),active_rms_target=target,positive_gain=False)
write(C/'comparison.json',{'samples':rows,'human_quality_verified':False,'GPT_user_locked_epoch':6,'default_acoustic_not_auto_changed':True,'matched_active_rms_per_text':True})
verify_protected()
for path,digest in read(C/'protected-hashes.json').items():assert sha(path)==digest,path
write(C/'comparison-verification.json',{'same_frozen_GPT6_semantic_inputs':True,'unchanged_semantic_codec':True,'same_reference_text_and_audio_features':True,'all_native32k_lossless':True,'original_checkpoints_resume_and_data_unchanged':True,'acoustic_epochs_compared':[10,12,14],'inference_noise_scales_compared':[.5,.25,0.],'human_electrical_artifact_resolved':False})
