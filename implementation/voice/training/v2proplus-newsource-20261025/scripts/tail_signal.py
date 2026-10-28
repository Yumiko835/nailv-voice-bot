"""Bounded derivative-copy treatment for quiet gaps and fading pre-pause tails.

No resampling, pitch shift, duration edit, neural enhancement or phase replacement.
Speech/noise separation is only an acoustic heuristic, not phoneme recognition.
"""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import numpy as np
from scipy import signal, ndimage

def regions(mask):
    edges=np.diff(np.r_[False,mask,False].astype(np.int8))
    return list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))

def treat_tails(y,sr,strength='light'):
    y=np.asarray(y,dtype=np.float32)
    if sr!=32000 or y.ndim!=1 or not len(y) or not np.isfinite(y).all():
        raise ValueError('Expected finite native 32kHz mono synthesis.')
    if strength not in ['light','moderate']:raise ValueError('Unknown bounded treatment.')
    if np.max(np.abs(y))<1e-8:return y.copy(),{'applied':False,'reason':'silent input'}
    hop=160;window=1024
    frequencies,times,z=signal.stft(y,sr,nperseg=window,noverlap=window-hop,boundary='zeros',padded=True)
    power=np.abs(z)**2;level=np.sqrt(power.sum(axis=0))
    present=level>max(1e-7,float(level.max())*.005)
    speech=max(float(np.percentile(level[present],75)),1e-7)
    relative=20*np.log10(np.maximum(level,1e-12)/speech)
    weak=np.clip((-relative-10)/14,0,1)
    quiet=relative<-20
    keep=np.zeros(len(times),bool);tail=np.zeros(len(times),np.float32)
    intervals=[]
    for start,end in regions(quiet):
        if (end-start)*hop/sr<.06:continue
        keep[start:end]=True
        intervals.append([float(times[start]),float(times[min(end,len(times)-1)])])
        left=max(0,start-round(.18*sr/hop))
        if start>left:tail[left:start]=np.maximum(tail[left:start],np.linspace(0,1,start-left,dtype=np.float32))
    # Estimate the floor only in quiet frames; suppress nothing if unsupported.
    if keep.sum()<6:return y.copy(),{'applied':False,'reason':'Insufficient quiet frames for a bounded noise estimate.'}
    quiet_profile=np.percentile(power[:,keep],60,axis=1)[:,None]
    # Synthesized hiss is not stationary: the floor during a fading vowel can
    # be much higher than digital gaps. A local frequency median provides a
    # bounded estimate of diffuse/valley energy without replacing the phase.
    # This estimate is only blended into the preselected weak/tail intervals.
    local_floor=ndimage.median_filter(power,size=(17,1),mode='nearest')*.65
    frequency_weight=np.clip((frequencies-180)/500,0,1)[:,None]
    profile=np.maximum(quiet_profile,local_floor)*frequency_weight
    weakcap,tailcap,gapcap=(4.,1.5,6.) if strength=='light' else (7.,3.,10.)
    # Strong speech is protected. Only weak regions or a fading tail before a
    # detected pause can be blended with the spectral attenuation candidate.
    target=np.maximum(weak,tail*np.clip((-relative-3)/12,0,1)*.75)
    target=ndimage.gaussian_filter1d(target,2)
    target[relative>=-3]=0
    cap=np.maximum(weak*weakcap,tail*tailcap)
    floor=10**(-cap[None,:]/20)
    gain=np.sqrt(np.maximum(1-.95*profile/np.maximum(power,1e-14),floor**2))
    gain=ndimage.gaussian_filter(gain,sigma=(1.,2.))
    gain=np.clip(gain,floor,1.)
    # Smooth downward expansion only inside very low-level gap interiors.
    quiet_interior=ndimage.minimum_filter1d(keep.astype(np.float32),size=9,mode='constant')
    gap_amount=ndimage.gaussian_filter1d(quiet_interior*weak,3)
    gap_gain=10**(-gapcap*gap_amount/20)
    _,candidate=signal.istft(z*gain*gap_gain[None,:],sr,nperseg=window,noverlap=window-hop,boundary=True)
    candidate=candidate[:len(y)]
    if len(candidate)<len(y):candidate=np.pad(candidate,(0,len(y)-len(candidate)))
    positions=np.arange(len(y))/sr
    blend=np.interp(positions,times,target).astype(np.float32)
    # Reconstructing only the affected region preserves protected core samples
    # exactly, avoiding a blanket low-pass or whole-voice spectral rewrite.
    out=(y+blend*(candidate-y)).astype(np.float32)
    assert len(out)==len(y) and np.isfinite(out).all()
    assert np.array_equal(out[blend==0],y[blend==0])
    meta={'applied':True,'strength':strength,'algorithm':'phase-preserving capped spectral attenuation + smooth quiet-gap downward expansion',
        'sample_rate':sr,'samples':len(y),'modified_fraction':float(np.mean(out!=y)),
        'protected_core_fraction':float(np.mean(blend==0)),'protected_core_bit_identical':True,
        'spectral_weak_cap_db':weakcap,'spectral_tail_cap_db':tailcap,'quiet_expander_cap_db':gapcap,
        'local_diffuse_floor_used':True,'fundamental_below_180hz_spectral_attenuation':False,
        'quiet_profile_frames':int(keep.sum()),'quiet_intervals_seconds':intervals,
        'sample_count_unchanged':True,'phase_replaced':False,'time_stretched':False,
        'resampled':False,'lowpass_applied':False,'hard_mute':False,'positive_gain':False,
        'human_quality_verified':False,
        'limitation':'Acoustic masks can include quiet consonants or breathy syllables; audition for loss of clarity. Tonal artifacts in strong voiced audio may remain.'}
    return out,meta
