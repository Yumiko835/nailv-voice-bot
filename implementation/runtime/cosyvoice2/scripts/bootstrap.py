
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
import os,sys,json,venv,subprocess,urllib.request,hashlib,time
ROOT=Path(project_path(''))
R=ROOT/'runtime/cosyvoice2';O=ROOT/'voice/comparison/cosyvoice2-20261026'
for p in [R/'cache',R/'models',R/'scripts',O/'logs',O/'prompts',O/'generated']:p.mkdir(parents=True,exist_ok=True)
for key,folder in {'HF_HOME':'hf','HUGGINGFACE_HUB_CACHE':'hf/hub','HF_HUB_CACHE':'hf/hub','TORCH_HOME':'torch','NUMBA_CACHE_DIR':'numba','MPLCONFIGDIR':'matplotlib','MODELSCOPE_CACHE':'modelscope','UV_CACHE_DIR':'uv','PIP_CACHE_DIR':'pip','TEMP':'tmp','TMP':'tmp'}.items():
    p=R/'cache'/folder;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',HF_HUB_DISABLE_XET='1')
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
write(O/'setup-status.json',{'stage':'creating-environment','updated':time.time()})
if not (R/'.venv/Scripts/python.exe').exists():venv.EnvBuilder(with_pip=False).create(R/'.venv')
site=R/'.venv/Lib/site-packages';site.mkdir(parents=True,exist_ok=True)
# Read-only reuse of existing matching CUDA Torch/Torchaudio binaries. New or
# version-specific dependencies install only into this new environment first.
(site/'shared-torch-runtime.pth').write_text(dependency_path("gpt_sovits",'.venv/Lib/site-packages\n'),encoding='utf-8')
url='https://huggingface.co/api/models/FunAudioLLM/CosyVoice2-0.5B/revision/main?blobs=true'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CosyVoice2-local-setup'}),timeout=60) as f:info=json.load(f)
write(R/'model-metadata.json',info)
files=[r for r in info['siblings'] if r['rfilename'] in ['llm.pt','flow.pt','hift.pt','campplus.onnx','speech_tokenizer_v2.onnx','spk2info.pt','cosyvoice2.yaml','README.md','LICENSE'] or r['rfilename'].startswith('CosyVoice-BlankEN/')]
write(R/'required-model-files.json',{'repository':'FunAudioLLM/CosyVoice2-0.5B','revision':info['sha'],'files':files})
print(json.dumps({'revision':info['sha'],'files':[{'name':r['rfilename'],'bytes':r.get('size',r.get('lfs',{}).get('size'))} for r in files]},ensure_ascii=False),flush=True)
uv=Path(dependency_path("optional_source",'uv.exe'))
requirements=['diffusers==0.29.0','HyperPyYAML==1.2.3','omegaconf==2.3.0','hydra-core==1.3.2','lightning==2.2.4','modelscope==1.20.0','conformer==0.3.2','openai-whisper==20231117','x-transformers==2.11.24','inflect==7.3.1','gdown==5.1.0','wget==3.2']
write(R/'dependency-request.json',{'packages':requirements,'torch_runtime_reused_read_only':str(Path(dependency_path("gpt_sovits",'.venv/Lib/site-packages'))),'optional_acceleration_packages_installed':False})
command=[str(uv),'pip','install','--python',str(R/'.venv/Scripts/python.exe'),'--index-url','https://pypi.org/simple','setuptools==75.8.0','wheel']
write(O/'setup-status.json',{'stage':'installing-inference-dependencies','updated':time.time()})
subprocess.run(command,check=True)
subprocess.run([str(R/'.venv/Scripts/python.exe'),'-B','-X','utf8',str(Path(__file__).with_name('install_deps.py'))],check=True)
write(O/'setup-status.json',{'stage':'dependencies-ready','updated':time.time()})
print('Isolated inference dependencies ready.',flush=True)
