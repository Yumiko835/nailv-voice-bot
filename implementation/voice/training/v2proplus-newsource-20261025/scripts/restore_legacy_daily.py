
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
import numpy as np,soundfile as sf
sys.path.insert(0,str(T/'scripts'));from reference_micro_gate import make_plan
C=A/'karaoke-reference-context-20261025';pool=read(C/'listening.json');record=next(r for r in pool['samples'] if r['id']=='ref-daily');case=read(C/'separation.json')[record['candidate_id']];c=case['candidate'];src=Path(case['primary']['path']);path=T/'prompts/source/daily_legacy.wav';shutil.copy2(src,path);x,sr=sf.read(path,dtype='float32');words=read(C/'checks-whisper.json')[c['id']+'-primary']['words'];vad=read(C/'microgate-vad.json')[c['id']]['spans'];planpath=T/'prompts/plans/daily_legacy.json';write(planpath,make_plan(x,sr,words,vad,sha(src)))
bankpath=T/'prompts/manifest.json';bank=read(bankpath);bank['prompts']['daily']=c|{'id':'daily_legacy','style':'daily','label':'日常闲聊（外币／行李箱）','path':str(path),'sha256':sha(path),'micro_gate_plan':{'path':str(planpath),'sha256':sha(planpath)},'human_emotion_verified':True,'human_reference_audio_accepted':True,'provenance_reference':str(src),'review_source':'Explicit clarified user choice: 更早那段：然后可能还要放一些外币啊什么的……行李箱里面一点也不方便','final_proplus_synthesis_human_approved':False};bank['daily_emotion_provisional']=False;bank['confirmed_recently']=['daily_legacy','gentle_a','surprised_b'];write(bankpath,bank)
write(T/'prompts/daily-choice-user-feedback-corrected.json',{'source':'Explicit user clarification','choice':'legacy daily: 外币／行李箱','candidate_id':c['id'],'reference_sha256':sha(path),'supersedes_daily_b_choice':True,'source_audio_and_dataset_unchanged':True});print(json.dumps({'daily':'daily_legacy','text':c['text']},ensure_ascii=False))
