"""JSONL broker for the previously validated standalone CPU critic entry point."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import sys,json,subprocess,os
from pathlib import Path
ROOT=Path(project_path(''))
OUT=ROOT/'voice/comparison/cosyvoice3-20261026/live-bridge'
SCRIPT=Path(__file__).resolve().parents[1]/'audio_critic.py'
def emit(d):print(json.dumps(d,ensure_ascii=False,allow_nan=False),flush=True)
emit({'event':'ready','device':'independent CPU critic'})
for line in sys.stdin:
    request=json.loads(line)
    if request.get('op')=='quit':emit({'event':'stopped'});break
    try:
        folder=Path(request['folder']).resolve();assert folder.is_relative_to((OUT/'runs').resolve())
        target=folder/'critic';target.mkdir(exist_ok=True)
        env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='-1',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        with (folder/'critic.log').open('w',encoding='utf-8') as log:
            p=subprocess.run([sys.executable,'-B',str(SCRIPT),'--manifest',str(folder/'manifest.json'),'--out',str(target)],
                stdout=log,stderr=subprocess.STDOUT,env=env,cwd=str(ROOT),timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if p.returncode:raise RuntimeError('CPU核对进程退出：'+hex(p.returncode&0xffffffff))
        details=json.loads((target/'details.json').read_text(encoding='utf-8'));result=next(iter(details.values()))[0]
        (folder/'critic.json').write_text(json.dumps({'device':'CPU only','assessment':result,'flags_advisory':True,'human_quality_verified':False},ensure_ascii=False,indent=2),encoding='utf-8')
        emit({'event':'result','result':{'scores':result['scores'],'flags':result['review_flags'],'recognized':result['content']['recognized']}})
    except Exception as exc:
        emit({'event':'error','error':str(exc)[:240]})
