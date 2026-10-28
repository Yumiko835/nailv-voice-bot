"""Persistent CPU critic, isolated from the GPT/HiFT torch and CUDA runtime."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import faulthandler
import json
import os
import sys
import traceback
from pathlib import Path

faulthandler.enable(all_threads=True)
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
ROOT=Path(project_path(''))
R3=ROOT/'runtime/cosyvoice3';OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge'
sys.path.insert(0,str(R3/'scripts'))
import lean_sensevoice
lean_sensevoice.install()
import audio_critic as ac
import psutil

def emit(data):
    print(json.dumps(data,ensure_ascii=False,allow_nan=False),flush=True)

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

critic=ac.Critic()
bank=ac.read(ac.O/'prompts/manifest.json')['prompts']
anchors=[ac.np.asarray(critic.file(item['path'],item['text'])['embedding']) for item in bank.values()]
within=[]
for i,a in enumerate(anchors):
    centroid=ac.np.mean([v for j,v in enumerate(anchors) if j!=i],axis=0)
    centroid/=ac.np.linalg.norm(centroid);within.append(float(a@centroid))
threshold=max(-1.,float(ac.np.percentile(within,5))-.12)
emit({'event':'ready','device':'independent CPU critic','pid':os.getpid()})
for line in sys.stdin:
    try:
        request=json.loads(line)
        if request.get('op')=='quit':emit({'event':'stopped'});break
        folder=Path(request['folder']).resolve()
        if not folder.is_relative_to((OUT/'runs').resolve()):raise ValueError('Folder outside voice output')
        sample=ac.read(folder/'manifest.json')['samples'][0]
        result=ac.assess(critic,sample,bank[sample['style']],anchors,threshold)
        target=folder/'critic'
        write(target/'details.json',{sample['id']:[result]})
        write(target/'calibration.json',{'conservative_threshold':threshold,'references':list(bank),'not_a_validated_personality_threshold':True})
        write(target/'ranking.json',{'ranking':ac.rank_results({sample['id']:[result]}),'device':'CPU','unvalidated_proxies':True})
        write(folder/'critic.json',{'device':'independent CPU process','assessment':result,'flags_advisory':True,'human_quality_verified':False})
        emit({'event':'result','result':{'scores':result['scores'],'flags':result['review_flags'],
              'recognized':result['content']['recognized'],'RSS_MiB':psutil.Process().memory_info().rss/1024**2,
              'cuda_initialized':ac.torch.cuda.is_initialized()}})
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        emit({'event':'error','error':type(exc).__name__+': '+str(exc)[:200]})
