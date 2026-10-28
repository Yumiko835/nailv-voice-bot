
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
import argparse,re,subprocess,contextlib
p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();torch=runtime();import numpy as np,soundfile as sf
sys.path.insert(0,str(ROOT/'runtime/sensevoice-curation/packages'));from funasr import AutoModel
import sentencepiece
for name in ['LoadFromFile','load_from_file','Load','load']:setattr(sentencepiece.SentencePieceProcessor,name,lambda self,path:self.LoadFromSerializedProto(Path(path).read_bytes()))
logfile=a.manifest.parent/'asr.log'
with logfile.open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):model=AutoModel(model=str(ROOT/'runtime/models/sensevoice-small'),device='cuda:0',ncpu=2,disable_update=True,disable_pbar=True,trust_remote_code=False,fp16=True)
model.model.encoder.register_forward_pre_hook(lambda module,inputs:tuple(x.half() if isinstance(x,torch.Tensor) and x.is_floating_point() else x for x in inputs));sys.path.append(str(A/'scripts'));from golden_text_comparison import phon,distance
checks=[]
for row in read(a.manifest)['samples']:
 x=np.frombuffer(subprocess.check_output([str(FF),'-v','error','-nostdin','-i',row['raw'],'-ac','1','-ar','16000','-f','f32le','pipe:1'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)),dtype='<f4').copy()
 with torch.autocast('cuda',dtype=torch.float16),logfile.open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):raw=model.generate(input=x,cache={},language='zh',use_itn=False,batch_size_s=30,disable_pbar=True)[0]['text']
 text=re.sub(r'<\|[^|]+\|>','',raw).strip();expected=phon(row['text']);error=distance(expected,phon(text))/max(1,len(expected));checks.append({'id':row['id'],'expected':row['text'],'recognized':text,'error':error,'seconds':row['seconds'],'raw_sha256':row['raw_sha256'],'human_sound_quality_verified':False})
write(a.manifest.parent/'content-check.json',checks);print(json.dumps(checks,ensure_ascii=False))
