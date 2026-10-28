
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
R=ROOT/'runtime/cosyvoice3'
OLD_R=ROOT/'runtime/cosyvoice2'
T=ROOT/'voice/training/cosyvoice3-personal-20261026'
O=ROOT/'voice/comparison/cosyvoice3-20261026'
BASE=R/'models/Fun-CosyVoice3-0.5B-2512'
def setup(offline=True):
    for key,folder in {'HF_HOME':'hf','TORCH_HOME':'torch','NUMBA_CACHE_DIR':'numba','MPLCONFIGDIR':'matplotlib','MODELSCOPE_CACHE':'modelscope','TEMP':'tmp','TMP':'tmp','XDG_CACHE_HOME':'xdg'}.items():
        p=R/'cache'/folder;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONUTF8='1',HF_HUB_DISABLE_XET='1')
    if offline:os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    os.environ.pop('onnx_path',None)
    # Reuse installed packages and already CV3-capable upstream source read-only.
    # No dependency changes to the working CosyVoice2 environment.
    sys.path[:0]=[str(R/'packages'),str(OLD_R/'src'),str(OLD_R/'src/third_party/Matcha-TTS'),str(ROOT/'tools')]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def make_lm():
    import yaml,torch
    from hyperpyyaml import load_hyperpyyaml
    prepare_blank_encoder()
    node=yaml.compose((BASE/'cosyvoice3.yaml').read_text(encoding='utf-8'))
    keep={'llm','llm_input_size','llm_output_size','spk_embed_dim','qwen_pretrain_path'}
    node.value=[(k,v) for k,v in node.value if k.value in keep or k.value.startswith('__set_seed')]
    conf=load_hyperpyyaml(yaml.serialize(node),overrides={'qwen_pretrain_path':str(BASE/'CosyVoice-BlankEN')})
    model=conf['llm'];state=torch.load(BASE/'llm.pt',map_location='cpu',mmap=True,weights_only=True);model.load_state_dict(state,strict=True);del state
    assert type(model).__name__=='CosyVoice3LM'
    return model
def prepare_blank_encoder():
    # llm.pt contains every Qwen parameter and is loaded strictly below.
    # Construct its exact official architecture from config rather than fetching
    # an additional redundant random-initialization checkpoint in BlankEN.
    from transformers import Qwen2Config,Qwen2ForCausalLM
    if getattr(Qwen2ForCausalLM,'_cv3_local_config_only',False):return
    original=Qwen2ForCausalLM.from_pretrained
    def config_only(cls,path,*args,**kwargs):
        if Path(path).resolve()==(BASE/'CosyVoice-BlankEN').resolve():return cls(Qwen2Config.from_pretrained(path,local_files_only=True))
        return original(path,*args,**kwargs)
    Qwen2ForCausalLM.from_pretrained=classmethod(config_only);Qwen2ForCausalLM._cv3_local_config_only=True
def lora_tools():
    import ast
    source=R/'scripts/legacy_lora_tools.py'
    if not source.exists():source=Path(project_path("source-work/cosyvoice2-curated-v2-20261026/common.py"))
    tree=ast.parse(source.read_text(encoding='utf-8'));keep={'inject_lora','training_forward_patch','adapter_state','export_adapter'}
    namespace=globals();exec(compile(ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in keep],type_ignores=[]),str(source),'exec'),namespace)
    return tuple(namespace[x] for x in ['inject_lora','training_forward_patch','adapter_state','export_adapter'])
