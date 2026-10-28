
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
import contextlib,subprocess,re
torch=runtime();import numpy as np,soundfile as sf
from process_ckpt import load_sovits_new
selected=read(T/'selected-models.json');verify_protected();receipt=read(T/'stage2-training-receipt.json');assert receipt['epochs_completed']==10 and receipt['weights_changed'] and len(receipt['exports'])==5;assert read(T/'training-receipt.json')['epochs_completed']==10
base=load_sovits_new(str(M/'v2Pro/s2Gv2ProPlus.pth'));trained=load_sovits_new(selected['sovits']['path']);frozen=[k for k in base['weight'] if k.startswith(('ssl_proj.','quantizer.'))];assert frozen and all(torch.equal(base['weight'][k].half(),trained['weight'][k].half()) for k in frozen),'Codec coordinates changed';del base,trained
manifest=read(T/'generated/test/manifest.json');assert len(manifest['samples'])==12
for sample in manifest['samples']:
 for key in ['raw','playback']:
  audio,sr=sf.read(sample[key],dtype='float32');info=sf.info(sample[key]);assert sr==32000 and info.subtype=='PCM_24' and np.isfinite(audio).all() and np.max(np.abs(audio))<1
 assert sha(sample['raw'])==sample['raw_sha256'] and sample['trimmed_samples']==0 and not sample['output_resampling'] and sample['no_output_denoising']
sys.path.insert(0,str(ROOT/'runtime/sensevoice-curation/packages'));from funasr import AutoModel
import sentencepiece
for name in ['LoadFromFile','load_from_file','Load','load']:setattr(sentencepiece.SentencePieceProcessor,name,lambda self,path:self.LoadFromSerializedProto(Path(path).read_bytes()))
with (T/'generated/test/asr-check.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):model=AutoModel(model=str(ROOT/'runtime/models/sensevoice-small'),device='cuda:0',ncpu=2,disable_update=True,disable_pbar=True,trust_remote_code=False,fp16=True)
model.model.encoder.register_forward_pre_hook(lambda module,inputs:tuple(x.half() if isinstance(x,torch.Tensor) and x.is_floating_point() else x for x in inputs))
sys.path.append(str(A/'scripts'));from golden_text_comparison import phon,distance
checks=[]
for r in manifest['samples']:
 x=np.frombuffer(subprocess.check_output([str(FF),'-v','error','-nostdin','-i',r['raw'],'-ac','1','-ar','16000','-f','f32le','pipe:1'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)),dtype='<f4').copy()
 with torch.autocast('cuda',dtype=torch.float16),(T/'generated/test/asr-check.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):raw=model.generate(input=x,cache={},language='zh',use_itn=False,batch_size_s=30,disable_pbar=True)[0]['text']
 text=re.sub(r'<\|[^|]+\|>','',raw).strip();expected=phon(r['text']);error=distance(expected,phon(text))/max(len(expected),1);checks.append({'id':r['id'],'expected':r['text'],'recognized':text,'full_phoneme_error_retaining_repeats':error,'possible_content_mismatch':error>.25,'audio_sha256':r['raw_sha256'],'human_sound_quality_verified':False})
write(T/'generated/test/technical-verification.json',{'native32k_pcm24':True,'no_lossy_encoding_or_output_resampling':True,'source_dataset_hash_unchanged':True,'frozen_semantic_codec_parameters':len(frozen),'checks':checks,'ASR_is_not_a_noise_or_similarity_approval':True,'human_sound_quality_verified':False});print(json.dumps(checks,ensure_ascii=False))
import runpy
runpy.run_path(str(Path(__file__).parent/'write_delivery_notes.py'),run_name='__main__')
