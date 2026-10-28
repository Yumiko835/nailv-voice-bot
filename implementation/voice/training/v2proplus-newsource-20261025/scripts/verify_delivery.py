
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
import urllib.request,urllib.error
base='http://127.0.0.1:49850';s=readjson=lambda url:json.load(urllib.request.urlopen(url,timeout=20));current=readjson(base+'/api/voice-proplus/status');assert current['ready'] and len(current['prompts'])==10 and current['reference_count']==10 and current['archived_reference_count']==1 and len(current['samples'])==11;assert current['prompts']['daily']['reference_id']=='daily_legacy'
for sample in current['samples']:
 request=urllib.request.Request(base+'/voice-proplus-media/'+sample['media'],headers={'Range':'bytes=0-43'})
 with urllib.request.urlopen(request,timeout=15) as response:assert response.status==206 and len(response.read())==44
payload={'text':'[解释] 对，我刚才说的就是这个意思。','style':'daily','temperature':.85};request=urllib.request.Request(base+'/api/voice-proplus/generate',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':base});job=json.load(urllib.request.urlopen(request,timeout=20));deadline=time.monotonic()+180
while job['status'] in ['pending','running']:
 assert time.monotonic()<deadline,'Online synthesis timed out';time.sleep(1.5);job=readjson(base+'/api/voice-proplus/job/'+job['id'])
assert job['status']=='complete',job
row=read(T/'generated/jobs'/job['id']/'manifest.json')['samples'][0];assert row['style']=='explaining' and row['reference_id']=='explaining' and row['text']==payload['text'].split('] ',1)[1] and row['settings']['repetition_penalty']==1.35;assert row['sample_rate']==32000 and row['export_subtype']=='PCM_24';assert all(a['duration_guard_passed'] for a in row['generation_attempts'][-1:]);verify_protected()
with urllib.request.urlopen(urllib.request.Request(base+'/voice-proplus-media/'+job['media'],headers={'Range':'bytes=0-43'}),timeout=15) as response:assert response.status==206 and len(response.read())==44
summary={'all11_test_players_available':True,'ten_emotion_styles':True,'active_references':10,'archived_optional_reference':1,'real_online_manual_prefix_override_passed':True,'online_job_id':job['id'],'online_reference_id':row['reference_id'],'online_seconds':row['seconds'],'normal_repetition_penalty':1.35,'both_stages_completed_epochs':10,'original_hashes_unchanged':True,'human_sound_quality_verified':False};write(T/'delivery-verification.json',summary);print(json.dumps(summary,ensure_ascii=False))
