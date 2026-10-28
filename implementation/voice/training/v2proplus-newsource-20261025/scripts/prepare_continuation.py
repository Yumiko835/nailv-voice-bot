"""Create a bounded acoustic-only continuation from the original full e10 state."""

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
C=T/'continuation-e10to14-20261025';C.mkdir(exist_ok=True)
for sub in ['checkpoints','logs','scripts','configs','generated']:(C/sub).mkdir(exist_ok=True)
assert not (C/'training-receipt.json').exists(),'This continuation is already complete.'
selection=read(T/'selected-models.json');assert selection['gpt']['epoch']==6 and selection['sovits_epoch']==10
if not (C/'before-selected-models.json').exists():
 shutil.copy2(T/'selected-models.json',C/'before-selected-models.json');shutil.copy2(T/'deployment.json',C/'before-deployment.json')
selection['gpt_selection_basis']='User selected this newly trained ProPlus GPT e6 on2026-10-25: e6/e10 sounded similar; keep e6. Independent of old V5 weights.'
selection['gpt_user_locked']=True;write(T/'selected-models.json',selection)
deployment=read(T/'deployment.json');deployment['models']=selection;write(T/'deployment.json',deployment)
write(C/'protected-hashes.json',{str(p):sha(p) for p in [T/'logs/stage2/latest-resume.pt',T/'dataset/manifest.json',T/'prompts/manifest.json',Path(selection['gpt']['path']),*[Path(r['path']) for r in read(T/'stage2-training-receipt.json')['exports']]]})
source=(Path(__file__).parent/'train_stage2.py').read_text(encoding='utf-8')
def replace(old,new):
 global source
 assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
replace("assert read(T/'feature-verification.json')['ready'];", "C=T/'continuation-e10to14-20261025'\nassert read(T/'selected-models.json')['gpt_user_locked'] and read(T/'selected-models.json')['gpt']['epoch']==6\nassert read(T/'feature-verification.json')['ready'];")
replace("epochs=1 if smoke else 10", "epochs=1 if smoke else 14")
replace("name='milkgreen-proplus',version='v2ProPlus',save_weight_dir=str(T/'checkpoints'/('smoke' if smoke else 'sovits'))", "name='milkgreen-proplus-continuation',version='v2ProPlus',save_weight_dir=str(C/'checkpoints')")
replace("write(T/'configs'/('stage2-'+a.mode+'.json'),config)", "write(C/'configs'/('stage2-'+a.mode+'.json'),config)")
replace("resume=T/'logs/stage2/latest-resume.pt'", "resume=C/'logs/latest-resume.pt';resume_source=resume if resume.exists() else T/'logs/stage2/latest-resume.pt'")
replace("if not smoke and resume.exists():", "if not smoke and resume_source.exists():")
replace("ck=torch.load(resume,map_location='cpu',weights_only=False)", "ck=torch.load(resume_source,map_location='cpu',weights_only=False)")
replace("del ck;gc.collect()", "del ck;gc.collect();assert start in [11,13,15],start;print(json.dumps({'resuming_from_epoch':start-1,'end_epoch':14,'GPT_fixed_epoch':6,'actual_lr_g':optim_g.param_groups[0]['lr'],'actual_lr_d':optim_d.param_groups[0]['lr'],'RNG_note':'Original e10 did not save RNG state; use a new reproducible continuation shuffle, not a bit-identical uninterrupted run.'}),flush=True)")
replace("write(T/('history-stage2-smoke.json' if smoke else 'history-stage2.json'),history)", "write(C/'history.json',history)")
replace("name='milkgreen-proplus'+('-smoke' if smoke else '')+'-e'+str(epoch)", "name='milkgreen-proplus-continued-e'+str(epoch)")
replace("write(T/('stage2-smoke-receipt.json' if smoke else 'stage2-training-receipt.json'),receipt)", "receipt.update(started_from_epoch=10,additional_epochs=4,gpt_fixed_epoch=6,gpt_retrained=False,training_data_refiltered=False,original_resume_preserved=True);write(C/'training-receipt.json',receipt)")
ast.parse(source);(C/'scripts/continue_stage2.py').write_text(source,encoding='utf-8')
# common.py is imported from this project's scripts, while all writes above have
# been moved to this branch. Original resume and model exports are never replaced.
shutil.copy2(Path(__file__).parent/'common.py',C/'scripts/common.py')
write(C/'plan.json',{'scope':'Acoustic Stage2 only, original293 training clips; GPT user locked to6','start_epoch':10,'end_epoch':14,'save_epochs':[12,14],'batch_size':1,'learning_rate_policy':'Keep loaded e10 optimizer learning rates and original exponential schedule; no additional LR variable.','original_resume_sha256':sha(T/'logs/stage2/latest-resume.pt'),'dataset_sha256':sha(T/'dataset/manifest.json'),'source_trainer_sha256':sha(Path(__file__).parent/'train_stage2.py'),'generated_trainer_sha256':sha(C/'scripts/continue_stage2.py'),'original_epochs_overwritten':False,'human_quality_verified':False})
print(str(C/'scripts/continue_stage2.py'))
