"""CV3-native speech-LM LoRA trial, quarter/half/full passes; no CV2 weights."""

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
setup()
import argparse,time,random,math,contextlib,threading,subprocess,gc,collections
import torch
sys.path.insert(0,str(OLD_R/'scripts'));import cosy_chat_backend as coordination
p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');args=p.parse_args()
assert not (T/'checkpoints.json').exists(),'Completed candidates are immutable; use a fresh study to continue.'
data=read(T/'dataset.json');train=data['train'];val=data['validation'];assert len(val)==10 and len(data['holdout'])==10
features={x['id']:torch.load(x['feature'],map_location='cpu',weights_only=True) for x in train+val}
inject,patch,adapter_state,export=lora_tools();torch.set_num_threads(2)
plan={'base':str(BASE/'llm.pt'),'base_sha256':sha(BASE/'llm.pt'),'architecture':'CosyVoice3LM',
    'learning_rate_peak':1e-5,'schedule':'two-step warmup, cosine decay to20% over one dataset pass',
    'rank':8,'alpha':16,'dropout':.05,'target_modules':['self_attn.q_proj','self_attn.v_proj'],
    'micro_batch':1,'gradient_accumulation':4,'gradient_checkpointing':True,'seed':1986,
    'save_fractions':[.25,.5,.8,1.0],'frozen':['official CV3 Flow','official CV3 HiFT','all original base parameters','chat LLM'],
    'source_dataset_sha256':sha(T/'dataset.json'),'training_clips':len(train),'training_minutes':data['train_minutes'],
    'fresh_CV3_tokens':True,'CV2_adapters_used':False,'speech_action_interleaving':True,'human_similarity_verified':False}
write(T/('smoke-plan.json' if args.smoke else 'training-plan.json'),plan)
telemetry=[];stop=threading.Event();started=time.monotonic();model=None
def monitor():
    while not stop.wait(1):
        try:telemetry.append(int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).splitlines()[0]))
        except Exception:pass
thread=threading.Thread(target=monitor,daemon=True)
try:
 with coordination.gpu_lease('cosyvoice3-smoke' if args.smoke else 'cosyvoice3-training'):
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported();free,total=torch.cuda.mem_get_info();assert free>2.7*1024**3
    torch.cuda.set_per_process_memory_fraction(min(4.1*1024**3,free-512*1024**2)/total);torch.cuda.reset_peak_memory_stats();thread.start()
    with (T/'training-load.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):model=make_lm()
    model.to(device='cuda',dtype=torch.bfloat16);names=inject(model);patch(model)
    params=[p for p in model.parameters() if p.requires_grad];plan['trainable_parameters']=sum(p.numel() for p in params);plan['lora_module_count']=len(names)
    write(T/('smoke-plan.json' if args.smoke else 'training-plan.json'),plan)
    probe=model.speech_embedding.weight[:2].detach().cpu().clone();opt=torch.optim.AdamW(params,lr=1e-5,weight_decay=.01)
    def batch(row):
        f=features[row['id']];out={}
        for key in ['text_token','speech_token','instruct_token']:
            out[key]=f[key][None,:];out[key+'_len']=torch.tensor([len(f[key])],dtype=torch.int32)
        return out
    def evaluate():
        model.eval();state=random.getstate();random.seed(1986);values=[]
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            for row in val:
                out=model(batch(row),torch.device('cuda'));values.append(float(out['loss']));del out
        random.setstate(state);model.train();return sum(values)/len(values)
    baseline=evaluate();print(json.dumps({'loaded_cv3_base':True,'baseline_validation_loss':baseline,'trainable_parameters':plan['trainable_parameters']}),flush=True)
    model.train();opt.zero_grad(set_to_none=True)
    if args.smoke:
        rows=sorted(train,key=lambda r:r['seconds'],reverse=True)[:3];before=[p.detach().clone() for p in params]
        for row in rows:
            with torch.autocast('cuda',dtype=torch.bfloat16):out=model(batch(row),torch.device('cuda'));loss=out['loss']/len(rows)
            assert torch.isfinite(loss);loss.backward();del out,loss
        norm=torch.nn.utils.clip_grad_norm_(params,1.,error_if_nonfinite=True);opt.step()
        assert any(not torch.equal(a,b) for a,b in zip(before,params));assert torch.equal(probe,model.speech_embedding.weight[:2].detach().cpu())
        write(T/'smoke-receipt.json',{'passed':True,'real_backward_and_optimizer_step':True,'longest_clips_seconds':[r['seconds'] for r in rows],'frozen_probe_unchanged':True,'gradient_norm':float(norm),'baseline_validation_loss':baseline})
    else:
        buckets=collections.defaultdict(list);random.seed(1986)
        for row in train:buckets[row['speech_action']].append(row)
        for rows in buckets.values():random.shuffle(rows)
        # Spread each speech-act stratum throughout the pass. Plain round-robin
        # would exhaust rare acts early and bias the later checkpoints.
        distributed=[((i+.5)/len(rows),key,row) for key,rows in sorted(buckets.items()) for i,row in enumerate(rows)]
        order=[row for _,_,row in sorted(distributed,key=lambda x:(x[0],x[1]))]
        assert len(order)==len(train) and len({r['id'] for r in order})==len(train)
        write(T/'training-order.json',{'ids':[r['id'] for r in order],'no_oversampling':True})
        steps=math.ceil(len(train)/4);marks={max(1,round(steps*f)):f for f in [.25,.5,.8,1.]};step=0;loss_sum=0.;saved=[]
        for i,row in enumerate(order):
            denom=min(4,len(order)-i//4*4)
            with torch.autocast('cuda',dtype=torch.bfloat16):out=model(batch(row),torch.device('cuda'));loss=out['loss']
            assert torch.isfinite(loss);loss_sum+=float(loss.detach());(loss/denom).backward();del out,loss
            if (i+1)%4==0 or i+1==len(order):
                step+=1;progress=(step-1)/max(1,steps-1);scale=min(1.,step/2)*(.2+.8*.5*(1+math.cos(math.pi*progress)))
                for group in opt.param_groups:group['lr']=1e-5*scale
                torch.nn.utils.clip_grad_norm_(params,1.,error_if_nonfinite=True);opt.step();opt.zero_grad(set_to_none=True)
                if step in marks:
                    fraction=marks[step];validation=evaluate();saved_model=export(model,names,fraction);saved_model.update(dataset_pass_fraction=fraction,optimizer_steps=step,validation_loss=validation)
                    saved.append(saved_model);write(T/'checkpoints.json',{'models':saved,'baseline_validation_loss':baseline,'human_similarity_verified':False})
                    print(json.dumps({'saved_fraction':fraction,'validation_loss':validation}),flush=True)
            if (i+1)%16==0 or i+1==len(order):
                status={'stage':'training','completed':i+1,'total':len(order),'optimizer_step':step,'loss_mean':loss_sum/(i+1),'seconds':time.monotonic()-started,'peak_torch_MiB':torch.cuda.max_memory_allocated()/1024**2};write(T/'status.json',status);print(json.dumps(status),flush=True)
        assert torch.equal(probe,model.speech_embedding.weight[:2].detach().cpu())
        write(T/'training-receipt.json',{'completed':True,'baseline_validation_loss':baseline,'models':saved,'all_unique_training_clips_seen_once':True,'frozen_probe_unchanged':True,'seconds':time.monotonic()-started,'human_similarity_verified':False})
finally:
    stop.set()
    if thread.is_alive():thread.join(timeout=2)
    write(T/('smoke-memory.json' if args.smoke else 'training-memory.json'),{'total_gpu_peak_MiB':max(telemetry,default=0),'peak_torch_MiB':torch.cuda.max_memory_allocated()/1024**2,'samples':telemetry})
    if model is not None:del model
    gc.collect();torch.cuda.empty_cache()
