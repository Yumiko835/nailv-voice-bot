
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
import json,hashlib,re,threading,subprocess,os,uuid
ROOT=Path(project_path(''));T=ROOT/'voice/training/v2proplus-newsource-20261025';G=Path(dependency_path("gpt_sovits",''));_lock=threading.Lock();_jobs={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def listening_path():return T/'listening.json' if (T/'listening.json').exists() else T/'generated/test/manifest.json'
def comparison_path():return T/'inference-diagnosis-20261025/gpt-epochs.json'
def continuation_path():return T/'continuation-e10to14-20261025/comparison.json'
def clarity_path():return T/'continuation-e10to14-20261025/clarity-20261025/manifest.json'
def e20_path():return T/'continuation-e14to20-20261025/comparison.json'
def expanded_e14_path():return T/'e14-more-sentences-20261025/manifest.json'
def tail_repair_path():return T/'e14-tail-repair-20261025/listening-v2.json'
def punctuation_path():return T/'punctuation-tail-patch-20261025/listening.json'
def status():
 deployment=read(T/'deployment.json') if (T/'deployment.json').exists() else {};out={'ready':deployment.get('ready',False),'version':'v2ProPlus','progress':read(T/'status.json') if (T/'status.json').exists() else {'stage':'preparing'},'samples':[],'prompts':{},'qq_connected':False}
 if (T/'prompts/manifest.json').exists():
  bank=read(T/'prompts/manifest.json');out['prompts']={key:{'label':p['label'],'text':p['text'],'reference_id':p['id']} for key,p in bank['prompts'].items()};out['reference_count']=len(bank['prompts'])+sum(p.get('enabled',True) for p in bank['alternates'].values());out['archived_reference_count']=sum(not p.get('enabled',True) for p in bank['alternates'].values())
 if (T/'selected-models.json').exists():
  models=read(T/'selected-models.json');out['gpt_epoch']=models['gpt']['epoch'];out['sovits_epoch']=models.get('sovits_epoch');out['gpt_user_locked']=models.get('gpt_user_locked',False)
 out['gpu_training']=(out['progress'].get('stage')=='training-proplus-sovits' and out['progress'].get('epochs') in [14,20]) or out['progress'].get('stage')=='proplus-comparing-continuation'
 out['generation_available']=out['ready'] and not out['gpu_training']
 manifest=listening_path()
 if out['ready'] and manifest.exists():out['manifest_sha256']=sha(manifest);out['samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(manifest)['samples']]
 comparison=comparison_path()
 if comparison.exists():
  out['comparison_sha256']=sha(comparison);out['gpt_comparison']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','gpt_epoch']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(comparison)['samples']]
 continuation=continuation_path()
 if continuation.exists():
  out['continuation_sha256']=sha(continuation);out['continuation_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','group']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(continuation)['samples']]
 clarity=clarity_path()
 if clarity.exists():
  out['clarity_sha256']=sha(clarity);out['clarity_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(clarity)['samples']]
 e20=e20_path()
 if e20.exists():
  out['e20_sha256']=sha(e20);out['e20_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','group','case']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(e20)['samples']]
  out['e20_method_base_epoch']=read(e20).get('method_base_epoch',20)
 expanded=expanded_e14_path()
 if expanded.exists():
  out['expanded_e14_sha256']=sha(expanded);out['expanded_e14_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','group','audition_label']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav','content_note':r.get('content_note','')} for r in read(expanded)['samples']]
 tail=tail_repair_path()
 if tail.exists():
  out['tail_repair_sha256']=sha(tail);out['tail_repair_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','case','case_title']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav'} for r in read(tail)['samples']]
 punct=punctuation_path()
 if punct.exists():
  out['punctuation_sha256']=sha(punct);out['punctuation_samples']=[{k:r[k] for k in ['id','text','label','seconds','reference_id','case','case_title']}|{'media':'test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav','content_note':r.get('content_note','')} for r in read(punct)['samples']]
 out['inference_patch']='punctuation-tail-v1'
 return out
def media_files():
 files={}
 for manifest in [listening_path(),comparison_path(),continuation_path(),clarity_path(),e20_path(),expanded_e14_path(),tail_repair_path(),punctuation_path()]:
  if manifest.exists():
   for r in read(manifest)['samples']:
    path=Path(r['playback']).resolve()
    if re.fullmatch('[a-z0-9_-]+',r['id']) and path.is_relative_to(T.resolve()) and path.is_file():files['test-'+r['id']+'-'+r['raw_sha256'][:12]+'.wav']=path
 for manifest in (T/'generated/jobs').glob('*/manifest.json') if (T/'generated/jobs').exists() else []:
  if not re.fullmatch('[a-f0-9]{12}',manifest.parent.name):continue
  for r in read(manifest)['samples']:
   path=Path(r['playback']).resolve()
   if path.is_relative_to(manifest.parent.resolve()) and path.is_file():files['job-'+manifest.parent.name+'.wav']=path
 return files
def start_job(data):
 if not status()['ready']:raise ValueError('双阶段模型仍在训练或验证，完成后即可生成。')
 if not status()['generation_available']:raise ValueError('正在续训音色模型，训练完成后恢复生成；现有试听仍可播放。')
 text=data.get('text');style=data.get('style','auto');temperature=data.get('temperature',.8)
 if not isinstance(text,str) or not text.strip() or len(text)>600:raise ValueError('请输入1～600字。')
 if not isinstance(style,str) or style not in ['auto',*read(T/'prompts/manifest.json')['prompts']]:raise ValueError('未知情绪。')
 if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not .75<=temperature<=.95:raise ValueError('灵活度须在0.75～0.95之间。')
 with _lock:
  if any(r['status'] in ['pending','running'] for r in _jobs.values()):raise ValueError('上一句仍在生成，请稍等。')
  key=uuid.uuid4().hex[:12];folder=T/'generated/jobs'/key;folder.mkdir(parents=True);payload={'samples':[{'id':'input','text':text,'style':style,'temperature':temperature,'seed':int.from_bytes(os.urandom(4),'little')}]};(folder/'request.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');(folder/'reference-manifest.json').write_text(json.dumps(read(T/'prompts/manifest.json'),ensure_ascii=False),encoding='utf-8');_jobs[key]={'id':key,'status':'pending'}
 def run():
  _jobs[key]['status']='running'
  try:
   with (folder/'worker.log').open('w',encoding='utf-8') as log:
    r=subprocess.run([str(G/'.venv/Scripts/python.exe'),'-B','-X','utf8',str(T/'scripts/synthesize_punctuation.py'),'--requests',str(folder/'request.json'),'--reference-manifest',str(folder/'reference-manifest.json'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,cwd=T,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));assert r.returncode==0,'生成未成功，日志已保存在本机。'
   sample=read(folder/'manifest.json')['samples'][0];_jobs[key].update(status='complete',media='job-'+key+'.wav',seconds=sample['seconds'],emotion=sample['label'])
  except Exception as exc:_jobs[key].update(status='failed',error=str(exc)[:250])
  (folder/'job.json').write_text(json.dumps(_jobs[key],ensure_ascii=False),encoding='utf-8')
 threading.Thread(target=run,daemon=True).start();return dict(_jobs[key])
def job(key):
 if not re.fullmatch('[a-f0-9]{12}',key):raise ValueError('任务号无效。')
 if key in _jobs:return dict(_jobs[key])
 path=T/'generated/jobs'/key/'job.json'
 if path.exists():return read(path)
 raise ValueError('任务不存在。')
