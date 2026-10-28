"""Loopback manual synthesis/review adapter; model workers exit after each request."""

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
import json,hashlib,threading,uuid,subprocess,os,re,datetime
ROOT=Path(project_path(''));REL=Path('voice/training/v5dev-hybrid-20261025');VERSION='milkgreen-v5dev-stage1-hybrid-v1'
from nailv_hybrid_routing import choose_style,STYLES,speech_chunks
_lock=threading.Lock();_jobs={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def status():
 t=ROOT/REL;config=t/'inference-config.json';progress=t/'status.json';dataset=t/'dataset/manifest.json';prompts=t/'prompts/manifest.json'
 if config.exists() and read(config).get('active_prompt_manifest'):prompts=Path(read(config)['active_prompt_manifest'])
 if progress.exists():state=read(progress)
 else:
  p=ROOT/'voice/training/v5turbo-golden-20261025/status.json';state=read(p) if p.exists() else {'stage':'preparing-data'}
 answer={'version':VERSION,'ready':config.exists() and (t/'training-receipt.json').exists(),'architecture':'微调 GPT + 官方原版 V5 Dev + 多语气原声','progress':state,'styles':{'auto':'自动选择'}|STYLES,'source_audio_uploaded':False,'sovits_finetuned':False}
 if dataset.exists():
  d=read(dataset);answer['dataset']={k:d[k] for k in ['train_count','train_minutes','holdout_count','human_training_labels_verified','original_text_preserved','particle_counts']}
 if prompts.exists():answer['prompts']={k:{'label':p['label'],'seconds':p['seconds'],'text':p['text'],'human_words_verified':p.get('human_words_verified',False),'media':('active-prompt-' if prompts.name=='active-manifest.json' else 'prompt-')+k+'.wav'} for k,p in read(prompts)['prompts'].items()}
 if config.exists():
  c=read(config);answer.update(default_checkpoint='e6',checkpoints=['e6'],checkpoint_locked='e6',temperature=c['settings']['temperature'],audio_io=c.get('audio_io',{}),repetition_penalty=c['settings']['repetition_penalty'])
 return answer
def validate_request(data):
 if not isinstance(data,dict):raise ValueError('请求格式无效。')
 text=data.get('text');speech_chunks(text);style=data.get('style','auto');route=choose_style(text,style)
 temperature=data.get('temperature',.9)
 if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not .85<=temperature<=.95:raise ValueError('采样灵活度请设在0.85～0.95之间。')
 checkpoint=data.get('checkpoint','default');config=ROOT/REL/'inference-config.json'
 if not config.exists():raise ValueError('模型仍在准备，暂时不能生成。')
 if not isinstance(checkpoint,str) or checkpoint not in {'e6','default'}:raise ValueError('已固定第6轮GPT，其余轮次仅保留存档。')
 return {'text':text,'style':style,'temperature':float(temperature),'checkpoint':checkpoint,'seed':-1},route
def start_job(data):
 request,route=validate_request(data)
 current=read(ROOT/REL/'inference-config.json')
 if current.get('active_prompt_manifest'):
  route['label']=read(current['active_prompt_manifest'])['prompts'][route['style']]['label'];route['reason']=['使用本轮净化参考']
 with _lock:
  if any(j['status'] in ['pending','running'] for j in _jobs.values()):raise ValueError('前一段还在生成，请等它完成后再试。')
  identifier=uuid.uuid4().hex[:12];_jobs[identifier]={'id':identifier,'status':'pending','route':{k:route[k] for k in ['style','label','reason']}}
  folder=ROOT/'voice/generated/hybrid'/identifier;folder.mkdir(parents=True);(folder/'request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
 def worker():
  try:
   _jobs[identifier]['status']='running';script=ROOT/REL/'scripts/run_hybrid_voice.py';python=Path(dependency_path("gpt_sovits",'.venv/Scripts/python.exe'));env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
   with (folder/'worker.log').open('w',encoding='utf-8') as log:r=subprocess.run([str(python),'-B','-X','utf8',str(script),'--request',str(folder/'request.json'),'--output',str(folder)],cwd=str(ROOT/REL),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=300)
   if r.returncode:
    failure=folder/'failure.json';message=read(failure).get('error') if failure.exists() else None
    raise RuntimeError(message or '本次生成失败，详细原因已保存在本机日志。')
   result=read(folder/'result.json');assert Path(result['playback']).resolve()==(folder/'speech.wav').resolve()
   _jobs[identifier].update(status='complete',media='generated-'+identifier+'.wav',seconds=result['seconds'],checkpoint=Path(result['gpt_checkpoint']).name,actual_reference_style=result.get('actual_reference_style'),reference_fallbacks=result.get('reference_fallbacks',[]))
  except subprocess.TimeoutExpired:_jobs[identifier].update(status='failed',error='本次生成超时，任务已结束。请缩短文字后再试。')
  except Exception as ex:_jobs[identifier].update(status='failed',error=str(ex)[:300])
 threading.Thread(target=worker,daemon=True).start();return dict(_jobs[identifier])
def job(identifier):
 if not re.fullmatch('[a-f0-9]{12}',identifier):raise ValueError('任务编号无效。')
 if identifier not in _jobs:raise ValueError('任务不存在或页面服务已重启。')
 return dict(_jobs[identifier])
def media_files():
 files={};t=(ROOT/REL).resolve();p=t/'prompts/manifest.json'
 if p.exists():
  for key,row in read(p)['prompts'].items():
   f=Path(row['path']).resolve()
   if f.is_relative_to(t/'prompts') and f.suffix=='.wav' and f.is_file():files['prompt-'+key+'.wav']=f
 p=t/'comparison/manifest.json'
 if p.exists():
  for row in read(p)['samples']:
   f=Path(row['playback']).resolve()
   if f.is_relative_to(t/'comparison') and f.suffix=='.wav' and f.is_file():files[row['id']+'.wav']=f
 gen=(ROOT/'voice/generated/hybrid').resolve()
 if gen.exists():
  for p in gen.glob('*/result.json'):
   if not re.fullmatch('[a-f0-9]{12}',p.parent.name):continue
   f=(p.parent/'speech.wav').resolve()
   if f.is_relative_to(gen) and f.is_file():files['generated-'+p.parent.name+'.wav']=f
 release=t/'inference-repairs/e6-deepcheck-20261025/release-listening.json'
 if release.exists():
  allowed=(t/'inference-repairs/e6-deepcheck-20261025').resolve()
  for row in read(release)['samples']:
   f=Path(row['path']).resolve();name=row['id']+'.wav'
   if re.fullmatch(r'e6-[a-z0-9_-]+\.wav',name) and f.is_relative_to(allowed) and f.suffix=='.wav' and f.is_file():files[name]=f
 # Clean-reference rescue comparison: exact manifest entries under this experiment only.
 rescue=t/'inference-repairs/clean-reference-turbo-20261025'
 release=rescue/'release-listening.json'
 if release.exists():
  for row in read(release)['samples']:
   f=Path(row['path']).resolve();name=row['id']+'.wav'
   if re.fullmatch(r'rescue-[a-z0-9_-]+\.wav',name) and f.is_relative_to(rescue.resolve()) and f.suffix=='.wav' and f.is_file():files[name]=f
 # Bounded manifest for the gentle-dereverb version; historical releases remain accessible.
 gentle=t/'inference-repairs/gentle-dereverb-20261025'
 release=gentle/'release-listening.json'
 if release.exists():
  for row in read(release)['samples']:
   f=Path(row['path']).resolve();name=row['id']+'.wav'
   if re.fullmatch(r'gentle-[a-z0-9_-]+\.wav',name) and f.is_relative_to(gentle.resolve()) and f.suffix=='.wav' and f.is_file():files[name]=f
 active=gentle/'prompts/active-manifest.json'
 if active.exists():
  for key,row in read(active)['prompts'].items():
   f=Path(row['path']).resolve()
   if f.is_relative_to(gentle.resolve()) and f.suffix=='.wav' and f.is_file():files['active-prompt-'+key+'.wav']=f
 # New repair serves only exact manifest entries inside its own experiment folder.
 connected=t/'inference-repairs/connected-noise-20261025'
 release=connected/'release-listening.json'
 if release.exists():
  for row in read(release)['samples']:
   f=Path(row['path']).resolve();name=row['id']+'.wav'
   if re.fullmatch(r'connected-[a-z0-9_-]+\.wav',name) and f.is_relative_to(connected.resolve()) and f.suffix=='.wav' and f.is_file():files[name]=f
 active=connected/'prompts-final85/active-manifest.json'
 if active.exists():
  for key,row in read(active)['prompts'].items():
   f=Path(row['path']).resolve()
   if f.is_relative_to(connected.resolve()) and f.suffix=='.wav' and f.is_file():files['active-prompt-'+key+'.wav']=f
 return files

def save_review(data):
 if not isinstance(data,dict) or data.get('version')!=VERSION:raise ValueError('试听版本已变，请刷新页面。')
 checkpoint=data.get('checkpoint');valid={'base','e2','e4','e6','e8','e10','none','tie'}
 if not isinstance(checkpoint,str) or checkpoint not in valid:raise ValueError('请选择实际听过的 GPT 权重。')
 notes=data.get('notes','');issues=data.get('issues',[])
 if not isinstance(notes,str) or len(notes)>2000:raise ValueError('意见请控制在2000字以内。')
 if not isinstance(issues,list) or any(not isinstance(x,str) or x not in {'pitch','slow','fast','pause','timbre','metallic','diction','style'} for x in issues) or len(set(issues))!=len(issues):raise ValueError('问题选项无效。')
 t=ROOT/REL;manifest=t/'comparison/manifest.json'
 if not manifest.exists():raise ValueError('训练试听尚未准备好。')
 identifier=uuid.uuid4().hex[:12];receipt={'id':identifier,'version':VERSION,'submitted_at':datetime.datetime.now().astimezone().isoformat(),'source':'explicit user hybrid checkpoint listening form','choices':{'checkpoint':checkpoint,'issues':issues,'notes':notes},'comparison_manifest_sha256':sha(manifest),'dataset_sha256':sha(t/'dataset/manifest.json'),'prompts_manifest_sha256':sha(t/'prompts/manifest.json'),'scope':'Subjective listening preference. Does not change dataset labels, deploy to QQ, or rewrite frozen comparison audio.'}
 current_config=read(ROOT/REL/'inference-config.json');receipt['inference_revision']=current_config.get('audio_io',{}).get('revision')
 release=ROOT/REL/'inference-repairs/e6-deepcheck-20261025/release-listening.json'
 if release.exists():receipt['latest_inference_listening_manifest_sha256']=sha(release);receipt['scope']='Explicit feedback on the current epoch-6-only inference revision; historical checkpoint comparison files are preserved.'
 active=current_config.get('active_prompt_manifest')
 if active:receipt['active_prompts_manifest_sha256']=sha(active)
 latest=ROOT/REL/'inference-repairs/gentle-dereverb-20261025/release-listening.json'
 if latest.exists():receipt['latest_inference_listening_manifest_sha256']=sha(latest);receipt['scope']='Explicit feedback on the gentle-dereverb inference revision; historical audio and reviews are preserved.'
 latest=ROOT/REL/'inference-repairs/connected-noise-20261025/release-listening.json'
 if latest.exists():receipt['latest_inference_listening_manifest_sha256']=sha(latest);receipt['scope']='Explicit feedback on connected-neural85 inference revision; no automatic subjective approval.'
 folder=ROOT/'review'/VERSION;folder.mkdir(parents=True,exist_ok=True);temp=folder/(identifier+'.tmp');temp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(folder/(identifier+'.json'));return identifier
