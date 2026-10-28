
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
import json,hashlib,shutil,subprocess,time
ROOT=Path(project_path(''));R=ROOT/'runtime/cosyvoice2';O=ROOT/'voice/comparison/cosyvoice2-20261026';T=ROOT/'voice/training/v2proplus-newsource-20261025'
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (O/'requests.json').exists()
bank=json.loads((T/'prompts/manifest.json').read_text(encoding='utf-8'));prompts={}
for style,prompt in bank['prompts'].items():
    assert sha(prompt['path'])==prompt['sha256']
    dest=O/'prompts'/(style+'.wav');shutil.copy2(prompt['path'],dest)
    prompts[style]={'style':style,'label':prompt['label'],'path':str(dest),'original_path':prompt['path'],'sha256':sha(dest),'text':prompt['text'],'reference_id':prompt['id'],
        'transcript':'Existing accepted reference transcript reused unchanged; no new claim of word-perfect manual verification.',
        'no_new_cleaning':True,'resampling':'Official frontend independently reads16k speech tokens/speaker embedding and24k acoustic features from this full-band copy.'}
assert len(prompts)==10
write(O/'prompts/manifest.json',{'prompts':prompts,'source_manifest_sha256':sha(T/'prompts/manifest.json'),'source_manifest_path':str(T/'prompts/manifest.json')})
requests=[]
for style in ['daily','gentle','teasing']:
    requests.append({'id':'devil-'+style,'label':'魔鬼句 · '+prompts[style]['label'],'style':style,'mode':'zero_shot','text':'慢慢来，妈妈妈妈','seed':20261026})
requests.extend([
 {'id':'long-daily','label':'日常长句 · 啊／呢','style':'daily','mode':'zero_shot','text':'今天先把手里的事情放一放，别一直皱着眉头啊。喝口水，我们慢慢聊，你刚刚说到哪儿了呢？','seed':20261026},
 {'id':'long-gentle','label':'温柔长句 · 吧／呢／啊','style':'gentle','mode':'zero_shot','text':'累了就靠着休息一会儿吧，不用急着把所有事情都做完呢。等你缓过来了，我们再一起想办法，好不好啊？','seed':20261026},
 {'id':'long-teasing','label':'调侃长句 · 啊／吧','style':'teasing','mode':'zero_shot','text':'你刚刚还说自己一点都不困，现在眼睛都快睁不开了啊。行啦，把手机放下，明天醒了再来跟我讲吧。','seed':20261026},
 {'id':'instruct-gentle','label':'instruct2 · 温柔安慰指令','style':'gentle','mode':'instruct2','instruction':'请用温柔、轻松、安慰人的语气说这句话。<|endofprompt|>','text':'今天已经做得很好了，剩下的事情明天再想吧，先好好休息一下，好不好？','seed':20261026},
])
for style in prompts:
    if style in ['daily','gentle','teasing']:continue
    requests.append({'id':'pool-'+style,'label':'参考池 · '+prompts[style]['label'],'style':style,'mode':'zero_shot','text':'今天也没什么特别的事情，就是想坐在这里，跟你聊一会儿，你慢慢说吧。','seed':20261026})
write(O/'requests.json',{'samples':requests,'reuse_all10_references':True,'no_training':True})
write(O/'gpt-sovits-status-before.json',json.loads((T/'status.json').read_text(encoding='utf-8')))
write(T/'status.json',{'stage':'proplus-comparing-continuation','activity':'cosyvoice2-comparison','project':'v2proplus-newsource-20261025','updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')})
commit=subprocess.check_output(['git','-C',str(R/'src'),'rev-parse','HEAD'],text=True).strip()
write(O/'source-code.json',{'repository':'https://github.com/FunAudioLLM/CosyVoice','commit':commit,'jit':False,'trt':False,'vllm':False,'fp16':True})
print(json.dumps({'active_prompts':len(prompts),'samples':len(requests),'commit':commit},ensure_ascii=False))
