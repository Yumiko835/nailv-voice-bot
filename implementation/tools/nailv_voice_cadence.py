
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
import datetime,hashlib,json,uuid
ROOT=Path(project_path(''));RELATIVE=Path('voice/previews/v2pro-cadence-20261024');VERSION='milkgreen-v2pro-cadence-v1'
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m.get('version')!=VERSION or not m.get('published_ready'):raise ValueError('停连对照尚未准备好。')
 return m
def media_files():
 m=manifest();folder=(ROOT/RELATIVE).resolve();files={}
 for s in m['samples']:
  for key,prefix in [('raw','raw-'),('playback','')]:
   p=(ROOT/s[key]).resolve()
   if p.is_relative_to(folder) and p.suffix=='.wav' and p.is_file():files[prefix+p.name]=p
 for key,r in m['references'].items():
  p=Path(r['playback']).resolve()
  if p.is_relative_to(folder/'references') and p.suffix=='.wav' and p.is_file():files['reference-'+key+'.wav']=p
 return files
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试听版本已变，请刷新。')
 for key,valid in [('preferred',{'A','B','C','D','none','unsure'}),('naturalness',{'better','same','worse','unsure'}),('conversation',{'original','lighter','mixed','none','unsure'})]:
  if not isinstance(data.get(key),str) or data[key] not in valid:raise ValueError('请完成三项实际试听判断。')
 issues=data.get('issues');valid={'pause','drawn','intonation','diction','timbre','nasal','metallic'}
 if not isinstance(issues,list) or any(not isinstance(x,str) or x not in valid for x in issues) or len(issues)!=len(set(issues)):raise ValueError('问题选项无效。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('意见请控制在2000字以内。')
 return {k:data[k] for k in ['preferred','naturalness','conversation','issues']}|{'notes':notes}
def save_review(data):
 choices=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12]
 record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user cadence audition form','choices':choices,'manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{s['id']:s['playback_sha256'] for s in m['samples']},'scope':'User listening only; no automatic QQ/live deployment or training-label certification.'}
 dest=ROOT/'review'/VERSION;dest.mkdir(parents=True,exist_ok=True);(dest/(identifier+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return identifier
