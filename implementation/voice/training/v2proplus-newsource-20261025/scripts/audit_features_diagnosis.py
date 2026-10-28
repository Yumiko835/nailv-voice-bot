
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
import numpy as np,soundfile as sf,contextlib
from scipy.signal import resample_poly
O=T/'inference-diagnosis-20261025';torch=runtime()
from feature_extractor import cnhubert
from module.models import SynthesizerTrn
from process_ckpt import load_sovits_new
cnhubert.cnhubert_base_path=str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base')
hubert=cnhubert.get_model().cuda().half().eval().requires_grad_(False)
h=read(G/'GPT_SoVITS/configs/s2v2ProPlus.json');net=SynthesizerTrn(h['data']['filter_length']//2+1,h['train']['segment_size']//h['data']['hop_length'],n_speakers=h['data']['n_speakers'],**(h['model']|{'version':'v2ProPlus'}));state=load_sovits_new(str(M/'v2Pro/s2Gv2ProPlus.pth'));net.load_state_dict(state['weight'],strict=False);del state;net=net.cuda().half().eval().requires_grad_(False)
ds=read(T/'dataset/manifest.json');results=[]
for row in ds['holdout'][:3]+ds['train'][:1]:
 y,sr=sf.read(F/'5-wav32k'/(row['id']+'.wav'),dtype='float32');assert sr==32000;x=resample_poly(y,1,2).astype('float32');features=[];codes=[]
 for scale in [1.,1145.14]:
  with torch.inference_mode():z=hubert.model(torch.from_numpy(x*scale).unsqueeze(0).cuda().half())['last_hidden_state'].transpose(1,2);c=net.extract_latent(z)[0,0].cpu();features.append(z.float().cpu());codes.append(c)
 cached=torch.load(F/'4-cnhubert'/(row['id']+'.wav.pt'),map_location='cpu',weights_only=True).float();assert cached.shape==features[1].shape
 results.append({'id':row['id'],'feature_dtype':str(z.dtype),'unit_vs_training_scale_feature_cosine':float(torch.nn.functional.cosine_similarity(features[0],features[1],dim=1).mean()),'unit_vs_training_scale_token_match':float((codes[0]==codes[1]).float().mean()),'cached_feature_max_error':float((cached-features[1]).abs().max()),'finite':bool(torch.isfinite(cached).all())})
write(O/'feature-scale-audit.json',results);print(json.dumps(results,ensure_ascii=True))
