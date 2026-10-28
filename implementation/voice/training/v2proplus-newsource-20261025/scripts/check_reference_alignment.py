
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
import runpy
O=T/'inference-diagnosis-20261025';bank=read(T/'prompts/manifest.json');manifest=O/'reference-alignment'/'manifest.json';write(manifest,{'samples':[{'id':key,'text':r['text'],'raw':r['path'],'raw_sha256':sha(r['path']),'seconds':r['seconds']} for key,r in bank['prompts'].items()]});sys.argv=['check_generated_text.py','--manifest',str(manifest)];runpy.run_path(str(Path(__file__).parent/'check_generated_text.py'),run_name='__main__')
