"""Lossless native-rate inference I/O; no denoiser, resampling, pitch or tempo edit."""

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
import hashlib
import numpy as np
import soundfile as sf

NATIVE_SR=32000
PIPELINE_REVISION='proplus-native-32k-pcm24-v1'

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def edge_fade(y,sr,ms=8.):
 """Half-cosine ramps affect only the first/last 8ms, leaving every sample between intact."""
 y=np.asarray(y,dtype=np.float32).copy()
 if y.ndim!=1 or not np.isfinite(y).all():raise ValueError('Invalid mono reference waveform.')
 if not 5<=ms<=10:raise ValueError('Reference edge fade must be 5–10ms.')
 n=min(round(sr*ms/1000),len(y)//2)
 if n<2:raise ValueError('Reference too short for a safe edge fade.')
 ramp=(.5-.5*np.cos(np.linspace(0,np.pi,n,dtype=np.float32)))
 y[:n]*=ramp;y[-n:]*=ramp[::-1]
 return y,n

def prepare_reference(source,destination,ms=8.,gate_plan=None):
 y,sr=sf.read(source,dtype='float32');original_sha=sha(source)
 if sr not in [44100,48000,NATIVE_SR]:raise ValueError('Expected a native44.1kHz or48kHz source prompt.')
 gate=None;protected=None;z=y
 if gate_plan:
  from reference_micro_gate import load_and_apply
  z,protected,gate=load_and_apply(y,sr,original_sha,gate_plan)
 faded,n=edge_fade(z,sr,ms)
 if protected is not None:
  faded[protected]=z[protected]
  assert np.array_equal(faded[protected],y[protected]),'Speech-protected samples changed'
 z=faded;sf.write(destination,z,sr,subtype='FLOAT')
 assert sha(source)==original_sha
 return {'original_path':str(source),'original_sha256':original_sha,'loaded_path':str(destination),'loaded_sha256':sha(destination),'fade_ms':ms,'fade_samples_each_edge':n,'seconds':len(y)/sr,'sample_rate':sr,'original_endpoints':[float(y[0]),float(y[-1])],'processed_endpoints':[float(z[0]),float(z[-1])],'interior_samples_unchanged':bool(np.array_equal(y[n:-n],z[n:-n])),'speech_protected_samples_unchanged':True if protected is not None else None,'micro_gate':gate,'reference_resampling':False,'words_or_duration_removed':False,'encoding':'WAV FLOAT reference copy'}

def float_audio_postprocess(self,audio,sr,batch_index_list=None,speed_factor=1.,split_bucket=True,fragment_interval=.3,super_sampling=False):
 """Worker-local override: retain native vocoder floats until safe PCM encoding.

 Upstream casts float16*32768 directly to int16. A +1 peak can wrap to -32768.
 Do not mutate shared GPT-SoVITS files or any model parameters.
 """
 import torch
 if sr!=NATIVE_SR or super_sampling:raise ValueError('This export path requires native V2 ProPlus 32kHz without super-resolution.')
 result=[]
 for batch in audio:
  fragments=[]
  for fragment in batch:
   fragment=fragment.detach().float()
   if not torch.isfinite(fragment).all():raise ValueError('Non-finite native vocoder output.')
   peak=fragment.abs().max()
   if peak>1:fragment=fragment/peak
   if fragment_interval>0:fragment=torch.cat((fragment,torch.zeros(round(sr*fragment_interval),device=fragment.device)))
   fragments.append(fragment)
  result.append(fragments)
 if split_bucket:fragments=self.recovery_order(result,batch_index_list)
 else:fragments=[f for batch in result for f in batch]
 return sr,torch.cat(fragments).cpu().numpy().astype(np.float32,copy=False)

def export_native(y,out):
 out=Path(out);y=np.asarray(y,dtype=np.float32)
 if y.ndim!=1 or not len(y) or not np.isfinite(y).all():raise ValueError('Invalid synthesis audio.')
 native=out/'native-float.wav';sf.write(native,y,NATIVE_SR,subtype='FLOAT')
 peak=float(np.abs(y).max());conversion=min(1.,.999/max(peak,1e-12))
 raw=out/'raw.wav';sf.write(raw,y*conversion,NATIVE_SR,subtype='PCM_24')
 frame=640;z=np.pad(y,(0,(-len(y))%frame)).reshape(-1,frame);rms=np.sqrt(np.mean(z*z,axis=1));active=rms>max(.001,float(rms.max())*.04)
 active_rms=float(np.sqrt(np.mean(z[active]**2))) if active.any() else 0.
 # Attenuate peaks/loud speech; never amplify weak/noisy failed synthesis.
 gain=min(1.,.09/max(active_rms,1e-12),.89/max(peak,1e-12))
 lead=5120;tail=10240;play=out/'speech.wav';sf.write(play,np.r_[np.zeros(lead,dtype=np.float32),y*gain,np.zeros(tail,dtype=np.float32)],NATIVE_SR,subtype='PCM_24')
 meta={'native_float':str(native),'native_float_sha256':sha(native),'raw':str(raw),'raw_sha256':sha(raw),'playback':str(play),'playback_sha256':sha(play),'native_peak':peak,'raw_conversion_gain_db':float(20*np.log10(conversion)),'playback_gain_db':float(20*np.log10(gain)),'padding_samples':{'lead':lead,'tail':tail},'trimmed_samples':0,'sample_rate':NATIVE_SR,'seconds':len(y)/NATIVE_SR,'export_format':'WAV','export_subtype':'PCM_24','lossy_encoding':False,'output_resampling':False,'audio_processing_revision':PIPELINE_REVISION,'upward_gain_allowed':False}
 return meta
