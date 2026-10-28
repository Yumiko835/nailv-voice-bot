"""Loopback status, explicit reviews and bounded local generation for new-source V5 Dev."""

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
import json,re,os,threading,uuid,subprocess,importlib.util,hashlib,time
ROOT=Path(project_path(''));T=ROOT/'voice/training/v5dev-newsource-20261025';G=Path(dependency_path("gpt_sovits",''));_lock=threading.Lock();_jobs={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reference_path():
 p=T/'emotion_prompts-v2/manifest.json'
 return p if p.exists() else T/'emotion_prompts/manifest.json'
def public_reference(key,p,kind='prompt',version='v1'):
 return {x:p[x] for x in ['label','text','seconds','source_id','start','end','estimated_bgm_energy_fraction','human_emotion_verified']}|{'filename':Path(p['path']).name,'media':version+'-'+kind+'-'+key+'.wav','style':p.get('style',key)}
def status():
 s=read(T/'status.json') if (T/'status.json').exists() else {'stage':'preparing'};d=read(T/'deployment.json') if (T/'deployment.json').exists() else {};out={'progress':s,'ready':d.get('ready',False),'active_default':d.get('activate_default',False),'review_version':'newsource-emotion-pool-v1','prompts':{},'qq_connected':False}
 if (T/'sources/manifest.json').exists():out['sources_hours']=read(T/'sources/manifest.json')['total_hours']
 if (T/'analysis/separation.json').exists():out['separated']=len(read(T/'analysis/separation.json'))
 if (T/'analysis/screen.json').exists():
  rows=list(read(T/'analysis/screen.json').values());good=[x for x in rows if x['eligible']];out.update(strict_checked=len(rows),strict_accepted=len(good),eligible_minutes=sum(x['seconds'] for x in good)/60)
 if (T/'dataset/manifest.json').exists():
  m=read(T/'dataset/manifest.json');out['dataset']={k:m[k] for k in ['train_count','train_minutes','holdout_count','validation_count','original_text_preserved']}
 if reference_path().exists():
  bank=read(reference_path());v='v2' if bank['version'].endswith('v2') else 'v1';out.update(review_version=bank['version'],reference_manifest_sha256=sha(reference_path()),pending_styles=bank.get('pending_styles',[]),candidates={},alternates={},fixed_epoch=True,audio_review_pending=bank.get('audio_review_pending',False),preferred_candidates=bank.get('preferred_candidates',{}))
  for kind in ['prompts','candidates','alternates']:
   for k,p in bank.get(kind,{}).items():out[kind][k]=public_reference(k,p,{'prompts':'prompt','candidates':'candidate','alternates':'alternate'}[kind],v)
 if (T/'emotion_prompts-v2/bgm-comparison.json').exists():
  out['bgm_comparison']=[{k:p[k] for k in ['style','label','text','seconds','source_id','start','end']}|{kind:{'media':'bgm-'+p['style']+'-'+kind+'.wav','sample_rate':p[kind]['sample_rate']} for kind in ['original','separated']} for p in read(T/'emotion_prompts-v2/bgm-comparison.json')['samples']]
 kp=T/'karaoke-reference-context-20261025/listening.json'
 if kp.exists():
  pool=read(kp);out['karaoke_pool']={'version':pool['version'],'manifest_sha256':sha(kp),'samples':[{k:p[k] for k in ['id','filename','label','style','text','seconds','source_id','start','end','human_emotion_verified','human_ending_feedback']}|{kind:{'media':'context-karaoke-'+p['id']+'-'+kind+'.wav'} for kind in ['primary','before','removed']} for p in pool['samples']]}
  reviews=[]
  for rp in (ROOT/'review/newsource-karaoke-context-pool-v1').glob('*.json'):
   try:
    r=read(rp)
    if r.get('manifest_sha256')==out['karaoke_pool']['manifest_sha256']:reviews.append(r)
   except (ValueError,OSError):continue
  if reviews:out['karaoke_pool']['last_choices']=max(reviews,key=lambda r:r['submitted_at'])['choices']
  cp=kp.parent/'reviewed-classification.json'
  if cp.exists():
   classification=read(cp)
   for p in out['karaoke_pool']['samples']:p.update(classification['overlays'].get(p['id'],{}))
 repair=T/'reference-microgate-20261025/manifest.json'
 if repair.exists():
  b=read(repair);stats=read(repair.parent/'technical-verification.json');out['reference_revision']={'version':'reference-microgate-review-v1','manifest_sha256':sha(repair),'samples':[{k:p[k] for k in ['id','style','label','role','text','seconds','source_id','start','end','gate_report']}|{'before':'microgate-'+p['id']+'-before.wav','after':'microgate-'+p['id']+'-after.wav'} for p in b['samples']],'verification':stats,'synthesis':[]};out['pending_styles']=b['pending_styles']
  checkpath=repair.parent/'synthesis-content-check.json';content=read(checkpath) if checkpath.exists() else {};out['reference_revision']['blocked_reference_ids']=content.get('blocked_reference_ids',[]);out['reference_revision']['content_check_sha256']=sha(checkpath) if checkpath.exists() else None
  for p in out['reference_revision']['samples']:p['selection_blocked']=p['id'] in content.get('blocked_reference_ids',[])
  out['prompts']={k:public_reference(k,p)|{'media':'microgate-'+p['id']+'-after.wav','processing_label':p['processing_label']} for k,p in b['prompts'].items()};out['alternates']={k:public_reference(k,p)|{'media':'microgate-'+p['id']+'-after.wav','processing_label':p['processing_label']} for k,p in b['alternates'].items()}
  for sub in ['synthesis','synthesis-replacements']:
   sm=repair.parent/sub/'manifest.json'
   if sm.exists():out['reference_revision']['synthesis'] += [{'id':r['id'],'text':r['text'],'label':('叠词完整性测试' if r['test_case_id']=='repeated-mama' else r['reference']['label']+' · 实际生成'),'reference_ab':r['reference'].get('role')=='replacement' and r['test_case_id']!='repeated-mama','content_mismatch':any(x['id']==r['id'] and x['gross_content_mismatch'] for x in content.get('samples',[])),'reference_id':r['reference']['id'],'media':'microgate-synthesis-'+r['id']+'.wav','seconds':r['seconds']} for r in read(sm)['samples']]
 final=T/'synthesis-diagnosis-20261025/final-v5-attempt/manifest.json'
 if final.exists():
  m=read(final);out['final_v5']={'version':m['version'],'manifest_sha256':sha(final),'confirmed_references':['gentle_a','surprised_b'],'pending_reference_style':'daily','previous_synthesis_human_rejected':True,'samples':[{k:r[k] for k in ['id','label','text','seconds','reference_id']}|{'media':'v5-final-'+r['id']+'.wav'} for r in m['samples']],'human_quality_verified':False,'fallback_if_rejected':'v2ProPlus'}
 if (T/'selected-checkpoint.json').exists():
  c=read(T/'selected-checkpoint.json');out['selection']={k:c[k] for k in ['epoch','ranking','automatic_eligibility_passed','human_naturalness_verified','default_is_provisional']}
 for folder in ['comparison','blind']:
  p=T/folder/'release-listening.json'
  if p.exists():out[folder]=[{k:r[k] for k in ['id','text','epoch','case']}|{'media':r['id']+'.wav'} for r in read(p)['samples']]
 return out
def routing():
 spec=importlib.util.spec_from_file_location('nailv_new_emotion_routing',T/'scripts/emotion_routing.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def start_job(data):
 if not isinstance(data,dict):raise ValueError('请求格式无效。')
 current=status()
 if not current['ready']:raise ValueError('已记录你的语气选择；参考音频的背景音乐问题正在修正，请先试听去伴奏对照。' if current.get('audio_review_pending') else '新素材模型仍在处理或验证，暂时不能生成；旧版试听仍保留。')
 r=routing().route(data.get('text'),data.get('style','auto'),data.get('context',''));temperature=data.get('temperature',.9)
 bank=read(reference_path())
 if r['style'] not in bank['prompts']:raise ValueError(r['label']+'的新参考还待你试听选择，请先在下方确认候选，或手动选已认可的情绪。')
 if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not .85<=temperature<=.95:raise ValueError('采样灵活度须在0.85～0.95。')
 chosen=read(T/'selected-checkpoint.json');epoch=data.get('epoch',chosen['epoch'])
 if type(epoch) is not int or epoch!=6:raise ValueError('本轮固定使用第6轮GPT。')
 with _lock:
  if any(v['status'] in ['pending','running'] for v in _jobs.values()):raise ValueError('上一段还在生成，请稍等。')
  key=uuid.uuid4().hex[:12];folder=T/'generated'/key;folder.mkdir(parents=True);request={'samples':[{'id':'input','text':r['text'],'style':r['style'],'context':data.get('context',''),'temperature':temperature,'seed':int.from_bytes(os.urandom(4),'little')}]};(folder/'request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8');(folder/'reference-manifest.json').write_text(json.dumps(bank|{'snapshot_of':str(reference_path())},ensure_ascii=False),encoding='utf-8');_jobs[key]={'id':key,'status':'pending','emotion':r['label'],'epoch':epoch}
 def work():
  _jobs[key]['status']='running'
  try:
   env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1');python=G/'.venv/Scripts/python.exe'
   with (folder/'worker.log').open('w',encoding='utf-8') as log:
    cmd=[str(python),'-B','-X','utf8',str(T/'scripts/synthesize.py'),'--epoch',str(epoch),'--requests',str(folder/'request.json'),'--reference-manifest',str(folder/'reference-manifest.json'),'--out',str(folder)];p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=str(T),env=env,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));assert p.returncode==0,'生成未成功，日志保留在本机。'
   result=read(folder/'manifest.json')['samples'][0];assert Path(result['playback']).resolve().is_relative_to(folder.resolve());_jobs[key].update(status='complete',media='generated-'+key+'.wav',seconds=result['seconds'],checkpoint=Path(result['gpt_checkpoint']).name)
  except Exception as exc:_jobs[key].update(status='failed',error=str(exc)[:250])
  (folder/'job.json').write_text(json.dumps(_jobs[key],ensure_ascii=False),encoding='utf-8')
 threading.Thread(target=work,daemon=True).start();return dict(_jobs[key])
def job(key):
 if not re.fullmatch('[a-f0-9]{12}',key):raise ValueError('任务编号无效。')
 if key in _jobs:return dict(_jobs[key])
 p=T/'generated'/key/'job.json'
 if p.exists():return read(p)
 raise ValueError('任务不存在。')
def media_files():
 files={};manifest=reference_path();base=manifest.parent.resolve()
 if manifest.exists():
  bank=read(manifest);v='v2' if bank['version'].endswith('v2') else 'v1'
  for kind in ['prompts','candidates','alternates']:
   for key,p in bank.get(kind,{}).items():
    f=Path(p['path']).resolve()
    if re.fullmatch('[a-z_]+',key) and f.is_relative_to(base) and f.is_file():files[public_reference(key,p,{'prompts':'prompt','candidates':'candidate','alternates':'alternate'}[kind],v)['media']]=f
 bgm=T/'emotion_prompts-v2/bgm-comparison.json'
 if bgm.exists():
  for row in read(bgm)['samples']:
   for kind in ['original','separated']:
    f=Path(row[kind]['path']).resolve()
    if re.fullmatch('[a-z_]+',row['style']) and f.is_relative_to(T.resolve()) and f.is_file():files['bgm-'+row['style']+'-'+kind+'.wav']=f
 kp=T/'karaoke-reference-context-20261025/listening.json'
 if kp.exists():
  for row in read(kp)['samples']:
   for kind in ['primary','before','removed']:
    f=Path(row[kind]['path']).resolve()
    if re.fullmatch('[a-z0-9_-]+',row['id']) and f.is_relative_to(T.resolve()) and f.is_file():files['context-karaoke-'+row['id']+'-'+kind+'.wav']=f
 repair=T/'reference-microgate-20261025/manifest.json'
 if repair.exists():
  for p in read(repair)['samples']:
   if not re.fullmatch('[a-z_]+',p['id']):continue
   for kind,filename in [('before',p['path']),('after',p['gated_preview']['path'])]:
    f=Path(filename).resolve()
    if f.is_relative_to(repair.parent.resolve()) and f.is_file():files['microgate-'+p['id']+'-'+kind+'.wav']=f
  for sub in ['synthesis','synthesis-replacements']:
   sm=repair.parent/sub/'manifest.json'
   if sm.exists():
    for p in read(sm)['samples']:
     f=Path(p['playback']).resolve()
     if re.fullmatch('[a-z0-9_-]+',p['id']) and f.is_relative_to(sm.parent.resolve()) and f.is_file():files['microgate-synthesis-'+p['id']+'.wav']=f
 final=T/'synthesis-diagnosis-20261025/final-v5-attempt/manifest.json'
 if final.exists():
  for r in read(final)['samples']:
   f=Path(r['playback']).resolve()
   if re.fullmatch('[a-z0-9_-]+',r['id']) and f.is_relative_to(final.parent.resolve()) and f.is_file():files['v5-final-'+r['id']+'.wav']=f
 for release in [T/'comparison/release-listening.json',T/'blind/release-listening.json']:
  if not release.exists():continue
  for row in read(release)['samples']:
   f=Path(row['path']).resolve();name=row['id']+'.wav'
   if re.fullmatch(r'[a-z0-9_-]+\.wav',name) and f.is_relative_to(T.resolve()) and f.is_file():files[name]=f
 for p in (T/'generated').glob('*/manifest.json') if (T/'generated').exists() else []:
  if not re.fullmatch('[a-f0-9]{12}',p.parent.name):continue
  row=read(p)['samples'][0];f=Path(row['playback']).resolve()
  if f.is_relative_to(p.parent.resolve()) and f.is_file():files['generated-'+p.parent.name+'.wav']=f
 return files
def save_review(data):
 if isinstance(data,dict) and data.get('version')=='reference-microgate-review-v1':return save_microgate_review(data)
 if isinstance(data,dict) and data.get('version')=='newsource-karaoke-context-pool-v1':return save_karaoke_review(data)
 if isinstance(data,dict) and data.get('version')=='newsource-emotion-pool-v2':return save_replacement_review(data)
 if not isinstance(data,dict) or data.get('version')!='newsource-emotion-pool-v1':raise ValueError('请刷新本轮页面后再保存。')
 bank=read(T/'emotion_prompts/manifest.json');choices=data.get('choices');valid={'unreviewed','keep','wrong_emotion','bad_audio','text_error'}
 if not isinstance(choices,dict) or set(choices)!=set(bank['prompts']) or any(v not in valid for v in choices.values()):raise ValueError('请按实际试听标记这10段参考。')
 notes=data.get('notes','')
 if not isinstance(notes,str) or len(notes)>4000:raise ValueError('补充意见最多4000字。')
 key=uuid.uuid4().hex[:12];out=ROOT/'review/newsource-emotion-pool-v1';out.mkdir(parents=True,exist_ok=True);record={'id':key,'submitted_at':time.time(),'source':'explicit user new-source emotion review','choices':choices,'notes':notes,'manifest_sha256':sha(T/'emotion_prompts/manifest.json'),'prompt_hashes':{k:p['sha256'] for k,p in bank['prompts'].items()},'training_data_rewritten':False};(out/(key+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return key

def atomic_json(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def save_replacement_review(data):
 selections=data.get('selections');notes=data.get('notes','')
 if not isinstance(selections,dict) or set(selections)!={'daily','sigh'}:raise ValueError('请分别选择日常、无奈两个分组。')
 if not isinstance(notes,str) or len(notes)>4000:raise ValueError('补充意见最多4000字。')
 with _lock:
  path=reference_path();before=sha(path);bank=read(path)
  if bank.get('audio_review_pending'):raise ValueError('闲聊A、无奈B的语气选择已记录。当前等待去伴奏音频的质量反馈，暂不启用含BGM原声。')
  if bank['version']!='newsource-emotion-pool-v2' or data.get('reference_manifest_sha256')!=before:raise ValueError('参考库已更新，请刷新页面后再保存。')
  # Validate the whole request before mutating anything.
  for style,key in selections.items():
   if key in ['unreviewed','none']:continue
   if key not in bank['candidates'] or bank['candidates'][key]['style']!=style:raise ValueError('候选不属于对应的情绪分组。')
   p=bank['candidates'][key]
   if sha(p['path'])!=p['sha256']:raise ValueError('候选音频已变化，请重新核对。')
  review_id=uuid.uuid4().hex[:12];out=ROOT/'review/newsource-emotion-pool-v2';out.mkdir(parents=True,exist_ok=True)
  atomic_json(out/(review_id+'.before.json'),bank)
  for style,key in selections.items():
   if key=='unreviewed':continue
   if key=='none':bank['prompts'].pop(style,None);continue
   bank['prompts'][style]=bank['candidates'][key]|{'style':style,'label':routing().STYLES[style],'human_emotion_verified':True,'review_status':'emotion_accepted','emotion_assignment':'Explicit user candidate selection','review_id':review_id}
  bank['pending_styles']=[s for s in ['daily','sigh'] if s not in bank['prompts']];bank['human_approved']=not bank['pending_styles'];bank['last_review_id']=review_id
  atomic_json(path,bank)
  atomic_json(out/(review_id+'.json'),{'id':review_id,'submitted_at':time.time(),'selections':selections,'notes':notes,'before_manifest_sha256':before,'after_manifest_sha256':sha(path),'training_or_model_modified':False})
  deployment=read(T/'deployment.json');deployment.update(reference_review_pending=bool(bank['pending_styles']),pending_emotion_styles=bank['pending_styles'],emotion_styles_available=list(bank['prompts']));atomic_json(T/'deployment.json',deployment)
  progress=read(T/'status.json') if (T/'status.json').exists() else {};progress.update(stage='emotion-reference-correction-awaiting-review' if bank['pending_styles'] else 'emotion-reference-review-complete',updated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),models_ready=True,epoch=6,pending_styles=bank['pending_styles'],accepted_styles=len(bank['prompts']));atomic_json(T/'status.json',progress)
  return review_id

def save_karaoke_review(data):
 path=T/'karaoke-reference-context-20261025/listening.json';pool=read(path);choices=data.get('choices');notes=data.get('notes','');valid={'unreviewed','keep','singer_remaining','hiss_or_artifact','host_damaged','wrong_emotion'}
 if data.get('manifest_sha256')!=sha(path):raise ValueError('试听清单已更新，请刷新后再保存。')
 if not isinstance(choices,dict) or set(choices)!={r['id'] for r in pool['samples']} or any(v not in valid for v in choices.values()):raise ValueError('请按实际试听标记本组参考。')
 if not isinstance(notes,str) or len(notes)>4000:raise ValueError('补充意见最多4000字。')
 key=uuid.uuid4().hex[:12];out=ROOT/'review/newsource-karaoke-context-pool-v1';out.mkdir(parents=True,exist_ok=True);record={'id':key,'submitted_at':time.time(),'manifest_sha256':sha(path),'choices':choices,'notes':notes,'sample_hashes':{r['id']:r['primary']['sha256'] for r in pool['samples']},'source':'Explicit human listening review; no automated quality approvals','model_or_training_modified':False,'reference_bank_automatically_activated':False};atomic_json(out/(key+'.json'),record);return key

def save_microgate_review(data):
 path=T/'reference-microgate-20261025/manifest.json';bank=read(path);selections=data.get('selections');notes=data.get('notes','')
 if data.get('manifest_sha256')!=sha(path):raise ValueError('候选已更新，请刷新后再保存。')
 if not isinstance(selections,dict) or set(selections)!={'daily','gentle','surprised'}:raise ValueError('请分别选择日常、温柔、惊讶三个分组。')
 for style,key in selections.items():
  if key in ['unreviewed','none']:continue
  if key not in bank['candidates'] or bank['candidates'][key]['style']!=style:raise ValueError('候选与情绪分组不符。')
  checkpath=path.parent/'synthesis-content-check.json'
  if checkpath.exists() and key in read(checkpath).get('blocked_reference_ids',[]):raise ValueError('这段参考的合成测试出现明显漏读，已暂时停用，请选择另一段。')
 if not isinstance(notes,str) or len(notes)>4000:raise ValueError('补充意见最多4000字。')
 key=uuid.uuid4().hex[:12];out=ROOT/'review/reference-microgate-review-v1';out.mkdir(parents=True,exist_ok=True);atomic_json(out/(key+'.json'),{'id':key,'submitted_at':time.time(),'manifest_sha256':sha(path),'selections':selections,'notes':notes,'candidate_sha256':{k:p['sha256'] for k,p in bank['candidates'].items()},'source':'Explicit human replacement reference review','models_modified':False});return key
