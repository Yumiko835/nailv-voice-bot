
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
HERE=Path(__file__).parent
source=(A/'scripts/train_stage1.py').read_text(encoding='utf-8')
source=source.replace('v5dev-newsource-20261025','v2proplus-newsource-20261025').replace("version='v5dev'","version='v2ProPlus'")
source=source.replace("plan=read(T/'configs/user-training-plan.json')","plan=read(T/'training-plan.json')['GPT']")
source=source.replace("assert not list((ROOT/'review/milkgreen-newsource-v5dev-v1').glob('*.json')),'Preserve real user listening judgments: create a new version.'","assert not (T/'published.json').exists(),'Published ProPlus training is frozen.'")
source=source.replace("acoustic={str(M/'gsv-v5-pretrained'/name):sha(M/'gsv-v5-pretrained'/name) for name in ['s2Gv5dev.pth','vocoder.pth']}","acoustic={r['path']:r['sha256'] for r in read(T/'official-assets.json')['files']}")
source=source.replace('milkgreen-newsource-v5dev-stage1','milkgreen-proplus-stage1').replace('milkgreen-newsource-stage1-e','milkgreen-proplus-stage1-e').replace('training-gpt-only','training-proplus-gpt').replace('official V5 Dev acoustic weights untouched','official ProPlus source weights untouched').replace('frozen official V5 acoustic model','independent V2 ProPlus project')
source=source.replace("'stage':'training-proplus-gpt',","'stage':'training-proplus-gpt','updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),")
(HERE/'train_stage1.py').write_text(source,encoding='utf-8')
print('Prepared isolated ProPlus GPT trainer; no V5 trainer/model changes.')
