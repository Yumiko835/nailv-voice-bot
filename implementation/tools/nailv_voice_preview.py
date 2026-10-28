"""Finite local voice auditions and explicit user ratings, independent of live TTS."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import datetime,hashlib,json,uuid
from pathlib import Path
ROOT=Path(project_path(''))
VERSION='milkgreen-voice-reference-preview-v1'
RELATIVE=Path('voice/previews/reference-v1-20261024')
def manifest():
 data=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if data['version']!=VERSION or len(data['samples'])!=6:raise ValueError('试音还没有准备完整。')
 return data
def media_files():
 data=manifest();folder=(ROOT/RELATIVE).resolve();result={}
 for sample in data['samples']:
  for key,prefix in [('playback',''),('raw','raw-')]:
   path=(ROOT/sample[key]).resolve()
   if path.is_relative_to(folder) and path.suffix=='.wav' and path.is_file():result[prefix+path.name]=path
 for ref in data['references']:
  path=(ROOT/ref['relative_path']).resolve()
  if path.is_relative_to(folder/'references') and path.suffix=='.wav' and path.is_file():result['reference-'+path.name]=path
 return result
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试听版本已变，请刷新页面。')
 valid={'A','B','C','none','tie'}
 for field in ['timbre_choice','naturalness_choice']:
  if not isinstance(data.get(field),str) or data[field] not in valid:raise ValueError('请分别选择音色和自然程度，也可选都不像或差不多。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('补充意见请控制在2000字以内。')
 return {k:data[k] for k in ['timbre_choice','naturalness_choice']}|{'notes':notes}
def save_review(data):
 votes=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12]
 record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit local audition form submission','manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{x['id']:x['playback_sha256'] for x in m['samples']},'choices':votes,'review_scope':'Subjective timbre and naturalness choices only; not reference-word verification, training approval or an automatic overall pass.'}
 folder=ROOT/'review/voice-preview-reference-v1';folder.mkdir(parents=True,exist_ok=True);path=folder/(identifier+'.json');path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return identifier
