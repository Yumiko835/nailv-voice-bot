
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
import urllib.request
O=T/'inference-diagnosis-20261025';base='http://127.0.0.1:49850'
def get(url):
 with urllib.request.urlopen(base+url,timeout=5) as response:return json.loads(response.read())
s=get('/api/voice-proplus/status');assert s['ready'] and len(s['samples'])==11 and len(s['gpt_comparison'])==10 and s['sovits_epoch']==10
verified=[]
for row in s['samples']+s['gpt_comparison']:
 with urllib.request.urlopen(urllib.request.Request(base+'/voice-proplus-media/'+row['media'],headers={'Range':'bytes=0-43'}),timeout=10) as response:
  data=response.read();assert response.status==206 and len(data)==44 and data[:4]==b'RIFF';verified.append(row['id'])
payload=json.dumps({'text':'妈妈妈妈，这么喜欢叫妈妈吗','style':'daily','temperature':.85}).encode();request=urllib.request.Request(base+'/api/voice-proplus/generate',data=payload,headers={'Content-Type':'application/json','Origin':base},method='POST')
with urllib.request.urlopen(request,timeout=10) as response:job=json.loads(response.read())
start=time.monotonic()
while job['status'] in ['pending','running']:
 assert time.monotonic()-start<240;time.sleep(.5);job=get('/api/voice-proplus/job/'+job['id'])
assert job['status']=='complete',job;result=read(T/'generated/jobs'/job['id']/'manifest.json')['samples'][0];assert result['settings']['repetition_penalty']==1.35 and result['text']=='妈妈妈妈，这么喜欢叫妈妈吗' and result['trimmed_samples']==0
verify_protected();selected=read(T/'selected-models.json')
for key in ['gpt','sovits']:assert sha(selected[key]['path'])==selected[key]['sha256']
write(O/'deployment-verification.json',{'healthy':True,'all21_media_range_requests_passed':verified,'actual_UI_generation_job':job,'actual_worker_settings':result['settings'],'models_unchanged':True,'human_electrical_artifact_resolved':False});print(json.dumps({'verified_media':len(verified),'actual_job':job,'worker_RP':result['settings']['repetition_penalty']},ensure_ascii=True))
