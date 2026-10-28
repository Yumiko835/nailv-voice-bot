
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
import json,hashlib,datetime,uuid,re,threading
ROOT=Path(project_path(''));RELATIVE=Path('voice/materials/daily-review-20261025');VERSION='milkgreen-daily-material-review-v1';LOCK=threading.Lock()
def manifest():
 m=json.loads((ROOT/RELATIVE/'manifest.json').read_text(encoding='utf-8'))
 if m.get('version')!=VERSION:raise ValueError('素材版本不符，请刷新。')
 return m
def records():
 folder=ROOT/'review'/VERSION;rows=[]
 for p in folder.glob('*.json'):
  r=json.loads(p.read_text(encoding='utf-8'))
  if r.get('source')=='explicit user material review form':rows.append(r)
 return sorted(rows,key=lambda x:(x['submitted_at'],x['id']))
def latest():
 states={};preferred=None
 digest=hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest()
 for r in records():
  if r.get('manifest_sha256')!=digest:raise ValueError('素材清单与已保存校对不一致，请恢复原版本。')
  for e in r['entries']:states[e['id']]=e
  if r.get('preferred_reference') is not None:preferred=r['preferred_reference']
 return states,preferred
def summary():
 m=manifest();states,preferred=latest();candidates=[]
 if states.get(preferred,{}).get('decision')!='accept':preferred=None
 for c in m['candidates']:
  candidates.append({k:c.get(k) for k in ['id','source_id','start','end','seconds','text_candidate','role','priority','flags','asr_auxiliary']}|{'review':states.get(c['id'])})
 return {'version':VERSION,'count':m['count'],'seconds':m['seconds'],'priority_count':m['priority_count'],'candidates':candidates,'preferred_reference':preferred,'accepted_count':sum(x['decision']=='accept' for x in states.values()),'training_accepted_count':sum(states.get(c['id'],{}).get('decision')=='accept' for c in m['candidates'] if c['role']=='training_candidate')}
def media_files():
 folder=(ROOT/RELATIVE).resolve();files={}
 for c in manifest()['candidates']:
  for key,prefix in [('path',''),('context_path','context-')]:
   p=Path(c[key]).resolve()
   if p.is_relative_to(folder) and p.suffix=='.wav' and p.is_file():files[prefix+c['id']+'.wav']=p
 return files
def validate(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('素材版本已变，请刷新。')
 entries=data.get('entries');bank={c['id']:c for c in manifest()['candidates']}
 if not isinstance(entries,list) or len(entries)>len(bank):raise ValueError('核对条目格式错误。')
 out=[];seen=set()
 for row in entries:
  if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] not in bank or row['id'] in seen:raise ValueError('条目编号无效或重复。')
  seen.add(row['id']);decision=row.get('decision');text=row.get('text');note=row.get('note','')
  if not isinstance(decision,str) or decision not in {'accept','reject','pending'}:raise ValueError('核对结论无效。')
  if not isinstance(text,str) or not 1<=len(text.strip())<=350 or any(ord(c)<32 and c not in '\n\t' for c in text):raise ValueError('请填写350字以内的原话。')
  if any(c in text for c in ['|','\n','\r']):raise ValueError('原话请写在一行里，不要使用竖线。')
  if not isinstance(note,str) or len(note)>500:raise ValueError('备注请控制在500字以内。')
  if decision=='accept' and row.get('checked') is not True:raise ValueError('请先实际试听，并勾选本人、原话、首尾、背景和常态声线已核对。')
  c=bank[row['id']];out.append({'id':row['id'],'decision':decision,'text':text.strip(),'note':note,'human_checks_explicit':decision=='accept' and row.get('checked') is True,'source_id':c['source_id'],'source_start':c['start'],'source_end':c['end'],'clip_sha256':c['sha256'],'role':c['role']})
 pref=data.get('preferred_reference')
 if pref is not None and (not isinstance(pref,str) or pref not in bank or bank[pref]['role']!='reference_calibration'):raise ValueError('常态参考编号无效。')
 if not out and pref is None:raise ValueError('还没有需要保存的核对。')
 states,_=latest();states.update({x['id']:x for x in out})
 if pref is not None and states.get(pref,{}).get('decision')!='accept':raise ValueError('请先将所选常态参考标为可用，并完成核对。')
 return out,pref
def compile_reviewed():
 m=manifest();states,preferred=latest();groups={'training':[],'reference':[],'evaluation':[]}
 for c in m['candidates']:
  s=states.get(c['id'],{})
  if s.get('decision')!='accept' or not s.get('human_checks_explicit') or s.get('clip_sha256')!=c['sha256']:continue
  row={**c,'text':s['text'],'human_words_verified':True,'human_speaker_verified':True,'human_boundaries_verified':True,'human_cleanliness_verified':True,'human_typical_voice_verified':True,'reviewed_text_sha256':hashlib.sha256(s['text'].encode('utf-8')).hexdigest(),'training_allowed':c['role']=='training_candidate'}
  groups[{'training_candidate':'training','reference_calibration':'reference','evaluation_holdout':'evaluation'}[c['role']]].append(row)
 out=ROOT/RELATIVE/'reviewed';out.mkdir(parents=True,exist_ok=True)
 for k,rows in groups.items():(out/(k+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'training.list').write_text(''.join(x['path']+'|milkgreen|zh|'+x['text']+'\n' for x in groups['training']),encoding='utf-8')
 result={'version':VERSION,'training_clips':len(groups['training']),'training_seconds':round(sum(x['seconds'] for x in groups['training']),2),'references':len(groups['reference']),'evaluation':len(groups['evaluation']),'preferred_reference':preferred if any(c['id']==preferred for c in groups['reference']) else None,'training_started':False,'requires_feature_rebuild_for_reviewed_text':True,'scope':'Only actual explicit user confirmations. Reference and evaluation roles never enter training.list.'}
 (out/'status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
def save_review(data):
 with LOCK:
  entries,pref=validate(data);m=manifest()
  for row in entries:
   c=next(c for c in m['candidates'] if c['id']==row['id'])
   if hashlib.sha256(Path(c['path']).read_bytes()).hexdigest()!=row['clip_sha256']:raise ValueError('原声文件已变，请重新生成校对版本。')
  identifier=uuid.uuid4().hex[:12];r={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user material review form','manifest_sha256':hashlib.sha256((ROOT/RELATIVE/'manifest.json').read_bytes()).hexdigest(),'entries':entries,'preferred_reference':pref,'scope':'Per-clip original-audio verification, not a synthesized-voice approval.'}
  folder=ROOT/'review'/VERSION;folder.mkdir(parents=True,exist_ok=True);temp=folder/(identifier+'.tmp');temp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(folder/(identifier+'.json'));result=compile_reviewed();return {'id':identifier,'status':result}
