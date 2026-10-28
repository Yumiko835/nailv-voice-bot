
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
import os,sys,json,hashlib,time
ROOT=Path(project_path(''));A=ROOT/'voice/training/v5dev-newsource-20261025';T=ROOT/'voice/training/v2proplus-newsource-20261025';G=Path(dependency_path("gpt_sovits",''));M=ROOT/'runtime/models/gpt-sovits-upgrade/GPT_SoVITS/pretrained_models';F=T/'features';FF=dependency_path('ffmpeg')
for folder in ['configs','scripts','dataset','prompts/source','prompts/plans','checkpoints/gpt','checkpoints/sovits','checkpoints/smoke','logs/stage1','logs/stage2','features/3-bert','features/4-cnhubert','features/5-wav32k','features/7-sv_cn','cache','generated']:(T/folder).mkdir(parents=True,exist_ok=True)
for k,v in {'HF_HOME':'huggingface','NUMBA_CACHE_DIR':'numba','LIBROSA_CACHE_DIR':'librosa','MPLCONFIGDIR':'matplotlib','TORCH_HOME':'torch','MODELSCOPE_CACHE':'modelscope','TEMP':'.','TMP':'.','PIP_CACHE_DIR':'pip','UV_CACHE_DIR':'uv'}.items():os.environ[k]=str(T/'cache'/v)
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',G2PW='0',version='v2ProPlus',hz='25hz',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',USE_LIBUV='0');os.environ['PATH']=str(FF.parent)+os.pathsep+os.environ.get('PATH','')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save_tensor(x,p):
 with Path(p).open('wb') as stream:
  import torch
  torch.save(x,stream)
def status(stage,**kwargs):
 data={'stage':stage,'updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'project':'v2proplus-newsource-20261025',**kwargs};write(T/'status.json',data);print(json.dumps(data,ensure_ascii=False),flush=True)
def runtime():
 import torch
 torch.set_num_threads(2);assert torch.cuda.is_available(),'CUDA required'
 sys.path[:0]=[str(G),str(G/'GPT_SoVITS'),str(G/'GPT_SoVITS/eres2net')]
 from tools.portable_runtime import activate
 activate(change_cwd=False);os.chdir(T)
 # Upstream Chinese frontend has relative model/cache paths. Resolve its
 # read-only assets explicitly instead of changing the shared engine folder.
 import importlib
 module=importlib.import_module('text.g2pw.g2pw');original=module.G2PWPinyin.__init__
 def local_g2pw(self,*args,**kwargs):
  kwargs['model_dir']=str(G/'GPT_SoVITS/text/G2PWModel');kwargs['model_source']=str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large');return original(self,*args,**kwargs)
 module.G2PWPinyin.__init__=local_g2pw;module.CACHE_PATH=str(T/'cache/polyphonic.pickle');module.MD5_PATH=str(T/'cache/polyphonic.md5')
 fast=importlib.import_module('fast_langdetect.infer')
 def local_fasttext(self,path):
  path=Path(path).resolve();previous=Path.cwd();assert path.name.isascii()
  try:os.chdir(path.parent);return fast.fasttext.load_model(path.name)
  finally:os.chdir(previous)
 fast.ModelLoader._load_windows_compatible=local_fasttext
 sv_module=importlib.import_module('sv');sv_module.sv_path=str(M/'sv/pretrained_eres2netv2w24s4ep4.ckpt')
 return torch
def verify_protected():
 for p,h in read(T/'protected-hashes.json').items():assert sha(p)==h,'Protected source/model changed: '+p
