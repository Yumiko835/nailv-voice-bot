"""Full ProPlus acoustic GAN fine-tuning, using upstream models and loss objectives."""

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
import argparse,random,math,collections,gc
p=argparse.ArgumentParser();p.add_argument('mode',choices=['smoke','train']);p.add_argument('--batch',type=int,default=2);a=p.parse_args();smoke=a.mode=='smoke'
assert read(T/'feature-verification.json')['ready'];torch=runtime();import numpy as np,soundfile as sf
from torch.utils.data import Dataset,DataLoader
from module.models import SynthesizerTrn,MultiPeriodDiscriminator
from module.data_utils import TextAudioSpeakerCollate
from module.mel_processing import spectrogram_torch,mel_spectrogram_torch,spec_to_mel_torch
from module.losses import discriminator_loss,generator_loss,feature_loss,kl_loss
from module import commons
from process_ckpt import load_sovits_new,savee
import utils
torch.manual_seed(20261025);random.seed(20261025);np.random.seed(20261025);assert torch.cuda.is_bf16_supported()
config=read(G/'GPT_SoVITS/configs/s2v2ProPlus.json');config['model']['version']='v2ProPlus';config['train'].update(epochs=1 if smoke else 10,batch_size=a.batch,learning_rate=.0001,text_low_lr_rate=.4,fp16_run=False,grad_ckpt=True,num_workers=0,save_every_epoch=2,pretrained_s2G=str(M/'v2Pro/s2Gv2ProPlus.pth'),pretrained_s2D=str(M/'v2Pro/s2Dv2ProPlus.pth'));config['data']['exp_dir']=str(F);config.update(name='milkgreen-proplus',version='v2ProPlus',save_weight_dir=str(T/'checkpoints'/('smoke' if smoke else 'sovits')),implementation='Official Generator/Discriminator and GAN+feature+mel+KL losses; BF16 autocast with FP32 spectral losses; no silent bad-sample substitution; every training row once per epoch.')
write(T/'configs'/('stage2-'+a.mode+'.json'),config);h=utils.HParams(**config);ds=read(T/'dataset/manifest.json');rows=sorted(ds['train'],key=lambda r:r['seconds'],reverse=True)[:a.batch] if smoke else ds['train'];phone_lines=(F/'2-name2text-train.txt').read_text(encoding='utf-8').splitlines();from text import cleaned_text_to_sequence
phones={line.split('\t')[0]:cleaned_text_to_sequence(line.split('\t')[1].split(),'v2ProPlus') for line in phone_lines}
class StrictDataset(Dataset):
 def __len__(self):return len(rows)
 def __getitem__(self,index):
  c=rows[index];name=c['id']+'.wav';x,sr=sf.read(F/'5-wav32k'/name,dtype='float32');assert sr==32000;wave=torch.from_numpy(x).unsqueeze(0);spec=spectrogram_torch(wave,h.data.filter_length,32000,h.data.hop_length,h.data.win_length,center=False)[0];ssl=torch.load(F/'4-cnhubert'/(name+'.pt'),map_location='cpu',weights_only=True);sv=torch.load(F/'7-sv_cn'/(name+'.pt'),map_location='cpu',weights_only=True)
  diff=spec.shape[-1]-ssl.shape[-1];assert abs(diff)<=1,(name,ssl.shape,spec.shape)
  if diff==1:ssl=torch.nn.functional.pad(ssl.float(),(0,1),mode='replicate').to(ssl.dtype)
  elif diff==-1:ssl=ssl[...,:spec.shape[-1]]
  assert torch.isfinite(ssl).all() and torch.isfinite(spec).all() and torch.isfinite(sv).all()
  return ssl,spec,wave,torch.tensor(phones[name],dtype=torch.float32),sv
loader=DataLoader(StrictDataset(),batch_size=a.batch,shuffle=True,num_workers=0,drop_last=False,collate_fn=TextAudioSpeakerCollate(version='v2ProPlus'),generator=torch.Generator().manual_seed(20261025))
net_g=SynthesizerTrn(h.data.filter_length//2+1,h.train.segment_size//h.data.hop_length,n_speakers=h.data.n_speakers,**h.model);base=load_sovits_new(str(M/'v2Pro/s2Gv2ProPlus.pth'));match=net_g.load_state_dict(base['weight'],strict=False);assert not match.unexpected_keys and all(k.startswith('enc_q.') for k in match.missing_keys),match;del base
net_d=MultiPeriodDiscriminator(h.model.use_spectral_norm,version='v2ProPlus');net_d.load_state_dict(torch.load(M/'v2Pro/s2Dv2ProPlus.pth',map_location='cpu',weights_only=False)['weight'],strict=True);net_g=net_g.cuda();net_d=net_d.cuda()
print(json.dumps({'stage2_models_loaded':True,'batch_size':a.batch,'smoke':smoke}),flush=True)
# Preserve the semantic codebook coordinates used by the independently trained
# GPT. Decoder, reference encoder, duration/text conditioning and GAN still train.
for module in [net_g.ssl_proj,net_g.quantizer]:module.requires_grad_(False)
special=[net_g.enc_p.text_embedding,net_g.enc_p.encoder_text,net_g.enc_p.mrte];special_ids={id(p) for module in special for p in module.parameters()};groups=[{'params':[p for p in net_g.parameters() if p.requires_grad and id(p) not in special_ids],'lr':.0001}]+[{'params':list(module.parameters()),'lr':.00004} for module in special];optim_g=torch.optim.AdamW(groups,lr=.0001,betas=h.train.betas,eps=h.train.eps,foreach=False);optim_d=torch.optim.AdamW(net_d.parameters(),lr=.0001,betas=h.train.betas,eps=h.train.eps,foreach=False)
probe=[k for k,v in net_g.state_dict().items() if v.is_floating_point() and k.startswith(('dec.','ref_enc.'))][:6]
def fingerprint():return hashlib.sha256(b''.join(net_g.state_dict()[k].detach().float().cpu().numpy().tobytes() for k in probe)).hexdigest()
initial=fingerprint();history=[];exports=[];start=1;updates=0;started=time.monotonic();resume=T/'logs/stage2/latest-resume.pt'
if not smoke and resume.exists():
 ck=torch.load(resume,map_location='cpu',weights_only=False);assert ck['dataset_sha256']==sha(T/'dataset/manifest.json');net_g.load_state_dict(ck['g'],strict=True);net_d.load_state_dict(ck['d'],strict=True);optim_g.load_state_dict(ck['optim_g']);optim_d.load_state_dict(ck['optim_d']);start=ck['epoch']+1;updates=ck['updates'];history=ck['history'];exports=ck['exports'];initial=ck['initial_fingerprint'];del ck;gc.collect()
for epoch in range(start,h.train.epochs+1):
 net_g.train();net_d.train();losses=[];count=0
 for i,batch in enumerate(loader,1):
  if smoke:print('smoke: batch ready',flush=True)
  ssl,ssl_len,spec,spec_len,y,y_len,text,text_len,sv=[x.cuda(non_blocking=False) for x in batch];count+=int(y.shape[0]);optim_g.zero_grad(set_to_none=True);optim_d.zero_grad(set_to_none=True)
  for p in net_d.parameters():p.requires_grad_(True)
  with torch.autocast('cuda',dtype=torch.bfloat16):
   y_hat,kl_ssl,ids_slice,x_mask,z_mask,latents,stats=net_g(ssl,spec,spec_len,text,text_len,sv);dr,dg,_,_=net_d(commons.slice_segments(y,ids_slice*h.data.hop_length,h.train.segment_size),y_hat.detach());loss_d,_,_=discriminator_loss(dr,dg)
  if smoke:print('smoke: G/D forward complete',flush=True)
  assert torch.isfinite(loss_d);loss_d.backward();grad_d=commons.clip_grad_value_(net_d.parameters(),None);assert math.isfinite(float(grad_d));optim_d.step()
  if smoke:print('smoke: discriminator update complete',flush=True)
  # The discriminator's weights are constant for the generator step; computing
  # unused D gradients would only consume memory and is not part of its update.
  for p in net_d.parameters():p.requires_grad_(False)
  with torch.autocast('cuda',dtype=torch.bfloat16):dr,dg,fr,fg=net_d(commons.slice_segments(y,ids_slice*h.data.hop_length,h.train.segment_size),y_hat)
  with torch.autocast('cuda',enabled=False):
   mel=spec_to_mel_torch(spec.float(),h.data.filter_length,h.data.n_mel_channels,32000,h.data.mel_fmin,h.data.mel_fmax);ymel=commons.slice_segments(mel,ids_slice,h.train.segment_size//h.data.hop_length);pred=mel_spectrogram_torch(y_hat.squeeze(1).float(),h.data.filter_length,h.data.n_mel_channels,32000,h.data.hop_length,h.data.win_length,h.data.mel_fmin,h.data.mel_fmax);lm=torch.nn.functional.l1_loss(ymel,pred)*h.train.c_mel;z,zp,mp,lp,mq,lq=latents;lk=kl_loss(zp,lq,mp,lp,z_mask)*h.train.c_kl;lf=feature_loss(fr,fg);lg,_=generator_loss(dg);loss_g=lg+lf+lm+kl_ssl.float()+lk
  assert torch.isfinite(loss_g);loss_g.backward();grad_g=commons.clip_grad_value_(net_g.parameters(),None);assert math.isfinite(float(grad_g));optim_g.step();updates+=1;losses.append([float(loss_d.detach()),float(loss_g.detach()),float(lm.detach()),float(lk.detach())])
  if i%20==0:status('training-proplus-sovits',epoch=epoch,epochs=h.train.epochs,items_done=count,items_total=len(rows),updates=updates,batch_size=a.batch,loss_mel=float(lm.detach()),elapsed_seconds=round(time.monotonic()-started,1))
 assert count==len(rows),'Training rows must not be silently removed or duplicated'
 result={'epoch':epoch,'loss_disc':float(np.mean(losses,axis=0)[0]),'loss_generator':float(np.mean(losses,axis=0)[1]),'loss_mel':float(np.mean(losses,axis=0)[2]),'loss_kl':float(np.mean(losses,axis=0)[3]),'seen_training_rows':count,'updates':updates,'elapsed_seconds':round(time.monotonic()-started,2)};history.append(result);write(T/('history-stage2-smoke.json' if smoke else 'history-stage2.json'),history)
 if epoch%2==0 or smoke:
  name='milkgreen-proplus'+('-smoke' if smoke else '')+'-e'+str(epoch);response=savee(net_g.state_dict(),name,epoch,updates,h,model_version='v2ProPlus');assert response=='Success.',response;path=Path(h.save_weight_dir)/(name+'.pth');reloaded=load_sovits_new(str(path));assert all(torch.isfinite(v).all() for v in reloaded['weight'].values());del reloaded;exports.append({'epoch':epoch,'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size});verify_protected()
  if not smoke:
   temp=resume.with_suffix('.tmp')
   with temp.open('wb') as stream:torch.save({'g':net_g.state_dict(),'d':net_d.state_dict(),'optim_g':optim_g.state_dict(),'optim_d':optim_d.state_dict(),'epoch':epoch,'updates':updates,'history':history,'exports':exports,'dataset_sha256':sha(T/'dataset/manifest.json'),'initial_fingerprint':initial},stream)
   temp.replace(resume)
 for optimizer in [optim_g,optim_d]:
  for group in optimizer.param_groups:group['lr']*=h.train.lr_decay
 print(json.dumps(result,ensure_ascii=False),flush=True)
assert fingerprint()!=initial and updates>0
receipt={'stage':'ProPlus Stage 2 full acoustic GAN','epochs_completed':h.train.epochs,'weights_changed':True,'initial_fingerprint':initial,'final_fingerprint':fingerprint(),'exports':exports,'optimizer_updates':updates,'batch_size':a.batch,'train_rows':len(rows),'dataset_sha256':sha(T/'dataset/manifest.json'),'all_official_source_weights_unchanged':True,'elapsed_seconds':round(time.monotonic()-started,2),'gpu_peak_allocated_mib':round(torch.cuda.max_memory_allocated()/2**20),'human_quality_verified':False};write(T/('stage2-smoke-receipt.json' if smoke else 'stage2-training-receipt.json'),receipt);status('proplus-sovits-training-complete',epochs=h.train.epochs,exports=len(exports),smoke=smoke,weights_changed=True)
