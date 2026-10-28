
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
assert not (T/'training-receipt.json').exists(),'This project is already trained; preserve its models and explicit reference choices. Do not reinitialize it.'
source=A/'dataset/manifest.json';dataset=read(source);assert dataset['train_count']==293
dest=T/'dataset/manifest.json'
if dest.exists():assert sha(dest)==sha(source),'Do not replace an existing training dataset'
else:shutil.copy2(source,dest)
assets=read(ROOT/'voice/training/v2proplus-golden-20261025/official-assets.json')
for asset in assets['files']:assert sha(asset['path'])==asset['sha256']
write(T/'official-assets.json',assets|{'training_started':False,'source_receipt':'Existing pinned official Hugging Face LFS verification; local hashes rechecked.'})
protected=read(A/'emotion_prompts-v2/protected-hashes.json')|{str(source):sha(source),str(A/'reference-microgate-20261025/manifest.json'):sha(A/'reference-microgate-20261025/manifest.json')}
protected.update({r['path']:r['sha256'] for r in assets['files']});write(T/'protected-hashes.json',protected)
for role in ['train','validation','holdout']:
 for row in dataset[role]:assert sha(row['path'])==row['sha256'] and hashlib.sha256(row['text'].encode()).hexdigest()==row['text_sha256']
approved=read(A/'synthesis-diagnosis-20261025/reference-selection.json');old=read(A/'reference-microgate-20261025/manifest.json');prompts=approved['prompts']|{'daily':old['candidates']['daily_b']|{'human_emotion_verified':True,'human_reference_audio_accepted':True,'emotion_status':'User explicitly accepted reusing the last rejected daily B for the ProPlus project.'}};alternates=old['alternates']
def copy_prompt(row):
 path=T/'prompts/source'/(row['id']+'.wav');shutil.copy2(row['path'],path);assert sha(path)==row['sha256'];plan=T/'prompts/plans'/(row['id']+'.json');shutil.copy2(row['micro_gate_plan']['path'],plan)
 return row|{'path':str(path),'micro_gate_plan':{'path':str(plan),'sha256':sha(plan)},'provenance_reference':row['path'],'final_proplus_synthesis_human_approved':False}
bank={'version':'proplus-reused-emotion-pool-v1','prompts':{k:copy_prompt(v) for k,v in prompts.items()},'alternates':{k:copy_prompt(v) for k,v in alternates.items()},'daily_emotion_provisional':False,'reselected_audio':False,'confirmed_recently':['daily_b','gentle_a','surprised_b'],'source_selection':str(A/'synthesis-diagnosis-20261025/reference-selection.json')};write(T/'prompts/manifest.json',bank)
for name in ['emotion_routing.py','nailv_connected_frontend.py','reference_micro_gate.py']:
 shutil.copy2(A/'scripts'/name,T/'scripts'/name)
plan={'version':'v2ProPlus','train_count':293,'train_minutes':dataset['train_minutes'],'source_dataset_sha256':sha(source),'refiltered_or_retranscribed':False,'GPT':{'epochs':10,'save_interval':2,'batch_size':1,'gradient_accumulation':4,'learning_rate':{'initial':1e-5,'peak':3e-4,'end':3e-5}},'SoVITS':{'epochs':10,'save_interval':2,'batch_size':2,'learning_rate':1e-4,'text_low_lr_rate':.4,'precision':'BF16 autocast, FP32 mel loss, finite-gradient checks','segment_samples':20480,'official_quantizer_frozen':True},'emotion_reference_count':len(prompts)+len(alternates),'official_assets':assets,'all_training_source_files_unchanged':True}
write(T/'training-plan.json',plan)
for p in Path(__file__).parent.iterdir():
 if p.suffix in ['.py','.js']:shutil.copy2(p,T/'scripts'/p.name)
status('preparing-proplus-features',train_count=293,train_minutes=dataset['train_minutes'],emotion_reference_count=11,GPT_epochs=10,SoVITS_epochs=10,source_dataset_reused_exactly=True)
