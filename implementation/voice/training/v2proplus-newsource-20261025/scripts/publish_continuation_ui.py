
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
import shutil,ast
C=T/'continuation-e10to14-20261025';here=Path(__file__).parent;p=here/'voice-proplus.html';s=p.read_text(encoding='utf-8')
if 'id="continuation"' not in s:
 old='GPT第6轮只是新模型的自动验证初选，听感尚待核对。';assert old in s;s=s.replace(old,'GPT已按你的选择固定为本次ProPlus第6轮。此次只续训SoVITS音色，不再比较或修改GPT。')
 marker='<details open><summary id="gpt-compare">';assert marker in s
 section='<section id="continuation"><h2>音色续训 · 固定GPT第6轮</h2><p>比较SoVITS第10、12、14轮。每句话使用同一份GPT语音编码、参考音频和解码随机种子；试听音量对齐，不加快播放。</p><div id="acoustic-samples" class="grid"></div><h2>另一种尝试 · 降低解码随机噪声量</h2><p>固定第10轮音色，比较原值0.5与0.25、0。此参数改变模型内部随机采样，不是对成品做降噪；减小可能让声音更平，是否有效以试听为准。</p><div id="noise-samples" class="grid"></div></section>'
 s=s.replace(marker,section+'<details><summary id="gpt-compare">')
 s=s.replace('新GPT轮次对照 · 音色固定第10轮','历史GPT轮次对照 · 已选第6轮')
 s=s.replace("lastComparison='',busy=false","lastComparison='',lastContinuation='',busy=false")
 s=s.replace("$('generate-button').disabled=!s.ready||busy;", "$('generate-button').disabled=!s.ready||busy||s.generation_available===false;")
 s=s.replace("$('generate-button').textContent=s.ready?'生成语音（本机）':'训练完成后可生成';", "$('generate-button').textContent=s.gpu_training?'音色续训中，完成后恢复生成':s.ready?'生成语音（本机）':'训练完成后可生成';")
 marker="if(s.comparison_sha256&&s.comparison_sha256!==lastComparison)";assert marker in s
 extra="if(s.continuation_sha256&&s.continuation_sha256!==lastContinuation){lastContinuation=s.continuation_sha256;$('acoustic-samples').replaceChildren();$('noise-samples').replaceChildren();for(const p of s.continuation_samples||[]){const card=el('article');card.append(el('h3',p.label),el('p',p.text));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src='/voice-proplus-media/'+p.media;card.append(audio);$(p.group==='noise'?'noise-samples':'acoustic-samples').append(card);}}"
 s=s.replace(marker,extra+marker);p.write_text(s,encoding='utf-8')
backup=C/'before-ui';backup.mkdir(exist_ok=True)
for old in [ROOT/'tools/nailv_proplus_voice.py',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html']:
 if not (backup/old.name).exists():shutil.copy2(old,backup/old.name)
ast.parse((here/'nailv_proplus_voice.py').read_text(encoding='utf-8'))
shutil.copy2(here/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py');shutil.copy2(p,ROOT/'outputs/奶绿V2ProPlus双阶段语音.html')
for name in ['nailv_proplus_voice.py','voice-proplus.html','prepare_continuation.py','compare_continuation.py','publish_continuation_ui.py']:
 shutil.copy2(here/name,T/'scripts'/name)
shutil.copy2(here/'compare_continuation.py',C/'scripts/compare_continuation.py')
print('Continuation comparison UI published; e6 user lock recorded, GPU training blocks new synthesis jobs only.')
