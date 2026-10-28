"""All existing GPT exports, fixed trained acoustic e10. No training."""

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
import contextlib,types,itertools
import numpy as np,yaml
from nailv_audio_export import prepare_reference,float_audio_postprocess,export_native
O=T/'inference-diagnosis-20261025';torch=runtime()
from nailv_connected_frontend import install
install()
import GPT_SoVITS.TTS_infer_pack.TTS as engine
from low_peak_loading import install as low_peak
low_peak(engine);engine.now_dir=str(M.parent.parent)
sel=read(T/'selected-models.json');bank=read(T/'prompts/manifest.json');cfg=O/'epoch-config.yaml';cfg.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':sel['gpt']['path'],'vits_weights_path':sel['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (O/'epoch-load.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):tts=engine.TTS(engine.TTS_Config(str(cfg)))
tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts);decode=tts.vits_model.decode;codes=[]
def fixed_decoder(semantic,*args,**kwargs):
 codes.append(semantic.detach().cpu().flatten().tolist());torch.manual_seed(777);torch.cuda.manual_seed_all(777);return decode(semantic,*args,**kwargs)
tts.vits_model.decode=fixed_decoder;rows=[]
for epoch in [2,4,6,8,10]:
 path=T/f'checkpoints/gpt/milkgreen-proplus-stage1-e{epoch}.ckpt'
 with (O/'epoch-load.log').open('a',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):tts.init_t2s_weights(str(path))
 for name,text,style in [('mama','妈妈妈妈，这么喜欢叫妈妈吗','daily'),('calm','嗯，别着急，我先听你把话说完。','gentle')]:
  out=O/'gpt-epochs'/f'gpt{epoch}-{name}';out.mkdir(parents=True,exist_ok=True);prompt=bank['prompts'][style];prepare_reference(prompt['path'],out/'reference.wav',gate_plan=prompt['micro_gate_plan']);tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None;codes.clear();settings={'text':text,'text_lang':'zh','prompt_text':prompt['text'],'prompt_lang':'zh','ref_audio_path':str(out/'reference.wav'),'top_k':5,'top_p':.9,'temperature':.85,'repetition_penalty':1.35,'seed':42,'speed_factor':1.,'text_split_method':'cut0','parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'super_sampling':False}
  with (out/'inference.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):parts=list(tts.run(settings))
  y=np.concatenate([x for _,x in parts]);runs=[len(list(g)) for _,g in itertools.groupby(codes[0])];item={'id':f'gpt{epoch}-{name}','label':f'GPT第{epoch}轮 · '+('重复词' if name=='mama' else '正常接话'),'gpt_epoch':epoch,'sovits_epoch':10,'text':text,'reference_id':prompt['id'],'settings':settings,'decoder_seed':777,'gpt_sha256':sha(path),'sovits_sha256':sel['sovits']['sha256'],'semantic_tokens':len(codes[0]),'max_identical_run':max(runs),'no_tempo_or_spectral_processing':True,**export_native(y,out)};rows.append(item);write(O/'gpt-epochs.json',{'samples':rows,'human_quality_verified':False,'default_not_automatically_changed':True});print(json.dumps({'id':item['id'],'seconds':item['seconds'],'max_repeat':max(runs)},ensure_ascii=True),flush=True)
verify_protected()
