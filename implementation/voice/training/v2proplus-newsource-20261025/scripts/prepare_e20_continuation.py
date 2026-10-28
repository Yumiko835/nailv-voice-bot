"""User-requested six more acoustic epochs, preserving the completed e14 branch."""

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
P=T/'continuation-e10to14-20261025';C=T/'continuation-e14to20-20261025'
for sub in ['checkpoints','logs','scripts','configs','generated','merges']:(C/sub).mkdir(parents=True,exist_ok=True)
assert not (C/'training-receipt.json').exists(),'20-epoch continuation already complete; reuse its outputs.'
selection=read(T/'selected-models.json');assert selection['gpt']['epoch']==6 and selection['gpt_user_locked'] and selection['sovits_epoch']==14
for name in ['selected-models.json','deployment.json']:
 if not (C/('before-'+name)).exists():shutil.copy2(T/name,C/('before-'+name))
protected=[P/'logs/latest-resume.pt',T/'dataset/manifest.json',T/'prompts/manifest.json',Path(selection['gpt']['path']),*[Path(r['path']) for r in read(P/'training-receipt.json')['exports']]]
write(C/'protected-hashes.json',{str(p):sha(p) for p in protected})
write(C/'user-request.json',{'finish_acoustic_epoch':20,'start_epoch':14,'GPT_user_locked':6,'noise_scale':.5,'previous_clarity_candidates':'User reports no meaningful change. Do not adopt previous bell-EQ or precision-weight variant.','requested_experiments':['compatible acoustic checkpoint interpolation','high-shelf EQ'],'request_is_not_a_claim':'Interpolation cannot guarantee semantic properties blend linearly; EQ may raise remaining noise. Current model is ProPlus, not V5.','cloud_audio':False,'QQ':False})
source=(P/'scripts/continue_stage2.py').read_text(encoding='utf-8')
def replace(old,new):
 global source
 assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
replace("C=T/'continuation-e10to14-20261025'", "C=T/'continuation-e14to20-20261025'")
replace("epochs=1 if smoke else 14", "epochs=1 if smoke else 20")
replace("resume_source=resume if resume.exists() else T/'logs/stage2/latest-resume.pt'", "resume_source=resume if resume.exists() else T/'continuation-e10to14-20261025/logs/latest-resume.pt'")
replace("start in [11,13,15]", "start in [15,17,19,21]")
replace("'end_epoch':14", "'end_epoch':20")
replace("Original e10 did not save RNG state; use a new reproducible continuation shuffle, not a bit-identical uninterrupted run.", "Source e14 did not save RNG state; use a new reproducible continuation shuffle, not a bit-identical uninterrupted run.")
replace("receipt.update(started_from_epoch=10,additional_epochs=4", "receipt.update(started_from_epoch=14,additional_epochs=6")
# Independent deterministic shuffle for this continuation. Optimizer state and
# loaded learning rates remain the e14 values, unchanged by this script.
source=source.replace('manual_seed(20261025)','manual_seed(20261026)').replace('random.seed(20261025)','random.seed(20261026)')
ast.parse(source);(C/'scripts/continue_stage2.py').write_text(source,encoding='utf-8');shutil.copy2(Path(__file__).parent/'common.py',C/'scripts/common.py')
write(C/'plan.json',{'start_epoch':14,'end_epoch':20,'additional_epochs':6,'save_epochs':[16,18,20],'GPT_fixed_epoch':6,'batch_size':1,'train_rows':293,'dataset_sha256':sha(T/'dataset/manifest.json'),'source_e14_resume_sha256':sha(P/'logs/latest-resume.pt'),'learning_rate_policy':'Resume the complete e14 G/D optimizer state and original learning-rate decay; no new LR variable.','original_model_files_overwritten':False,'frozen_semantic_codebook':True,'experiments':{'early_checkpoint':10,'late_checkpoint_initial_candidate':20,'late_weight_ratios':[.85,.7],'high_shelf_hz':6000,'high_shelf_db':[2.,3.],'combined_initial_candidate':'70%late+30%e10, plus2dB shelf'},'human_sound_quality_verified':False})
print(str(C/'scripts/continue_stage2.py'))
