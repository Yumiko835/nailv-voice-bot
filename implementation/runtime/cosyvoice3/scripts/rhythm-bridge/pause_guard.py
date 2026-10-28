"""Cheap, conservative interior-gap guard; no ASR or emotion/model scoring.

Only long, very weak gaps bounded by speech are shortened. Coherent weak voice
is ambiguous and requests another synthesis seed instead of cutting a word.
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
import numpy as np

VERSION='interior-pause-guard-v1'

def _spans(mask):
    d=np.diff(np.r_[False,mask,False].astype(np.int8))
    return zip(np.flatnonzero(d==1),np.flatnonzero(d==-1))

def _periodicity(segment,sr):
    # Rough periodicity is used to PROTECT weak words, not diagnose a moan.
    step=max(1,sr//16000);x=np.asarray(segment[::step],dtype=np.float64);rate=sr/step
    frame=round(.04*rate);hop=round(.025*rate);values=[]
    lo,hi=max(2,round(rate/600)),min(frame-2,round(rate/70))
    for a in range(0,len(x)-frame+1,hop):
        v=x[a:a+frame];v=v-v.mean()
        if np.sqrt(np.mean(v*v))<3e-5:values.append(0.);continue
        corr=np.correlate(v,v,'full')[frame-1:]
        cumulative=np.r_[0.,np.cumsum(v*v)];lags=np.arange(lo,hi+1)
        den=np.sqrt(cumulative[frame-lags]*(cumulative[frame]-cumulative[lags]))+1e-18
        values.append(float(np.max(corr[lags]/den)))
    return float(np.mean(np.asarray(values)>.72)) if values else 0.

def inspect(y,sr,text='',affect=None):
    y=np.asarray(y);hop=max(1,round(.01*sr));frame=max(2,round(.02*sr))
    if y.ndim!=1 or len(y)<frame*3:raise ValueError('Expected mono audio')
    starts=np.arange(0,len(y)-frame+1,hop)
    rms=np.sqrt(np.asarray([np.mean(y[a:a+frame].astype(np.float64)**2) for a in starts]))
    db=20*np.log10(rms+1e-12);reference=float(np.percentile(db,85))
    threshold=min(-36.,reference-20.)
    quiet=db<threshold
    # Bridge only a single 10ms interruption, never a whole low-volume syllable.
    quiet[1:-1]|=quiet[:-2]&quiet[2:]
    active=np.flatnonzero(db>max(-40.,reference-12.))
    deliberate=bool(re.search(r'…{2,}|\.{3,}|(?:停顿|停|等|安静)[一二两三四五\d]+秒',text))
    limit=1.5 if deliberate else (1.25 if affect=='pet_loss' else .95)
    target=.7 if deliberate else (.55 if affect=='pet_loss' else .38)
    regions=[]
    if len(active):
        for a,b in _spans(quiet):
            start=int(starts[a]+frame//2);end=int(starts[min(b,len(starts)-1)]+frame//2)
            if (end-start)/sr<limit or a<=active[0] or b>=active[-1]:continue
            # Keep a safety margin around neighboring spoken syllables.
            inner=y[min(end,start+round(.06*sr)):max(start,end-round(.06*sr))]
            voiced_fraction=_periodicity(inner,sr)
            regions.append({'start_sample':start,'end_sample':end,'start_seconds':start/sr,'end_seconds':end/sr,
                'seconds':(end-start)/sr,'quiet_threshold_db':threshold,
                'median_db':float(np.median(db[a:b])),'weak_periodic_fraction':voiced_fraction,
                'safe_to_shorten':voiced_fraction<=.15,'retained_seconds':target})
    return {'version':VERSION,'regions':regions,'retry_recommended':any(not x['safe_to_shorten'] for x in regions),
            'not_an_ASR_or_moan_classifier':True,'explicit_thinking_pause':deliberate}

def repair(y,sr,text='',affect=None):
    report=inspect(y,sr,text,affect);pieces=[];cursor=0;output_samples=0;silences=[]
    for region in report['regions']:
        if not region['safe_to_shorten']:continue
        a,b=region['start_sample'],region['end_sample'];keep=round(region['retained_seconds']*sr)
        edge=min(round(.06*sr),keep//4);ramp=min(round(.016*sr),edge)
        prefix=y[cursor:a].copy();pieces.append(prefix);output_samples+=len(prefix)
        left=y[a:a+edge].copy();right=y[b-edge:b].copy()
        left[-ramp:]*=np.cos(np.linspace(0,np.pi/2,ramp))**2
        right[:ramp]*=np.sin(np.linspace(0,np.pi/2,ramp))**2
        pieces.extend([left,np.zeros(keep-2*edge,dtype=y.dtype),right])
        silences.append([(output_samples+edge)/sr,(output_samples+keep-edge)/sr])
        output_samples+=keep;cursor=b
    pieces.append(y[cursor:].copy())
    out=np.concatenate(pieces) if silences else y.copy()
    report.update(applied=bool(silences),known_silences=silences,removed_seconds=(len(y)-len(out))/sr,
                  no_global_pitch_or_tempo_change=True,voiced_regions_not_cut=True)
    return out,report

def silence_known_intervals(y,sr,regions):
    out=y.copy()
    for start,end in regions:
        a,b=round(start*sr),round(end*sr)
        if not 0<=a<b<=len(out):raise ValueError('Invalid known pause interval')
        n=min(round(.008*sr),(b-a)//4)
        out[a:a+n]*=np.cos(np.linspace(0,np.pi/2,n))**2
        out[a+n:b-n]=0
        out[b-n:b]*=np.sin(np.linspace(0,np.pi/2,n))**2
    return out
