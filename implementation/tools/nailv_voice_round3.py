"""Versioned broad audition media and explicit listener/label feedback."""

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
import json,uuid,hashlib,datetime
ROOT=Path(project_path(''));RELATIVE=Path('voice/previews/v2pro-round3-20261024');VERSION='milkgreen-v2pro-round3'
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m.get('version')!=VERSION or m.get('backend')!='GPT-SoVITS v2Pro' or not m.get('published_ready'):raise ValueError('本轮试音尚未准备好。')
 return m
def media_files():
 m=manifest();folder=(ROOT/RELATIVE).resolve();files={}
 for row in m['samples']:
  for key,prefix in [('playback',''),('raw','raw-')]:
   p=(ROOT/row[key]).resolve()
   if p.is_relative_to(folder) and p.suffix=='.wav' and p.is_file():files[prefix+p.name]=p
 for row in m['references']:
  p=Path(row['path']).resolve()
  if p.is_relative_to(folder/'references') and p.suffix=='.wav' and p.is_file():files['reference-'+row['id']+'.wav']=p
 return files
def validate_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试听版本已变，请刷新。')
 m=manifest();ids={x['id'] for x in m['samples'] if not x.get('excluded_from_main_audition')}
 if not isinstance(data.get('sample_id'),str) or data['sample_id'] not in ids|{'none','unsure'}:raise ValueError('请选择一条试听，也可以选都不合适。')
 if data.get('overall') not in {'closer','same','worse','unsure'}:raise ValueError('请选择总体听感。')
 allowed={'nasal','diction','pitch','pace','pause','accent','metallic'};issues=data.get('remaining_issues')
 if not isinstance(issues,list) or len(issues)>7 or any(not isinstance(x,str) or x not in allowed for x in issues) or len(issues)!=len(set(issues)):raise ValueError('问题选项无效。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('补充意见请控制在2000字以内。')
 return {'sample_id':data['sample_id'],'overall':data['overall'],'remaining_issues':issues,'notes':notes}
def save_review(data):
 choices=validate_review(data);m=manifest();identifier=uuid.uuid4().hex[:12];record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit local round3 audition form submission','choices':choices,'manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'sample_sha256':{s['id']:s['playback_sha256'] for s in m['samples']},'scope':'Subjective listening only; not reference word confirmation or stable training approval.'};folder=ROOT/'review/voice-preview-v2pro-round3';folder.mkdir(parents=True,exist_ok=True);(folder/(identifier+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return identifier
def validate_reference(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('参考版本已变，请刷新。')
 refs={r['id']:r for r in manifest()['references']};rid=data.get('reference_id')
 if not isinstance(rid,str) or rid not in refs:raise ValueError('参考片段不存在。')
 text=data.get('text')
 if not isinstance(text,str) or not 2<=len(text.strip())<=300 or any(c in text for c in '|\r\n'):raise ValueError('请填写逐字核对后的单段原话。')
 for field in ['words_checked','speaker_checked','boundaries_checked']:
  if data.get(field) is not True:raise ValueError('请先实际听原声，核对说话人、文字和首尾完整性；未确认也可以先不保存。')
 if data.get('voice_state') not in {'typical','atypical','unsure'}:raise ValueError('请选择原声状态。')
 return {'reference_id':rid,'text':text.strip(),'words_checked':True,'speaker_checked':True,'boundaries_checked':True,'voice_state':data['voice_state'],'source_sha256':refs[rid]['sha256']}
def save_reference(data):
 choices=validate_reference(data);identifier=uuid.uuid4().hex[:12];record={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user original-reference word/speaker/boundary review','choices':choices,'scope':'Confirms only this source clip. Does not certify other ASR labels or synthesized audio.'};folder=ROOT/'review/voice-reference-v2pro-round3';folder.mkdir(parents=True,exist_ok=True);(folder/(identifier+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return identifier
