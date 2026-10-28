"""Launch only this isolated AstrBot instance; no QQ sends or model probes."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import os
import runpy
import sys
from pathlib import Path

ROOT=Path(project_path(''))
R=ROOT/'runtime/astrbot'
os.environ.update(ASTRBOT_ROOT=str(R/'app'), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                  TEMP=str(R/'tmp'), TMP=str(R/'tmp'), HF_HOME=str(ROOT/'cache/huggingface'))
if not os.environ.get('CHAT_API_KEY'):
    os.environ['CHAT_API_KEY']=(ROOT.parent.parent/secret_path("CHAT_API_KEY_FILE")).read_text(encoding='utf-8-sig').strip()
os.chdir(R/'app')
sys.path[:0]=[str(R/'scripts'),str(R/'app')]
import nailv_provider  # registers the budgeted native adapter before loading providers
sys.argv=[str(R/'app/main.py'),'--webui-dir',str(R/'app/data/dist/dist')]
runpy.run_path(str(R/'app/main.py'),run_name='__main__')
