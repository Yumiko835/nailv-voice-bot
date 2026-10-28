"""GPT-only refinement with explicit LR/accumulation, independent V2 ProPlus project."""

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
import os,sys,json,hashlib,time,math,argparse,random,collections
ROOT=Path(project_path(''));G=Path(dependency_path("gpt_sovits",''));T=ROOT/'voice/training/v2proplus-newsource-20261025';F=T/'features';M=ROOT/'runtime/models/gpt-sovits-upgrade/GPT_SoVITS/pretrained_models'
p=argparse.ArgumentParser();p.add_argument('stage',choices=['smoke','train']);args=p.parse_args();smoke=args.stage=='smoke'
os.environ.update(HF_HOME=str(T/'cache/huggingface'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TEMP=str(T/'cache'),TMP=str(T/'cache'),NUMBA_CACHE_DIR=str(T/'cache/numba'),LIBROSA_CACHE_DIR=str(T/'cache/librosa'),MPLCONFIGDIR=str(T/'cache/matplotlib'),TORCH_HOME=str(T/'cache/torch'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',G2PW='0',version='v2ProPlus',hz='25hz')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
 p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
assert read(T/'feature-verification.json')['ready']
plan=read(T/'training-plan.json')['GPT'];assert plan['learning_rate']['peak']==.0003 and plan['learning_rate']['initial']==.00001 and plan['learning_rate']['end']==.00003
if (T/'comparison/manifest.json').exists():assert not read(T/'comparison/manifest.json')['published_ready'],'Published comparison frozen: create another training version.'
assert not (T/'published.json').exists(),'Published ProPlus training is frozen.'
assert smoke or read(T/'smoke-receipt.json')['weights_changed']
import torch,numpy as np,yaml
torch.set_num_threads(2);assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
random.seed(20261025);np.random.seed(20261025);torch.manual_seed(20261025);torch.cuda.manual_seed_all(20261025)
sys.path[:0]=[str(G),str(G/'GPT_SoVITS')]
from tools.portable_runtime import activate
activate(change_cwd=True)
from AR.data.dataset import Text2SemanticDataset
from AR.models.t2s_lightning_module import Text2SemanticLightningModule
from AR.modules.optim import ScaledAdam
from torch.utils.data import DataLoader
base=torch.load(M/'s1v3.ckpt',map_location='cpu',weights_only=False);config=base['config'];config['train'].update(epochs=1 if smoke else 10,batch_size=1,save_every_n_epoch=2,precision='bf16-mixed',gradient_clip=1.0,if_dpo=False,gradient_accumulation=4)
config['optimizer'].update(lr=.0003,lr_init=.00001,lr_end=.00003)
config['data'].update(max_sec=54,num_workers=0)
config.update(pretrained_s1=str(M/'s1v3.ckpt'),train_semantic_path=str(F/'6-name2semantic-train.tsv'),train_phoneme_path=str(F/'2-name2text-train.txt'),output_dir=str(T/'logs/stage1'))
model=Text2SemanticLightningModule(config,T,is_train=False);model.load_state_dict(base['weight'],strict=True);del base
train=Text2SemanticDataset(str(F/'2-name2text-train.txt'),str(F/'6-name2semantic-train.tsv'),max_sec=20,pad_val=1024)
dev=Text2SemanticDataset(str(F/'2-name2text-validation.txt'),str(F/'6-name2semantic-validation.tsv'),max_sec=20,pad_val=1024)
manifest=read(T/'dataset/manifest.json');assert len(train.item_names)==len(manifest['train']),'Dataset silently filtered/doubled rows; audit before training.'
# The upstream dev dataset may repeat fewer than 100 samples internally; evaluate each held-out ID once.
dev_unique=[];seen=set()
for i,name in enumerate(dev.item_names):
 if name not in seen:seen.add(name);dev_unique.append(i)
loader=DataLoader(train,batch_size=1,shuffle=True,num_workers=0,collate_fn=train.collate,generator=torch.Generator().manual_seed(20261025))
model=model.cuda();params=list(model.model.parameters());names=[[n for n,_ in model.model.named_parameters()]]
optimizer=ScaledAdam(params,lr=.0003,betas=(.9,.95),clipping_scale=2.,parameters_names=names,show_dominant_parameters=False,clipping_update_period=1000)
epochs=1 if smoke else 10;accum=4;steps_per_epoch=math.ceil((min(8,len(loader)) if smoke else len(loader))/accum);total_updates=steps_per_epoch*epochs;warmup=max(2,min(150,total_updates//5))
config['optimizer'].update(warmup_steps=warmup,decay_steps=total_updates);config['train']['exp_name']='milkgreen-proplus-stage1'
config.update(implementation={'optimizer':'upstream ScaledAdam','actual_lr_schedule':'explicit warmup+cosine, bypass upstream hard-coded 0.002 scheduler','gradient_accumulation':'loss divided by group size; tail group flushed','loader_filter_max_sec':20,'inference_max_sec':54,'acoustic_training':False,'human_training_labels_verified':False})
(T/'configs'/('stage1-'+args.stage+'.yaml')).write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False),encoding='utf-8')
acoustic={r['path']:r['sha256'] for r in read(T/'official-assets.json')['files']}
probe_keys=[k for k,v in model.state_dict().items() if v.is_floating_point()][:6];before={k:model.state_dict()[k].detach().cpu().clone() for k in probe_keys}
def fingerprint():return hashlib.sha256(b''.join(model.state_dict()[k].detach().float().cpu().numpy().tobytes() for k in probe_keys)).hexdigest()
initial=fingerprint();history=[];exports=[];updates=0;started=time.monotonic()
def move(batch):return {k:v.cuda(non_blocking=False) if isinstance(v,torch.Tensor) else v for k,v in batch.items()}
def forward(batch):return model.model.forward_old(batch['phoneme_ids'],batch['phoneme_ids_len'],batch['semantic_ids'],batch['semantic_ids_len'],batch['bert_feature'])
def evaluate():
 model.eval();losses=[];acc=[]
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
  for i in dev_unique:
   loss,a=forward(move(dev.collate([dev[i]])));assert torch.isfinite(loss);losses.append(float(loss));acc.append(float(a))
 return float(np.mean(losses)),float(np.mean(acc))
for epoch in range(1,epochs+1):
 model.train();optimizer.zero_grad(set_to_none=True);losses=[];acc=[];limit=min(8,len(loader)) if smoke else len(loader)
 for i,batch in enumerate(loader):
  if i>=limit:break
  pos=i%accum;group_size=min(accum,limit-(i-pos))
  with torch.autocast('cuda',dtype=torch.bfloat16):loss,a=forward(move(batch))
  assert torch.isfinite(loss),f'Nonfinite loss at epoch {epoch}, item {i}'
  (loss/group_size).backward();losses.append(float(loss.detach()));acc.append(float(a))
  if pos==group_size-1:
   grad=torch.nn.utils.clip_grad_norm_(params,1.0,error_if_nonfinite=True)
   if updates<warmup:lr=.00001+(.0003-.00001)*(updates+1)/warmup
   else:lr=.00003+(.0003-.00003)*.5*(1+math.cos(math.pi*min(1,(updates-warmup)/max(1,total_updates-warmup))))
   for group in optimizer.param_groups:group['lr']=lr
   optimizer.step();optimizer.zero_grad(set_to_none=True);updates+=1
  if (i+1)%20==0:
   status={'stage':'training-proplus-gpt','updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'epoch':epoch,'epochs':epochs,'items_done':i+1,'items_total':limit,'optimizer_updates':updates,'actual_learning_rate':optimizer.param_groups[0]['lr'],'average_loss':float(np.mean(losses)),'elapsed_seconds':round(time.monotonic()-started,1),'sovits_training':False}
   write(T/('status-smoke.json' if smoke else 'status.json'),status);print(json.dumps(status),flush=True)
 val_loss,val_acc=evaluate();row={'epoch':epoch,'train_loss':float(np.mean(losses)),'train_top3_accuracy':float(np.mean(acc)),'validation_loss':val_loss,'validation_top3_accuracy':val_acc,'validation_unique_count':len(dev_unique),'optimizer_updates':updates,'actual_lr':optimizer.param_groups[0]['lr'],'elapsed_seconds':round(time.monotonic()-started,2)};history.append(row);print(json.dumps(row),flush=True)
 if smoke or epoch%2==0:
  dest=T/'checkpoints'/('smoke' if smoke else 'gpt');dest.mkdir(parents=True,exist_ok=True);path=dest/f'milkgreen-proplus-stage1-e{epoch}.ckpt'
  payload={'weight':collections.OrderedDict((k,v.detach().half().cpu()) for k,v in model.state_dict().items()),'config':config,'info':f'GPT-e{epoch}; Stage1 only; official ProPlus source weights untouched','dataset_sha256':sha(T/'dataset/manifest.json')}
  with path.open('wb') as f:torch.save(payload,f)
  reload=torch.load(path,map_location='cpu',weights_only=False);assert set(reload['weight'])==set(model.state_dict());assert all(torch.isfinite(v).all() for v in reload['weight'].values());del reload
  exports.append({'epoch':epoch,'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'validation_loss':val_loss,'validation_top3_accuracy':val_acc});write(T/('smoke-checkpoints.json' if smoke else 'checkpoints.json'),exports)
  for p,digest in acoustic.items():assert sha(p)==digest,'Official acoustic model changed!'
 write(T/('history-smoke.json' if smoke else 'history.json'),history)
changed=fingerprint()!=initial;assert changed and updates>0
receipt={'stage':'GPT Stage 1 only','epochs_completed':epochs,'optimizer_updates':updates,'weights_changed':changed,'probe_parameter_change_l2':{k:float(torch.linalg.vector_norm(model.state_dict()[k].detach().float().cpu()-v)) for k,v in before.items()},'initial_probe_sha256':initial,'final_probe_sha256':fingerprint(),'exports':exports,'official_acoustic_weights_sha256_unchanged':acoustic,'dataset_sha256':sha(T/'dataset/manifest.json'),'validation_unique_count':len(dev_unique),'training_human_labels_verified':False,'source_audio_uploaded':False,'elapsed_seconds':round(time.monotonic()-started,2),'gpu_peak_allocated_mib':round(torch.cuda.max_memory_allocated()/1024**2),'inference_reload_pending':True,'live_qq_voice_deployed':False}
write(T/('smoke-receipt.json' if smoke else 'training-receipt.json'),receipt)
write(T/('status-smoke.json' if smoke else 'status.json'),{'stage':'gpt-training-complete','epochs':epochs,'optimizer_updates':updates,'weights_changed':changed,'sovits_training':False,'inference_validation_pending':True})
print(json.dumps({'training_finished':True,'epochs':epochs,'optimizer_updates':updates,'weights_changed':changed,'exports':len(exports)}),flush=True)
