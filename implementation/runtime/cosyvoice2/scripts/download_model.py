
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from pathlib import Path
import os,json,hashlib,time
ROOT=Path(project_path(''));R=ROOT/'runtime/cosyvoice2';O=ROOT/'voice/comparison/cosyvoice2-20261026'
os.environ.update(HF_HOME=str(R/'cache/hf'),HF_HUB_CACHE=str(R/'cache/hf/hub'),HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',HF_HUB_DOWNLOAD_TIMEOUT='120',HF_HUB_ETAG_TIMEOUT='30',TEMP=str(R/'cache/tmp'),TMP=str(R/'cache/tmp'))
from huggingface_hub import hf_hub_download
manifest=json.loads((R/'required-model-files.json').read_text(encoding='utf-8'));dest=R/'models/CosyVoice2-0.5B';dest.mkdir(parents=True,exist_ok=True)
receipts=[]
for i,row in enumerate(manifest['files']):
    file=hf_hub_download(repo_id=manifest['repository'],filename=row['rfilename'],revision=manifest['revision'],local_dir=dest,token=False)
    p=Path(file)
    with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    expected=row.get('lfs',{}).get('sha256') or row.get('lfs',{}).get('oid')
    if expected:assert digest==expected.removeprefix('sha256:')
    receipts.append({'path':str(p),'name':row['rfilename'],'bytes':p.stat().st_size,'sha256':digest,'published_lfs_sha256':expected,'published_hash_verified':bool(expected)})
    (R/'download-receipt.json').write_text(json.dumps({'repository':manifest['repository'],'revision':manifest['revision'],'files':receipts},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'completed':i+1,'total':len(manifest['files']),'file':row['rfilename'],'bytes':p.stat().st_size},ensure_ascii=False),flush=True)
print('All required official CosyVoice2 weights downloaded and recorded.',flush=True)
