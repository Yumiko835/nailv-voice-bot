
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
import subprocess
PY=G/'.venv/Scripts/python.exe';HERE=Path(__file__).parent
assert read(T/'training-receipt.json')['epochs_completed']==10
def run(mode,batch):
 log=T/'logs'/('stage2-'+mode+'-batch'+str(batch)+'.log')
 with log.open('w',encoding='utf-8') as stream:r=subprocess.run([str(PY),'-B','-X','utf8',str(HERE/'train_stage2.py'),mode,'--batch',str(batch)],stdout=stream,stderr=subprocess.STDOUT,cwd=T,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 return r.returncode,log
batch=1
rc,log=run('smoke',batch)
if rc:
 text=log.read_text(encoding='utf-8',errors='replace')
 if 'out of memory' in text.lower():batch=1;status('proplus-training-memory-adjustment',batch_size=1,reason='Own smoke process exceeded available CUDA memory; no other apps stopped.');rc,log=run('smoke',batch)
 if rc:raise RuntimeError('Stage2 smoke failed: '+str(log)+'\n'+log.read_text(encoding='utf-8',errors='replace')[-3000:])
receipt=read(T/'stage2-smoke-receipt.json');assert receipt['weights_changed']
status('proplus-acoustic-smoke-passed',batch_size=batch,gpu_peak_allocated_mib=receipt['gpu_peak_allocated_mib'])
rc,log=run('train',batch)
if rc:raise RuntimeError('Stage2 full training failed: '+str(log)+'\n'+log.read_text(encoding='utf-8',errors='replace')[-3000:])
assert read(T/'stage2-training-receipt.json')['epochs_completed']==10
