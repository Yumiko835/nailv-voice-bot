
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
import shutil
path=T/'deployment.json';old=read(path);shutil.copy2(path,T/'deployment-first-tests.json');write(path,old|{'ready':False,'reason':'Four generated samples have severe content errors and are being regenerated; trained weights remain unchanged.'});bad=['daily','excited','gentle','excited-oral'];rows=[r|{'repetition_penalty':1.35} for r in read(T/'generated/test-requests.json')['samples'] if r['id'] in bad];write(T/'generated/retry-rp135-requests.json',{'samples':rows});status('proplus-retrying-content',completed=0,total=len(bad),reason='RP1.10 generated loops/early EOS; compare official default RP1.35 on identical inputs/seed/reference.')
