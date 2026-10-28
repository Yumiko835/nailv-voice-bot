
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
import os,sys,json,hashlib
ROOT=Path(project_path(''))
R=ROOT/'runtime/cosyvoice2'
T=ROOT/'voice/training/cosyvoice2-curated-v2-20261026'
O=ROOT/'voice/comparison/cosyvoice2-20261026'
BASE=R/'models/CosyVoice2-0.5B'
def setup():
    for key,folder in {'HF_HOME':'hf','TORCH_HOME':'torch','NUMBA_CACHE_DIR':'numba','MPLCONFIGDIR':'matplotlib','MODELSCOPE_CACHE':'modelscope','TEMP':'tmp','TMP':'tmp'}.items():os.environ[key]=str(R/'cache'/folder)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONUTF8='1')
    os.environ.pop('onnx_path',None)
    sys.path[:0]=[str(R/'src'),str(R/'src/third_party/Matcha-TTS'),str(ROOT/'tools')]
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def integration_sources():
    local=T/'scripts/integration'
    return local if (local/'infer.py').is_file() else Path(project_path("source-work/cosyvoice2-20261026"))
def make_lm():
    import yaml
    from hyperpyyaml import load_hyperpyyaml
    node=yaml.compose((BASE/'cosyvoice2.yaml').read_text(encoding='utf-8'))
    names={'llm','llm_input_size','llm_output_size','spk_embed_dim','qwen_pretrain_path'}
    node.value=[(k,v) for k,v in node.value if k.value in names or k.value.startswith('__set_seed')]
    config=load_hyperpyyaml(yaml.serialize(node),overrides={'qwen_pretrain_path':str(BASE/'CosyVoice-BlankEN')})
    import torch
    model=config['llm']
    state=torch.load(BASE/'llm.pt',map_location='cpu',weights_only=True,mmap=True)
    model.load_state_dict(state,strict=True);del state
    return model

def inject_lora(model,rank=8,alpha=16,dropout=.05):
    import torch
    from torch import nn
    import torch.nn.functional as F
    class LoRALinear(nn.Module):
        def __init__(self,base):
            super().__init__();self.base=base;self.scale=alpha/rank;self.dropout=nn.Dropout(dropout)
            self.lora_A=nn.Parameter(torch.empty(rank,base.in_features,device=base.weight.device,dtype=torch.float32))
            self.lora_B=nn.Parameter(torch.zeros(base.out_features,rank,device=base.weight.device,dtype=torch.float32))
            nn.init.kaiming_uniform_(self.lora_A,a=5**.5)
        def forward(self,x):return self.base(x)+F.linear(F.linear(self.dropout(x),self.lora_A),self.lora_B)*self.scale
    for p in model.parameters():p.requires_grad_(False)
    modules={name:module for name,module in model.named_modules() if name.endswith(('.self_attn.q_proj','.self_attn.v_proj')) and isinstance(module,nn.Linear)}
    for name,module in modules.items():
        parent,attr=name.rsplit('.',1);setattr(model.get_submodule(parent),attr,LoRALinear(module))
    return list(modules)

def training_forward_patch(model):
    import types,torch
    from cosyvoice.utils.mask import make_pad_mask
    # Same official speech-token SFT objective. Skip the unrelated Qwen text
    # vocabulary head and return only its final hidden representation.
    def encoder_forward(self,xs,xs_lens):
        mask=~make_pad_mask(xs_lens,xs.shape[1])
        result=self.model.model(inputs_embeds=xs,attention_mask=mask,output_hidden_states=False,return_dict=True,use_cache=False)
        return result.last_hidden_state,mask.unsqueeze(1)
    model.llm.forward=types.MethodType(encoder_forward,model.llm)
    model.llm.model.config.use_cache=False
    model.llm.model.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    original=model.criterion_ce.forward
    model.criterion_ce.forward=lambda x,target:original(x.float(),target)

def adapter_state(model,names):
    return {name:{'A':model.get_submodule(name).lora_A.detach().cpu().clone(),
                  'B':model.get_submodule(name).lora_B.detach().cpu().clone(),
                  'scale':model.get_submodule(name).scale} for name in names}

def export_adapter(model,names,epoch):
    import torch
    folder=T/'checkpoints';folder.mkdir(exist_ok=True)
    adapter=adapter_state(model,names)
    adapter_path=folder/f'adapter-e{epoch}.pt';torch.save({'adapters':adapter,'epoch':epoch,'base_sha256':sha(BASE/'llm.pt')},adapter_path)
    # Merge only the low-rank delta into ORIGINAL FP32 weights. Do not export
    # the BF16-rounded frozen base used during training.
    state=torch.load(BASE/'llm.pt',map_location='cpu',weights_only=True,mmap=True)
    for name,values in adapter.items():
        key=name+'.weight';assert key in state
        state[key]=state[key].float()+values['scale']*(values['B'].float()@values['A'].float())
    merged=folder/f'llm-e{epoch}.pt';torch.save(state,merged);del state
    return {'epoch':epoch,'adapter':str(adapter_path),'merged':str(merged),'sha256':sha(merged)}
