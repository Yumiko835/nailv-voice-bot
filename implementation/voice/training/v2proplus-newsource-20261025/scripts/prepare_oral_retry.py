
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
row=next(r for r in read(T/'generated/test-requests.json')['samples'] if r['id']=='excited-oral');samples=[row|{'id':'oral-seed'+str(seed),'seed':seed,'repetition_penalty':1.35} for seed in [73,137]];write(T/'generated/oral-retry-requests.json',{'samples':samples})
