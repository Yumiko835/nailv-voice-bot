"""Attenuate only independently unvoiced, low-energy gaps; protected samples stay exact."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.ndimage import uniform_filter1d,maximum_filter1d
POLICY='reference-quiet-gaps-v1'

def protection_mask(samples,sr,words,vad):
 mask=np.zeros(samples,dtype=bool)
 for rows,pad in [(words,.10),(vad,.08)]:
  for row in rows:
   lo=max(0,int((row['start']-pad)*sr));hi=min(samples,int(np.ceil((row['end']+pad)*sr)));mask[lo:hi]=True
 return mask

def make_plan(y,sr,words,vad,source_sha256):
 y=np.asarray(y,dtype=np.float32);assert y.ndim==1 and sr in [44100,48000] and np.isfinite(y).all()
 protected=protection_mask(len(y),sr,words,vad)
 # Absolute ceiling and relative limit both apply; quiet voices receive a
 # lower threshold. No spectral processing and no gain increase are used.
 active_rms=float(np.sqrt(np.mean(y[protected]**2))) if protected.any() else 0.
 threshold_db=min(-44.,20*np.log10(max(active_rms,1e-12))-22.)
 threshold=10**(threshold_db/20);rms=np.sqrt(np.maximum(uniform_filter1d(y.astype(np.float64)**2,max(1,round(.02*sr)),mode='nearest'),0))
 peak=maximum_filter1d(np.abs(y),max(1,round(.01*sr)),mode='nearest')
 quiet=(~protected)&(rms<threshold)&(peak<2*threshold)
 edges=np.diff(np.r_[False,quiet,False].astype(np.int8));regions=[]
 for lo,hi in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
  if hi-lo>=round(.12*sr):regions.append([int(lo),int(hi)])
 return {'policy':POLICY,'source_sha256':source_sha256,'sample_rate':sr,'samples':len(y),'words':words,'vad':vad,'word_padding_ms':100,'vad_padding_ms':80,'rms_window_ms':20,'absolute_threshold_ceiling_dbfs':-44.,'actual_threshold_dbfs':float(threshold_db),'minimum_quiet_gap_ms':120,'transition_ms':20,'attenuation_db':-4.5,'regions_samples':regions,'protected_sample_count':int(protected.sum()),'automatic_speech_detection_is_not_infallible':True,'no_spectral_filtering':True}

def apply_plan(y,sr,plan):
 y=np.asarray(y,dtype=np.float32);assert plan['policy']==POLICY and sr==plan['sample_rate'] and len(y)==plan['samples']
 protected=protection_mask(len(y),sr,plan['words'],plan['vad']);gain=np.ones(len(y),dtype=np.float32);floor=np.float32(10**(plan['attenuation_db']/20));ramp_len=round(plan['transition_ms']*sr/1000)
 for lo,hi in plan['regions_samples']:
  assert 0<=lo<hi<=len(y) and not protected[lo:hi].any()
  n=min(ramp_len,(hi-lo)//2);curve=np.full(hi-lo,floor,dtype=np.float32)
  if n>1:
   ramp=(.5-.5*np.cos(np.linspace(0,np.pi,n))).astype(np.float32);curve[:n]=1-(1-floor)*ramp;curve[-n:]=curve[:n][::-1]
  gain[lo:hi]=curve
 z=y*gain;assert np.array_equal(z[protected],y[protected]) and np.isfinite(z).all()
 return z,protected,{'policy':POLICY,'regions_seconds':[[a/sr,b/sr] for a,b in plan['regions_samples']],'quiet_gap_count':len(plan['regions_samples']),'quiet_gap_seconds':sum(b-a for a,b in plan['regions_samples'])/sr,'modified_samples':int(np.count_nonzero(z!=y)),'protected_samples_bit_identical':True,'maximum_attenuation_db':plan['attenuation_db'],'threshold_dbfs':plan['actual_threshold_dbfs'],'trimmed_samples':0,'resampled':False,'positive_gain':False,'hard_mute':False}

def load_and_apply(y,sr,source_sha256,descriptor):
 path=Path(descriptor['path']);actual=hashlib.sha256(path.read_bytes()).hexdigest();assert actual==descriptor['sha256'],'Gate plan changed'
 plan=json.loads(path.read_text(encoding='utf-8'));assert plan['source_sha256']==source_sha256,'Refuse repeated gating or a gate plan belonging to another source'
 return apply_plan(y,sr,plan)
