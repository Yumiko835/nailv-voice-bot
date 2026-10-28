"""Same acoustic checkpoint and reference; isolate Stage1 and front-end."""

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
import contextlib,types,gc,inspect,itertools
import numpy as np,soundfile as sf,yaml
from nailv_audio_export import prepare_reference,float_audio_postprocess,export_native
O=T/'inference-diagnosis-20261025';torch=runtime()
from nailv_connected_frontend import install
install()
import GPT_SoVITS.TTS_infer_pack.TTS as engine
from low_peak_loading import install as low_peak
low_peak(engine);engine.now_dir=str(M.parent.parent)
sel=read(T/'selected-models.json');bank=read(T/'prompts/manifest.json');cfg=O/'gpt-config.yaml';cfg.write_text(yaml.safe_dump({'custom':{'version':'v2ProPlus','device':'cuda','is_half':True,'t2s_weights_path':sel['gpt']['path'],'vits_weights_path':sel['sovits']['path'],'cnhuhbert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-hubert-base'),'bert_base_path':str(G/'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large')}},allow_unicode=True),encoding='utf-8')
with (O/'gpt-load.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):tts=engine.TTS(engine.TTS_Config(str(cfg)))
tts.audio_postprocess=types.MethodType(float_audio_postprocess,tts);original=tts.vits_model.decode;captures=[]
def capture(codes,*args,**kwargs):
 captures.append(codes.detach().cpu().flatten().tolist());return original(codes,*args,**kwargs)
tts.vits_model.decode=capture;rows=[]
def run(name,text,style,rp=1.35,seed=42):
 out=O/'gpt-matrix'/name;out.mkdir(parents=True,exist_ok=True);prompt=bank['prompts'][style];prepare_reference(prompt['path'],out/'reference.wav',gate_plan=prompt['micro_gate_plan']);tts.prompt_cache['ref_audio_path']=None;tts.prompt_cache['prompt_text']=None;captures.clear();settings={'text':text,'text_lang':'zh','prompt_text':prompt['text'],'prompt_lang':'zh','ref_audio_path':str(out/'reference.wav'),'top_k':5,'top_p':.9,'temperature':.85,'repetition_penalty':rp,'seed':seed,'speed_factor':1.,'text_split_method':'cut0','parallel_infer':False,'batch_size':1,'split_bucket':False,'streaming_mode':False,'return_fragment':False,'fragment_interval':0.,'use_cuda_graph':False,'use_flash_attention':False,'super_sampling':False}
 with (out/'inference.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):parts=list(tts.run(settings))
 y=np.concatenate([x for _,x in parts]);runs=[len(list(g)) for k,g in itertools.groupby(captures[0])];row={'id':name,'text':text,'style':style,'label':prompt['label'],'reference_id':prompt['id'],'settings':settings,'gpt_path':tts.configs.t2s_weights_path,'max_identical_run':max(runs),'semantic_tokens':len(captures[0]),'no_tempo_adjustment':True,**export_native(y,out)};rows.append(row);write(O/'gpt-matrix.json',{'samples':rows});print(json.dumps({'id':name,'seconds':row['seconds'],'max_repeat':max(runs)},ensure_ascii=True),flush=True)
# Text-preprocessing adds a leading full stop for short initial interjections.
# Evaluate removal separately, without changing source texts or saved models.
pre=tts.text_preprocessor if hasattr(tts,'text_preprocessor') else tts.text_preprocessor
orig=pre.pre_seg_text;source=__import__('textwrap').dedent(inspect.getsource(orig));assert 'text = "。" + text if lang != "en" else "." + text' in source
source=source.replace('text = "。" + text if lang != "en" else "." + text','pass  # diagnostic: do not prepend an artificial full stop')
namespace={};exec(compile(source,'<diagnostic-front-end>','exec'),orig.__func__.__globals__,namespace);pre.pre_seg_text=types.MethodType(namespace['pre_seg_text'],pre)
run('e6-gentle-no-added-period','嗯，别着急，我先听你把话说完。','gentle')
pre.pre_seg_text=orig
# Include more repeated words and a sentence with several pauses.
for name,text,style in [('e6-papa','爸爸爸爸，别闹啦，我听到了。','daily'),('e6-redup','好好好，我知道啦，慢慢说。','daily'),('e6-thinking','嗯，那个，等一下，我想想啊。','daily'),('e6-long','我刚才只是开个玩笑，你别急嘛，先坐下来，慢慢把事情说清楚。','daily')]:run(name,text,style)
with (O/'gpt-load.log').open('a',encoding='utf-8') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):tts.init_t2s_weights(str(M/'s1v3.ckpt'))
for name,text,style in [('official-mama','妈妈妈妈，这么喜欢叫妈妈吗','daily'),('official-gentle','嗯，别着急，我先听你把话说完。','gentle')]:run(name,text,style)
verify_protected();write(O/'gpt-diagnosis-complete.json',{'cases':len(rows),'models_unchanged':True,'human_quality_verified':False})
