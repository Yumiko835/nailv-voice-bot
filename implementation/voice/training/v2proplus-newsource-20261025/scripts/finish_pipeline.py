"""Finish the authorized job after the already-running acoustic worker exits."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from common import *
import subprocess,traceback,argparse,psutil,shutil
p=argparse.ArgumentParser();p.add_argument('--train-pid',type=int,required=True);args=p.parse_args();HERE=Path(__file__).parent;PY=G/'.venv/Scripts/python.exe'
write(T/'continuation-process.json',{'pid':os.getpid(),'script':str(Path(__file__).resolve()),'waiting_for_train_pid':args.train_pid,'scope':'finish both-stage model, test12 phrases, publish local UI; no QQ or external messages'})
def run(name,*arguments):
 log=T/'logs'/('finish-'+Path(name).stem+'.log')
 with log.open('w',encoding='utf-8') as stream:r=subprocess.run([str(PY),'-B','-X','utf8',str(HERE/name),*map(str,arguments)],stdout=stream,stderr=subprocess.STDOUT,cwd=T,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if r.returncode:raise RuntimeError(name+' failed: '+str(log)+'\n'+log.read_text(encoding='utf-8',errors='replace')[-4000:])
try:
 if not (T/'stage2-training-receipt.json').exists():
  worker=psutil.Process(args.train_pid);cmd=worker.cmdline();assert any('train_stage2.py' in q for q in cmd) and 'train' in cmd
  while not (T/'stage2-training-receipt.json').exists():
   try:worker.wait(timeout=30)
   except psutil.TimeoutExpired:continue
   if not (T/'stage2-training-receipt.json').exists():raise RuntimeError('Acoustic training stopped before its completion receipt; preserve all checkpoints and inspect the training log.')
 models=read(T/'selected-models.json');s2=read(T/'stage2-training-receipt.json');assert s2['epochs_completed']==10;models['sovits']=next(r for r in s2['exports'] if r['epoch']==10);write(T/'selected-models.json',models);verify_protected()
 for path in HERE.iterdir():
  if path.suffix in ['.py','.js','.html']:shutil.copy2(path,T/'scripts'/path.name)
 status('proplus-generating-tests',completed=0,total=12)
 run('synthesize.py','--requests',T/'generated/test-requests.json','--out',T/'generated/test');run('check_outputs.py')
 checks=read(T/'generated/test/technical-verification.json')['checks'];write(T/'deployment.json',{'ready':True,'version':'v2ProPlus','models':models,'prompts_manifest_sha256':sha(T/'prompts/manifest.json'),'gpt_epochs_trained':10,'SoVITS_epochs_trained':10,'source_dataset_reused_unchanged':True,'human_quality_verified':False,'content_check_warning_ids':[r['id'] for r in checks if r['possible_content_mismatch']],'qq_connected':False});status('proplus-ready',GPT_epochs=10,SoVITS_epochs=10,gpt_default_epoch=models['gpt']['epoch'],sovits_default_epoch=10,emotion_styles=10,reference_clips=11,test_samples=12,human_quality_verified=False)
 write(T/'completion.json',{'complete':True,'technical_validation_complete':True,'human_listening_pending':True,'output':str(T),'page':'http://127.0.0.1:49850/voice-proplus'})
 print(json.dumps(read(T/'completion.json'),ensure_ascii=False),flush=True)
except Exception as exc:
 write(T/'pipeline-failure.json',{'error':str(exc),'traceback':traceback.format_exc(),'checkpoints_preserved':True});status('proplus-failed',error=str(exc));raise
