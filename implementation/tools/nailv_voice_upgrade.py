"""User-selected standard v2Pro auditions and versioned subjective ratings."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import json,hashlib,uuid,datetime
from pathlib import Path
ROOT=Path(project_path(''));RELATIVE=Path('voice/previews/backend-v2-20261024');VERSION='milkgreen-v2pro-preview-v2'
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m['version']!=VERSION or m['backend']!='GPT-SoVITS v2Pro' or len(m['samples'])!=6:raise ValueError('v2Pro试音尚未准备完整。')
 return m
def media_files():
 m=manifest();folder=(ROOT/RELATIVE).resolve();files={}
 for row in m['samples']:
  for key,prefix in [('playback',''),('raw','raw-')]:
   path=(ROOT/row[key]).resolve()
   if path.is_relative_to(folder) and path.suffix=='.wav' and path.is_file():files[prefix+path.name]=path
 for key,name in [('native_48k','reference-native.wav'),('legacy_16k','reference-old.wav')]:
  path=Path(m['references'][key]['path']).resolve()
  allowed=[folder/'references',(ROOT/'voice/previews/reference-v1-20261024/references').resolve()]
  if any(path.is_relative_to(a) for a in allowed) and path.suffix=='.wav' and path.is_file():files[name]=path
 return files
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试音版本已变，请刷新。')
 fields={'reference_state':{'typical','different_state','unsure'},'reference_choice':{'native_48k','legacy_16k','none','tie'},'noise_change':{'less','same','more','unsure'}}
 for name,options in fields.items():
  if not isinstance(data.get(name),str) or data[name] not in options:raise ValueError('请完成三个试听判断，也可以选择不确定或都不像。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('补充意见请控制在2000字以内。')
 return {name:data[name] for name in fields}|{'notes':notes}
def save_review(data):
 choices=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12];record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit local v2Pro audition form submission','choices':choices,'manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{x['id']:x['playback_sha256'] for x in m['samples']},'scope':'Subjective reference-state, timbre and electrical-sound judgments. Not reference-word confirmation, automatic quality approval or voice training.'};folder=ROOT/'review/voice-preview-v2pro-v2';folder.mkdir(parents=True,exist_ok=True);(folder/(identifier+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return identifier
