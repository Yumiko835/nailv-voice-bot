"""Project-local punctuation segmentation and bounded acoustic tail processing."""

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
from scipy import signal

SPLITS=set('，、。！？；：,.!?;:\n…')

def cut_punc(text):
    chunks=[];buf='';start=0
    for i,char in enumerate(text):
        buf+=char
        decimal=char=='.' and i>0 and i+1<len(text) and text[i-1].isdigit() and text[i+1].isdigit()
        if char in SPLITS and not decimal:
            spoken=buf.rstrip('，、。！？；：,.!?;:\n…').strip()
            if re.search(r'[\w\u3400-\u9fff]',spoken):
                terminal='？' if char in '?？' else '！' if char in '!！' else '。'
                chunks.append({'source':buf,'source_start':start,'source_end':i+1,'spoken':spoken,'inference_text':spoken+terminal,'boundary':char})
            buf='';start=i+1
    if re.search(r'[\w\u3400-\u9fff]',buf):
        chunks.append({'source':buf,'source_start':start,'source_end':len(text),'spoken':buf.strip(),'inference_text':buf.strip()+'。','boundary':''})
    content=lambda x:re.sub(r'[^\w\u3400-\u9fff]','',x)
    assert content(''.join(c['spoken'] for c in chunks))==content(text),'Spoken content lost during splitting'
    if not chunks:raise ValueError('没有可朗读的文字。')
    return chunks

def tail_token_plan(codes,trigger=12,keep=8):
    if not codes:return {'original_tokens':0,'retained_tokens':0,'terminal_run':0,'removed_tokens':0}
    last=codes[-1];run=1
    for x in reversed(codes[:-1]):
        if x!=last:break
        run+=1
    remove=run-keep if run>=trigger else 0
    return {'original_tokens':len(codes),'retained_tokens':len(codes)-remove,
        'terminal_run':run,'removed_tokens':remove,'trigger_frames':trigger,'keep_frames':keep,
        'scope':'Only consecutive identical IDs at the target suffix; no lexical word deduplication.'}

def _frames(y,size=640,hop=320):
    padded=np.pad(y,(size//2,size//2+hop))
    return np.lib.stride_tricks.sliding_window_view(padded,size)[::hop].copy()

def deess(y,sr=32000,reduction_db=5.):
    y=np.asarray(y,dtype=np.float32)
    if sr!=32000 or not 4<=reduction_db<=6:raise ValueError('Invalid native rate or de-esser reduction.')
    band=signal.sosfiltfilt(signal.butter(4,[4500,9000],btype='bandpass',fs=sr,output='sos'),y)
    low=signal.sosfiltfilt(signal.butter(4,[80,800],btype='bandpass',fs=sr,output='sos'),y)
    f=_frames(y);b=_frames(band);l=_frames(low)
    energy=np.mean(f*f,axis=1);high=np.mean(b*b,axis=1)/(energy+1e-15);lowratio=np.mean(l*l,axis=1)/(energy+1e-15)
    zcr=np.mean(np.diff(np.signbit(f),axis=1),axis=1)
    # These are acoustic candidates, not proof that a frame is pure breathing.
    detected=(zcr>.16)&(lowratio<.25)&(high>.18)&(energy>1e-10)
    amount=np.zeros(len(detected),np.float64);previous=0.
    for i,target in enumerate(detected.astype(float)):
        coeff=np.exp(-.01/(.008 if target>previous else .05))
        previous=coeff*previous+(1-coeff)*target;amount[i]=previous
    control=np.interp(np.arange(len(y))/sr,np.arange(len(amount))*.01,amount)
    gain=10**(-reduction_db*control/20)
    z=(y+band*(gain-1)).astype(np.float32)
    return z,{'algorithm':'4500-9000Hz split-band dynamic attenuation','maximum_band_reduction_db':reduction_db,
        'candidate_frame_fraction':float(np.mean(detected)),'actual_peak_band_reduction_db':float(np.max(reduction_db*control)),
        'zero_crossing_threshold':.16,'low_80_800hz_energy_ratio_ceiling':.25,'high_band_energy_ratio_floor':.18,
        'attack_ms':8,'release_ms':50,'phase_delay_samples':0,
        'classification_is_acoustic_not_phonetic':True,'may_soften_unvoiced_consonants':True}

def tail_envelope(y,sr=32000,fade_ms=100.):
    y=np.asarray(y,dtype=np.float32)
    if sr!=32000 or not 80<=fade_ms<=120:raise ValueError('Tail fade must be 80-120ms at native rate.')
    # Conservative floor and 40ms hangover protect quiet final consonants.
    size=160;p=np.pad(y,(0,(-len(y))%size));rms=np.sqrt(np.mean(p.reshape(-1,size)**2,axis=1))
    present=rms[rms>1e-7]
    speech=float(np.percentile(present,90)) if len(present) else 0.
    threshold=max(10**(-60/20),speech*10**(-32/20))
    voiced=np.flatnonzero(rms>threshold)
    if not len(voiced):raise ValueError('短句缺少可确认的有效能量，保留原音待检查。')
    detected=min(len(y),int((voiced[-1]+1)*size));end=min(len(y),detected+round(sr*.04))
    width=min(round(sr*fade_ms/1000),end);start=end-width
    ramp=(.5-.5*np.cos(np.linspace(0,np.pi,width))).astype(np.float32)
    fade=np.ones(len(y),np.float32);fade[start:end]=1-ramp;fade[end:]=0
    # The lowpass exists only as a zero-phase candidate blended in the final
    # 100ms; earlier words are bit-identical and are not low-pass filtered.
    low=signal.sosfiltfilt(signal.butter(4,5000,btype='lowpass',fs=sr,output='sos'),y)
    mix=np.zeros(len(y),np.float32);mix[start:end]=ramp;mix[end:]=1
    z=((y+mix*(low-y))*fade).astype(np.float32)
    assert np.array_equal(z[:start],y[:start]) and len(z)==len(y)
    return z,{'algorithm':'Cosine tail envelope + synchronized 5kHz dynamic lowpass blend',
        'fade_ms':fade_ms,'last_energy_frame_end_sample':detected,'energy_threshold_dbfs':float(20*np.log10(threshold)),
        'energy_detection_is_not_word_alignment':True,'hangover_ms':40,'fade_start_sample':start,'fade_end_sample':end,
        'lowpass_cutoff_hz':5000,'unchanged_before_fade':True,'removed_samples':0,
        'zeros_after_detected_end':len(y)-end,'may_attenuate_very_quiet_final_consonants':True}

def process_clause(y,sr=32000):
    breath,deesser=deess(y,sr,5.)
    z,tail=tail_envelope(breath,sr,100.)
    assert len(z)==len(y) and np.isfinite(z).all()
    return z,breath,{'deesser':deesser,'tail':tail,'sample_rate':sr,'resampled':False,
        'pitch_shifted':False,'time_stretched':False,'human_quality_verified':False}
