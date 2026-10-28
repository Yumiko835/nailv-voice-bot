
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
import shutil,ast
O=T/'inference-diagnosis-20261025';backup=O/'before';backup.mkdir(exist_ok=True);here=Path(__file__).parent
for path in [T/'listening.json',T/'selected-models.json',T/'deployment.json',T/'scripts/synthesize.py',T/'scripts/nailv_audio_export.py',ROOT/'tools/nailv_proplus_voice.py',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html']:
 target=backup/path.name
 if not target.exists():shutil.copy2(path,target)
rows=read(T/'listening.json')['samples'];repair=[{'id':r['id'],'text':r['text'],'style':r['style'],'seed':42,'repetition_penalty':1.35} for r in rows if r['settings']['repetition_penalty']!=1.35];assert len(repair)==8
write(O/'repair-requests.json',{'samples':repair});feedback=read(O/'user-feedback.json');feedback['controlled_acoustic_listening_order']=['e10','e2','official'];feedback['additional_training_requested']=False;feedback['gpt_epoch_question']='New ProPlus e6 is an automatic provisional choice among freshly trained checkpoints, not an old V5 weight. All five exports now compared without retraining.';write(O/'user-feedback.json',feedback)
for name in ['synthesize.py','nailv_audio_export.py']:
 ast.parse((here/name).read_text(encoding='utf-8'));shutil.copy2(here/name,T/'scripts'/name)
print('Prepared8 repair requests; prior code, listening and configuration snapshotted.')
