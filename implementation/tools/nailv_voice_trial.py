
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
ROOT=Path(project_path(''));RELATIVE=Path('voice/previews/v2pro-trained-trial-20261024');VERSION='milkgreen-v2pro-trained-trial-v1'
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m.get('version')!=VERSION or not m.get('published_ready'):raise ValueError('训练试音尚未准备好。')
 return m
def sampling_controls():
 p=ROOT/RELATIVE/'parameter-control/manifest.json'
 if not p.is_file():return None
 m=json.loads(p.read_text(encoding='utf-8'))
 return m if m.get('version')=='milkgreen-official-sampling-control-v1' and m.get('auxiliary_asr_complete') else None
def media_files():
 m=manifest();root=(ROOT/RELATIVE).resolve();files={}
 for r in m['samples']:
  for key,prefix in [('playback',''),('raw','raw-')]:
   p=(ROOT/r[key]).resolve()
   if p.is_relative_to(root) and p.suffix=='.wav' and p.is_file():files[prefix+p.name]=p
 for key,name in [('playback','reference.wav'),('path','reference-original.wav')]:
  p=Path(m['reference'][key]).resolve()
  if p.is_relative_to(root/'references') and p.suffix=='.wav' and p.is_file():files[name]=p
 control=sampling_controls()
 if control:
  for r in control['samples']:
   for key,prefix in [('playback',''),('raw','raw-')]:
    p=(ROOT/r[key]).resolve()
    if p.is_relative_to(root/'parameter-control') and p.suffix=='.wav' and p.is_file():files[prefix+p.name]=p
 return files
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试听版本已变，请刷新。')
 if not isinstance(data.get('preferred'),str) or data['preferred'] not in {'base','voice','semantic','both','params42','params0','none','unsure'}:raise ValueError('请选择相对最好的一组，也可以选都不合适。')
 if data['preferred'].startswith('params') and sampling_controls() is None:raise ValueError('默认采样对照尚未准备好。')
 if not isinstance(data.get('change'),str) or data['change'] not in {'closer','same','worse','unsure'}:raise ValueError('请选择训练前后的总体变化。')
 if not isinstance(data.get('consistency'),str) or data['consistency'] not in {'stable','unstable','unsure'}:raise ValueError('请选择同一组两句话的声线是否稳定。')
 issues=data.get('issues');valid={'nasal','diction','pitch','pace','pause','accent','metallic'}
 if not isinstance(issues,list) or any(not isinstance(x,str) or x not in valid for x in issues) or len(issues)!=len(set(issues)):raise ValueError('问题选项无效。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('补充意见请控制在2000字以内。')
 return {k:data[k] for k in ['preferred','change','consistency','issues']}|{'notes':notes}
def save_review(data):
 choices=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12];record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user trained-trial audition form','choices':choices,'manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{r['id']:r['playback_sha256'] for r in m['samples']},'scope':'Listener judgment only, not automatic deployment or human certification of all ASR training labels.'};control=sampling_controls()
 if control:record['sampling_controls_sha256']=hashlib.sha256((ROOT/RELATIVE/'parameter-control/manifest.json').read_bytes()).hexdigest();record['sampling_control_sample_sha256']={r['id']:r['playback_sha256'] for r in control['samples']}
 folder=ROOT/'review/voice-preview-v2pro-trained-trial-v1';folder.mkdir(parents=True,exist_ok=True);(folder/(identifier+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return identifier
