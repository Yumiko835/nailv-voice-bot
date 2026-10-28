
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
import argparse,math,contextlib,collections
p=argparse.ArgumentParser();p.add_argument('stage',choices=['text','hubert','speaker','semantic','check']);a=p.parse_args();ds=read(T/'dataset/manifest.json');rows=ds['train']+ds['validation']+ds['holdout'];fingerprint=sha(T/'dataset/manifest.json');existing=read(F/'input-fingerprint.json') if (F/'input-fingerprint.json').exists() else None;assert existing is None or existing['dataset_sha256']==fingerprint
write(F/'input-fingerprint.json',{'dataset_sha256':fingerprint,'version':'v2ProPlus','recomputed_from_original_audio_and_text':True})
torch=runtime();import numpy as np,soundfile as sf
from scipy.signal import resample_poly
if a.stage=='text':
 from transformers import AutoModelForMaskedLM,AutoTokenizer
 from TTS_infer_pack.TextPreprocessor import TextPreprocessor
 from text.symbols2 import symbols
 from text import cleaned_text_to_sequence
 path=G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large';tokenizer=AutoTokenizer.from_pretrained(str(path));bert=AutoModelForMaskedLM.from_pretrained(str(path),torch_dtype=torch.float16).cuda().eval().requires_grad_(False);pre=TextPreprocessor(bert,tokenizer,'cuda');lines=[];audit=[]
 sys.path.insert(0,str(T/'scripts'));from nailv_connected_frontend import install
 install()
 for i,c in enumerate(rows,1):
  ids,features,norm=pre.get_phones_and_bert(c['text'],'zh','v2ProPlus');phones=[symbols[j] for j in ids];assert cleaned_text_to_sequence(phones,'v2ProPlus')==ids
  for char in '啊呀呢吧吗嘛哦唔嗯哎呗啦':assert norm.count('恩' if char=='嗯' else char)>=c['text'].count(char)
  dest=F/'3-bert'/(c['id']+'.wav.pt');features=features.detach().half().cpu();assert torch.isfinite(features).all() and features.shape[-1]==len(phones);save_tensor(features,dest);lines.append(c['id']+'.wav\t'+' '.join(phones)+'\t[]\t'+norm);audit.append({'id':c['id'],'original':c['text'],'frontend_text':norm,'original_label_preserved':True,'bert_sha256':sha(dest)})
  if i%30==0:status('proplus-features-text',completed=i,total=len(rows))
 (F/'2-name2text-all.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8');write(F/'text-audit.json',audit)
elif a.stage=='hubert':
 from feature_extractor import cnhubert
 cnhubert.cnhubert_base_path=str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base');model=cnhubert.get_model().to(device='cuda',dtype=torch.float16).eval().requires_grad_(False);audit=[]
 for i,c in enumerate(rows,1):
  assert sha(c['path'])==c['sha256'];y,sr=sf.read(c['path'],dtype='float32');d=math.gcd(sr,32000);x=resample_poly(y,32000//d,sr//d).astype(np.float32);peak=float(np.abs(x).max());assert 0<peak<2.2
  # Official preparation normalization, only on the new training derivatives.
  gain=.475/peak+.5;wave=x*gain;assert np.max(np.abs(wave))<1;sf.write(F/'5-wav32k'/(c['id']+'.wav'),wave,32000,subtype='PCM_16');hubert=resample_poly(wave*np.float32(1145.14),1,2).astype(np.float32)
  with torch.inference_mode():features=model.model(torch.from_numpy(hubert.copy()).unsqueeze(0).to(device='cuda',dtype=torch.float16))['last_hidden_state'].transpose(1,2).cpu()
  assert torch.isfinite(features).all();save_tensor(features,F/'4-cnhubert'/(c['id']+'.wav.pt'));audit.append({'id':c['id'],'source_sha256':c['sha256'],'train_waveform_gain':gain,'huBERT_samples':len(hubert),'source_text_modified':False,'denoising':False})
  if i%30==0:status('proplus-features-hubert',completed=i,total=len(rows))
 write(F/'waveform-audit.json',audit)
elif a.stage=='speaker':
 from ERes2NetV2 import ERes2NetV2
 import kaldi as Kaldi
 sv=ERes2NetV2(baseWidth=24,scale=4,expansion=4);sv.load_state_dict(torch.load(M/'sv/pretrained_eres2netv2w24s4ep4.ckpt',map_location='cpu',weights_only=False),strict=True);sv=sv.cuda().half().eval().requires_grad_(False)
 for i,c in enumerate(rows,1):
  y,sr=sf.read(F/'5-wav32k'/(c['id']+'.wav'),dtype='float32');wave=torch.from_numpy(resample_poly(y,1,2).copy()).cuda().half()
  with torch.inference_mode():embedding=sv.forward3(Kaldi.fbank(wave.unsqueeze(0),num_mel_bins=80,sample_frequency=16000,dither=0).unsqueeze(0)).cpu()
  assert embedding.shape==(1,20480) and torch.isfinite(embedding).all();save_tensor(embedding,F/'7-sv_cn'/(c['id']+'.wav.pt'))
  if i%30==0:status('proplus-features-speaker',completed=i,total=len(rows))
elif a.stage=='semantic':
 from process_ckpt import load_sovits_new
 from module.models import SynthesizerTrn
 config=read(G/'GPT_SoVITS/configs/s2v2ProPlus.json');base=load_sovits_new(str(M/'v2Pro/s2Gv2ProPlus.pth'));kwargs=config['model']|{'version':'v2ProPlus'};model=SynthesizerTrn(config['data']['filter_length']//2+1,config['train']['segment_size']//config['data']['hop_length'],n_speakers=config['data']['n_speakers'],**kwargs);match=model.load_state_dict(base['weight'],strict=False);assert not match.unexpected_keys and all(k.startswith('enc_q.') for k in match.missing_keys),match;del base;model=model.to(device='cuda',dtype=torch.float16).eval().requires_grad_(False);lines=['item_name\tsemantic_audio']
 for i,c in enumerate(rows,1):
  with torch.inference_mode():codes=model.extract_latent(torch.load(F/'4-cnhubert'/(c['id']+'.wav.pt'),map_location='cpu',weights_only=True).cuda().half())[0,0].cpu().tolist()
  assert 50<len(codes)<280 and all(0<=n<1024 for n in codes);lines.append(c['id']+'.wav\t'+' '.join(map(str,codes)))
  if i%50==0:status('proplus-features-semantic',completed=i,total=len(rows))
 (F/'6-name2semantic-all.tsv').write_text('\n'.join(lines)+'\n',encoding='utf-8')
else:
 text=(F/'2-name2text-all.txt').read_text(encoding='utf-8').splitlines();semantic=(F/'6-name2semantic-all.tsv').read_text(encoding='utf-8').splitlines();assert len(text)==len(rows) and len(semantic)==len(rows)+1
 for role in ['train','validation','holdout']:
  ids={r['id']+'.wav' for r in ds[role]};tl=[line for line in text if line.split('\t')[0] in ids];sl=[line for line in semantic[1:] if line.split('\t')[0] in ids];assert len(tl)==len(sl)==len(ids);(F/('2-name2text-'+role+'.txt')).write_text('\n'.join(tl)+'\n',encoding='utf-8');(F/('6-name2semantic-'+role+'.tsv')).write_text(semantic[0]+'\n'+'\n'.join(sl)+'\n',encoding='utf-8')
 (F/'2-name2text.txt').write_text((F/'2-name2text-train.txt').read_text(encoding='utf-8'),encoding='utf-8')
 for c in rows:
  assert sha(c['path'])==c['sha256'] and hashlib.sha256(c['text'].encode()).hexdigest()==c['text_sha256']
  for sub in ['3-bert','4-cnhubert','7-sv_cn']:assert torch.isfinite(torch.load(F/sub/(c['id']+'.wav.pt'),map_location='cpu',weights_only=True)).all()
 verify_protected();write(T/'feature-verification.json',{'ready':True,'version':'v2ProPlus','train_count':293,'validation_count':10,'independent_holdout_count':10,'all_features_recomputed':True,'source_dataset_sha256':fingerprint,'source_audio_text_unchanged':True,'no_refiltering_or_ASR':True,'speaker_dimension':20480});status('proplus-features-ready',train_count=293)
