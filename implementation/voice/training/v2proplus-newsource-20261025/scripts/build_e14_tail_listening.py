
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
from tail_signal import treat_tails
from nailv_audio_export import export_native
import numpy as np, soundfile as sf

O=T/'e14-tail-repair-20261025'
assert not (O/'listening-v2.json').exists(), 'Preserve prior listening files.'
old={r['id']:r for r in read(T/'e14-more-sentences-20261025/manifest.json')['samples']}
new={r['id']:r for r in read(O/'guard-regression/manifest.json')['samples']}
selected=read(T/'selected-models.json');assert selected==read(O/'selected-models-before.json')
samples=[]
source_cases=[
 ('slow','B03 · 慢慢来',old['e14-more-b03'],new['tailguard-e14-more-b03']),
 ('pause','C03 · 短句与停顿',old['e14-more-c03'],new['tailguard-e14-more-c03']),
 ('breath','E04 · 温柔语气与换气',old['e14-more-e04'],new['tailguard-e14-more-e04']),
]
verification=[]
for case,title,original,base in source_cases:
    if case=='slow':
        samples.append(original|{'id':'e14-tail-listen-slow-original','case':case,'case_title':title,'label':'A · 原版（8.64秒，拖音对照）','treatment':'historical-original'})
        label='B · 循环重试后（4.00秒，不做降噪）'
    else:
        label='A · 原版（未做收尾处理）'
    samples.append(base|{'id':'e14-tail-listen-'+case+'-raw','case':case,'case_title':title,'label':label,'treatment':'unprocessed'})
    y,sr=sf.read(base['native_float'],dtype='float32');assert sr==32000
    for strength,label in [('light','轻处理'),('moderate','稍强处理')]:
        z,meta=treat_tails(y,sr,strength)
        assert meta['applied'] and len(y)==len(z) and np.isfinite(z).all()
        d=O/'postprocessed-v2'/(case+'-'+strength);d.mkdir(parents=True,exist_ok=True)
        exported=export_native(z,d)
        # Use the exact same playback gain for the whole comparison. Do not
        # make a treatment sound better by globally turning it down or up.
        gain=10**(base['playback_gain_db']/20)
        assert gain<=1 and float(np.max(np.abs(z*gain)))<.999
        sf.write(exported['playback'],np.r_[np.zeros(5120,dtype=np.float32),z*gain,np.zeros(10240,dtype=np.float32)],sr,subtype='PCM_24')
        exported.update(playback_gain_db=base['playback_gain_db'],playback_sha256=sha(exported['playback']))
        row=base|exported|{'id':'e14-tail-listen-'+case+'-'+strength,'case':case,'case_title':title,'label':('C' if case=='slow' else 'B')+' · '+label if strength=='light' else ('D' if case=='slow' else 'C')+' · '+label,'source_native_sha256':sha(base['native_float']),'treatment':meta,'no_output_denoising':False,'matched_playback_gain':True}
        samples.append(row)
        verification.append({'case':case,'strength':strength,'source_sha256':sha(base['native_float']),'output_sha256':exported['raw_sha256'],'processing':meta})
write(O/'listening-v2.json',{'samples':samples,'models':selected,'human_quality_verified':False,'postprocessing_adopted_as_default':False,'comparison_loudness':'Exact same playback gain as unprocessed source; no positive gain, pitch/time/rate edits.'})
write(O/'postprocessing-verification-v2.json',verification)
print(json.dumps({'samples':len(samples),'treatments':[{'case':r['case'],'strength':r['strength'],'protected_core_fraction':r['processing']['protected_core_fraction'],'modified_fraction':r['processing']['modified_fraction']} for r in verification]},ensure_ascii=False))
