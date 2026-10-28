"""Explicit confirmation-ending edit: retain attack/fall, reduce central hold only."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import numpy as np,parselmouth
from scipy import ndimage,signal
def spans(mask,times):
    d=np.diff(np.r_[False,mask,False].astype(int));return [(float(times[a]),float(times[min(b-1,len(times)-1)])) for a,b in zip(np.flatnonzero(d==1),np.flatnonzero(d==-1))]
def affirm_hmm(y,sr,text,target_ms):
    import re
    assert re.search(r'[，,]\s*嗯[。.!！]?$',text) and target_ms in (280,340)
    frame=round(.02*sr);hop=round(.01*sr)
    rms=np.array([np.sqrt(np.mean(y[a:a+frame]**2)) for a in range(0,len(y)-frame+1,hop)]);rt=(np.arange(len(rms))*hop+frame/2)/sr
    mask=ndimage.binary_closing(rms>max(1e-5,np.percentile(rms,90)*10**(-30/20)),iterations=1)
    regions=spans(mask,rt);assert len(regions)>=2;start,end=regions[-1];prev=regions[-2][1]
    assert .035<=start-prev<=.45 and .4<=end-start<=.9 and end>=len(y)/sr-.25
    pitch=parselmouth.Sound(y,sampling_frequency=sr).to_pitch_ac(time_step=.01,pitch_floor=65,pitch_ceiling=600,voicing_threshold=.5)
    vt=pitch.xs();f0=pitch.selected_array['frequency'];v=vt[(f0>0)&(vt>=start)&(vt<=end)];assert len(v)>=20
    onset=max(start,float(v[0])-.035);offset=min(end,float(v[-1])+.06);part=y[round(onset*sr):round(offset*sr)].copy()
    target=round(target_ms*sr/1000);assert len(part)-target>round(.07*sr)
    # Keep the complete phonetic trajectory. Praat TD-PSOLA adjusts this hum's
    # duration without applying a pitch shift or processing the preceding words.
    # A flat duration tier at the edges preserves their temporal extent.
    from parselmouth.praat import call
    sound=parselmouth.Sound(part,sampling_frequency=sr);length=len(part)/sr;protect=.055;transition=.012
    factor=(target_ms/1000-2*protect-transition)/(length-2*protect-transition);assert .2<factor<1.
    manipulation=call(sound,'To Manipulation',.01,65,600);tier=call(manipulation,'Extract duration tier')
    for tm,scale in [(0.,1.),(protect,1.),(protect+transition,factor),(length-protect-transition,factor),(length-protect,1.),(length,1.)]:call(tier,'Add point',tm,scale)
    call([tier,manipulation],'Replace duration tier');rendered=call(manipulation,'Get resynthesis (overlap-add)');cut=rendered.values[0].astype(y.dtype).copy()
    assert abs(len(cut)/sr-target_ms/1000)<.012 and np.isfinite(cut).all()
    fade_in=round(.008*sr);fade_out=round(.018*sr);cut[:fade_in]*=np.sin(np.linspace(0,np.pi/2,fade_in))**2;cut[-fade_out:]*=np.cos(np.linspace(0,np.pi/2,fade_out))**2
    prefix_end=round(start*sr);body=y[:prefix_end].copy();bridge=round(.008*sr);body[-bridge:]*=np.cos(np.linspace(0,np.pi/2,bridge))**2
    out=np.r_[body,cut,np.zeros(round(.04*sr),dtype=y.dtype)];assert np.array_equal(out[:prefix_end-bridge],y[:prefix_end-bridge])
    return out,{'semantic_target':'brief audible confirmation of the preceding statement','nominal_hmm_ms':target_ms,'actual_hmm_ms':1000*len(cut)/sr,'local_gain_db':0,'complete_hmm_trajectory_used':True,'onset_and_end_duration_uncompressed_ms':55,'detected_final_energy_region':[start,end],'extracted_region':[onset,offset],'method':'Praat TD-PSOLA with duration tier, hum only','central_duration_factor':factor,'output_not_lowpass_filtered':True,'body_unchanged_until_seconds':(prefix_end-bridge)/sr,'no_global_stretch_or_requested_pitch_shift':True,'automatic_boundary_requires_explicit_hmm_context':True}
