"""Accepted calm confirmation ending, preserving input punctuation and full hum.

This is explicitly optional duration postprocessing, not native synthesis. It
uses no ASR, character timestamps, fixed audio clip, added pause or pitch shift.
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
import re

VERSION='calm-complete-hum313-v1'
STYLES={'daily','explaining'}

def eligible(text,style):
    # Only a plain explicit final confirmation. Thinking, questions, expressive
    # exclamations, initial 嗯 and stronger emotional references retain native audio.
    match=re.search(r'[，,。.]\s*嗯[。.]?$',text)
    return style in STYLES and match is not None and len(re.findall(r'[\u3400-\u9fff]',text[:match.start()]))>=4

def apply(y,sr,text,style):
    receipt={'policy':VERSION,'active':eligible(text,style),'applied':False,'target_ms':313,
      'text_unchanged':True,'reference_unchanged':True,'added_pause_seconds':0,
      'ASR_or_character_alignment':False,'fixed_audio_clip':False,'local_gain_db':0}
    if not receipt['active']:return y,receipt|{'reason':'Not a plain calm terminal confirmation.'}
    import numpy as np
    import parselmouth
    from scipy import ndimage
    from parselmouth.praat import call,run
    assert y.ndim==1 and sr>0 and np.isfinite(y).all()
    def keep(reason):return y,receipt|{'reason':reason}
    frame=round(.02*sr);hop=round(.01*sr)
    if len(y)<frame:return keep('Too short; native audio retained.')
    rms=np.array([np.sqrt(np.mean(y[a:a+frame]**2)) for a in range(0,len(y)-frame+1,hop)])
    times=(np.arange(len(rms))*hop+frame/2)/sr
    mask=ndimage.binary_closing(rms>max(1e-5,np.percentile(rms,90)*10**(-30/20)),iterations=1)
    changes=np.diff(np.r_[False,mask,False].astype(int))
    regions=[(float(times[a]),float(times[min(b-1,len(times)-1)])) for a,b in zip(np.flatnonzero(changes==1),np.flatnonzero(changes==-1))]
    if len(regions)<2:return keep('No reliable independent final region; native audio retained.')
    start,end=regions[-1];previous=regions[-2][1]
    if not (.035<=start-previous<=.45 and .4<=end-start<=.9 and end>=len(y)/sr-.25):
        return keep('Ending already short or not safely separate; native audio retained.')
    pitch=parselmouth.Sound(y,sampling_frequency=sr).to_pitch_ac(time_step=.01,pitch_floor=65,pitch_ceiling=600,voicing_threshold=.5)
    pt=pitch.xs();f0=pitch.selected_array['frequency'];voiced=pt[(f0>0)&(pt>=start)&(pt<=end)]
    if len(voiced)<20:return keep('Insufficient periodic evidence for complete hum; native audio retained.')
    onset=max(start,float(voiced[0])-.035);offset=min(end,float(voiced[-1])+.06)
    part=y[round(onset*sr):round(offset*sr)].copy();target=round(.313*sr)
    if len(part)-target<=round(.07*sr):return keep('Ending already short; native audio retained.')
    length=len(part)/sr;protect=.055;transition=.012
    factor=(.313-2*protect-transition)/(length-2*protect-transition)
    if not .2<factor<1.:return keep('Required duration change outside accepted range; native audio retained.')
    # Praat's unvoiced overlap-add transitions use its own RNG. A local seed
    # makes repeated processing stable without changing the duration trajectory.
    run('seedResult = random_initializeWithSeedUnsafelyButPredictably (313)')
    sound=parselmouth.Sound(part,sampling_frequency=sr)
    manipulation=call(sound,'To Manipulation',.01,65,600);tier=call(manipulation,'Extract duration tier')
    for tm,scale in [(0.,1.),(protect,1.),(protect+transition,factor),(length-protect-transition,factor),(length-protect,1.),(length,1.)]:call(tier,'Add point',tm,scale)
    call([tier,manipulation],'Replace duration tier')
    rendered=call(manipulation,'Get resynthesis (overlap-add)');cut=rendered.values[0].astype(y.dtype).copy()
    if abs(len(cut)/sr-.313)>=.012 or not np.isfinite(cut).all():return keep('Duration renderer validation failed; native audio retained.')
    fade_in=round(.008*sr);fade_out=round(.018*sr)
    cut[:fade_in]*=np.sin(np.linspace(0,np.pi/2,fade_in))**2
    cut[-fade_out:]*=np.cos(np.linspace(0,np.pi/2,fade_out))**2
    prefix_end=round(start*sr);body=y[:prefix_end].copy();bridge=round(.008*sr)
    body[-bridge:]*=np.cos(np.linspace(0,np.pi/2,bridge))**2
    out=np.r_[body,cut,np.zeros(round(.04*sr),dtype=y.dtype)]
    assert np.array_equal(out[:prefix_end-bridge],y[:prefix_end-bridge])
    detail={'actual_hmm_ms':1000*len(cut)/sr,'complete_hmm_trajectory_used':True,
      'onset_and_end_duration_uncompressed_ms':55,'detected_final_energy_region':[start,end],
      'extracted_region':[onset,offset],'central_duration_factor':factor,
      'body_unchanged_until_seconds':(prefix_end-bridge)/sr,'Praat_seed':313,'method':'Praat TD-PSOLA duration tier; complete isolated terminal hum only'}
    return out,receipt|{'applied':True,'reason':'Human-accepted complete short confirmation method.','detail':detail}
