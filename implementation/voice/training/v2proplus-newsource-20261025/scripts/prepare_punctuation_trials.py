
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
from punctuation_audio_patch import cut_punc,tail_token_plan,process_clause,deess
import numpy as np
from scipy import signal
O=T/'punctuation-tail-patch-20261025';O.mkdir(exist_ok=True)
assert not (O/'primitive-verification.json').exists()
sel=read(T/'selected-models.json');assert sel['gpt']['epoch']==6 and sel['sovits_epoch']==14
for k in ['gpt','sovits']:assert sha(sel[k]['path'])==sel[k]['sha256']
write(O/'selected-models-before.json',sel);write(O/'deployment-before.json',read(T/'deployment.json'))
write(O/'feedback.json',{'user_requested':'Strict punctuation clauses,250ms clean gaps,top_k15,temperature0.8,repetition_penalty1.35; suffix repeated-ID trim;100ms cosine+dynamic5kHz LP;4.5-9kHz5dB deesser. No training.','previous_treatments_user_feedback':'没什么效果','not_a_confirmed_single_cause':'Punctuation and processing are requested hypotheses to test.'})
tests=[
 ('01','慢慢来与句尾','gentle','慢慢来，慢慢来，先把这句话说清楚。'),
 ('02','妈妈妈妈与连读','daily','妈妈妈妈，这么喜欢叫妈妈吗？'),
 ('03','自然接话','daily','先别着急，你慢慢说，我听着呢。'),
 ('04','口癖与短语','daily','那个，等一下啊，我先想想这个东西放哪儿了。'),
 ('05','短句停顿','daily','行吧，那就这么说好了。剩下的事情，我们回头再商量。'),
 ('06','温柔与换气','gentle','累了就先歇一会儿吧，水就放在旁边，不用急着把事情都做完。'),
 ('07','日常休息','daily','你先休息一下，剩下的事情，等明天再说吧。'),
 ('08','问句与解释','daily','是这个，还是那个？我说的是左边，不是右边。'),
 ('09','各类标点与轻声','daily','我想好了：茶、咖啡，都行；你挑吧！'),
]
rows=[{'id':'punc-'+n,'audition_label':n+' · '+label,'text':text,'style':style,'seed':42,'temperature':.8} for n,label,style,text in tests]
write(O/'requests.json',{'samples':rows});write(O/'reference-manifest.json',read(T/'prompts/manifest.json'))
assert [c['spoken'] for c in cut_punc('慢慢来，妈妈妈妈。')]==['慢慢来','妈妈妈妈']
assert len(cut_punc('你说：茶、咖啡，随便；好吗？可以！'))==6
assert tail_token_plan([1,2,3]+[7]*27)['removed_tokens']==19
assert tail_token_plan([1,2,1,2,1,2])['removed_tokens']==0
assert cut_punc('价格是3.14元。')[0]['spoken']=='价格是3.14元'
sr=32000;rng=np.random.default_rng(20261025);seconds=3
t=np.arange(sr*seconds)/sr
tone=(.15*np.sin(2*np.pi*220*t)+.05*np.sin(2*np.pi*440*t)).astype(np.float32)
noise=signal.sosfiltfilt(signal.butter(6,[4500,9000],fs=sr,btype='bandpass',output='sos'),rng.normal(0,.03,len(t)))
x=tone.copy();x[sr:2*sr]=noise[sr:2*sr]
z,meta=deess(x)
inner=slice(round(sr*1.2),round(sr*1.8));delta=float(10*np.log10(np.sum(z[inner]**2)/np.sum(x[inner]**2)))
assert -5.5<delta<-3.5 and meta['actual_peak_band_reduction_db']>4.9
out,_,processing=process_clause(x);assert len(out)==len(x) and np.isfinite(out).all() and out[-1]==0
write(O/'primitive-verification.json',{'strict_split_word_preservation':True,'decimal_preserved':True,
 'normal_repeated_sequence_not_trimmed':True,'abnormal_suffix27_retains8':True,
 'synthetic_highband_noise_reduction_db':delta,'finite_same_sample_count':True,
 'synthetic_tests_do_not_prove_speech_quality':True})
status('proplus-comparing-continuation',activity='punctuation-tail-patches',completed=0,total=len(rows))
print(json.dumps({'sentences':len(rows),'clauses':sum(len(cut_punc(r['text'])) for r in rows),'synthetic_deesser_db':delta},ensure_ascii=False))
