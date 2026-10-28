
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
import json,hashlib,uuid,datetime
ROOT=Path(project_path(''));RELATIVE=Path('voice/previews/backend-ab-20261025');VERSION='milkgreen-two-backend-ab-v1'
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m.get('version')!=VERSION or not m.get('published_ready'):raise ValueError('模型对照还未准备好。')
 return m
def media_files():
 m=manifest();root=(ROOT/RELATIVE).resolve();files={}
 for s in m['samples']:
  for key,prefix in [('raw','raw-'),('playback','')]:
   p=(ROOT/s[key]).resolve()
   if p.is_relative_to(root) and p.suffix=='.wav' and p.is_file():files[prefix+p.name]=p
 for key,r in m['references'].items():
  for field,prefix in [('path','reference-original-'),('playback','reference-')]:
   p=Path(r[field]).resolve()
   if p.is_relative_to(root/'references') and p.suffix=='.wav' and p.is_file():files[prefix+key+'.wav']=p
 return files
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('模型对照版本已变，请刷新。')
 for key,valid in [('timbre',{'A','B','none','tie'}),('naturalness',{'A','B','none','tie'}),('consistency',{'stable','unstable','unsure'})]:
  if not isinstance(data.get(key),str) or data[key] not in valid:raise ValueError('请完成音色、自然度和声线稳定性三项判断。')
 issues=data.get('issues');valid={'slow','elongation','pitch','timbre','metallic','diction','pause'}
 if not isinstance(issues,list) or any(not isinstance(x,str) or x not in valid for x in issues) or len(issues)!=len(set(issues)):raise ValueError('问题选项无效。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('意见请控制在2000字以内。')
 return {k:data[k] for k in ['timbre','naturalness','consistency','issues']}|{'notes':notes}
def save_review(data):
 choices=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12];r={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user two-backend comparison form','choices':choices,'manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{s['id']:s['playback_sha256'] for s in m['samples']},'label_mapping':m['label_mapping'],'scope':'Synthesized timbre and naturalness listening judgment, not automatic deployment or training approval.'};folder=ROOT/'review'/VERSION;folder.mkdir(parents=True,exist_ok=True);temp=folder/(identifier+'.tmp');temp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(folder/(identifier+'.json'));return identifier
