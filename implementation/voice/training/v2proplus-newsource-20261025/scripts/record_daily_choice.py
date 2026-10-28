
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
path=T/'prompts/manifest.json';bank=read(path);backup=T/'prompts/before-daily-b-user-choice.json'
if not backup.exists():shutil.copy2(path,backup)
row=read(A/'reference-microgate-20261025/manifest.json')['candidates']['daily_b'];source=T/'prompts/source/daily_b.wav';shutil.copy2(row['path'],source);plan=T/'prompts/plans/daily_b.json';shutil.copy2(row['micro_gate_plan']['path'],plan)
bank['prompts']['daily']=row|{'path':str(source),'micro_gate_plan':{'path':str(plan),'sha256':sha(plan)},'provenance_reference':row['path'],'human_emotion_verified':True,'human_reference_audio_accepted':True,'emotion_status':'Explicit user: 日常闲聊也可以用之前最后淘汰的那一版','final_proplus_synthesis_human_approved':False};bank['daily_emotion_provisional']=False;bank['confirmed_recently']=['daily_b','gentle_a','surprised_b'];write(path,bank)
write(T/'prompts/daily-choice-user-feedback.json',{'source':'Explicit user chat instruction','text':'日常闲聊也可以用之前最后淘汰的那一版','resolved_as':'daily_b: the clean but deliberately slower reading-style reference most recently rejected','reference_sha256':row['sha256'],'previous_V5_synthesis_failure_not_treated_as_ProPlus_failure':True,'dataset_changed':False})
print(json.dumps({'daily_reference':'daily_b','dataset_changed':False},ensure_ascii=False))
