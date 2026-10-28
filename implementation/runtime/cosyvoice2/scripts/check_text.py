
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
import os,sys,json,re,contextlib,subprocess,hashlib
ROOT=Path(project_path(''));R=ROOT/'runtime/cosyvoice2';O=ROOT/'voice/comparison/cosyvoice2-20261026'
for k,v in {'HF_HOME':'hf','TORCH_HOME':'torch','NUMBA_CACHE_DIR':'numba','MPLCONFIGDIR':'matplotlib','TEMP':'tmp','TMP':'tmp'}.items():os.environ[k]=str(R/'cache'/v)
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
sys.path.insert(0,str(ROOT/'runtime/sensevoice-curation/packages'))
import torch,numpy as np,sentencepiece
from funasr import AutoModel
for name in ['LoadFromFile','load_from_file','Load','load']:setattr(sentencepiece.SentencePieceProcessor,name,lambda self,path:self.LoadFromSerializedProto(Path(path).read_bytes()))
sys.path.append(str(ROOT/'voice/training/v5dev-newsource-20261025/scripts'))
from golden_text_comparison import phon,distance
assert torch.cuda.is_available();torch.set_num_threads(2)
with (O/'logs/asr.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    model=AutoModel(model=str(ROOT/'runtime/models/sensevoice-small'),device='cuda:0',ncpu=2,disable_update=True,disable_pbar=True,trust_remote_code=False,fp16=True)
model.model.encoder.register_forward_pre_hook(lambda module,inputs:tuple(x.half() if isinstance(x,torch.Tensor) and x.is_floating_point() else x for x in inputs))
data=json.loads((O/'generated/manifest.json').read_text(encoding='utf-8'));checks=[]
ff=Path(dependency_path("ffmpeg"))
for row in data['samples']:
    x=np.frombuffer(subprocess.check_output([str(ff),'-v','error','-nostdin','-i',row['raw'],'-ac','1','-ar','16000','-f','f32le','pipe:1'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)),dtype='<f4').copy()
    with torch.autocast('cuda',dtype=torch.float16),(O/'logs/asr.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):recognized=model.generate(input=x,cache={},language='zh',use_itn=False,batch_size_s=30,disable_pbar=True)[0]['text']
    recognized=re.sub(r'<\|[^|]+\|>','',recognized).strip();expected=phon(row['text']);error=distance(expected,phon(recognized))/max(1,len(expected))
    checks.append({'id':row['id'],'expected':row['text'],'recognized':recognized,'phonetic_error':error,'no_repeated_words_deduplicated':True,'human_quality_verified':False})
    print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
(O/'content-check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
