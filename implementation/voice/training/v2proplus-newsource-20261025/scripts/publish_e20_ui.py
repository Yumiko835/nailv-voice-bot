
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
import ast,shutil
C=T/'continuation-e14to20-20261025';here=Path(__file__).parent;backup=C/'before-ui';backup.mkdir(exist_ok=True)
for old in [ROOT/'tools/nailv_proplus_voice.py',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html']:
 if not (backup/old.name).exists():shutil.copy2(old,backup/old.name)
p=here/'voice-proplus.html';s=p.read_text(encoding='utf-8')
if 'id="e20"' not in s:
 marker='<section id="clarity">';assert marker in s
 section='''<section id="e20"><h2>20轮续训与提亮对照 · GPT固定第6轮</h2><p>先比较纯模型第14、16、18、20轮的电音与咬字，再比较插值和高频均衡。模型轮数增加或高频变亮，都不能单独代表音质更好。</p><label for="e20-case">选择同一句来比较</label><select id="e20-case"><option value="mama">重复词：妈妈妈妈，这么喜欢叫妈妈吗</option><option value="calm">正常接话：嗯，别着急，我先听你把话说完</option><option value="clear">清晰度：先说清楚，这件事情是不是你说的呀</option></select><p id="e20-base-note">训练完成后显示对照。当前默认仍为GPT第6轮＋音色第14轮。</p><h3>① 纯模型轮次</h3><div id="e20-epochs" class="grid"></div><h3>② 权重插值</h3><div id="e20-merges" class="grid"></div><h3>③ 高频均衡</h3><p class="small">6kHz起的高频均衡分别试2dB、3dB；也可能让残余电音、底噪或齿音更明显，请一起比较。</p><div id="e20-eq" class="grid"></div><h3>④ 插值＋2dB高频均衡</h3><div id="e20-combined" class="grid"></div><p class="small">同一句沿用同一份GPT语音编码、参考特征和解码种子777，试听音量对齐；无移调、加速或重采样。额外候选均单独保存，尚未改成默认。</p></section>'''
 s=s.replace(marker,section+'<details><summary>历史试听 · 第14轮及更早的对照</summary>'+marker);s=s.replace('<script>','</details><script>',1)
 s=s.replace("lastClarity='',busy=false","lastClarity='',lastE20='',e20Rows=[],busy=false")
 marker='const labels={';assert marker in s
 render="function renderE20(){const ids={epoch:'e20-epochs',merge:'e20-merges',eq:'e20-eq',combined:'e20-combined'};for(const id of Object.values(ids))$(id).replaceChildren();const selected=$('e20-case').value||'mama';for(const p of e20Rows){if(p.case!==selected)continue;const card=el('article');card.append(el('h3',p.label),el('p',p.text));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src='/voice-proplus-media/'+p.media;card.append(audio);$(ids[p.group]).append(card);}}$('e20-case').onchange=renderE20;\n"
 s=s.replace(marker,render+marker)
 marker="if(s.clarity_sha256&&s.clarity_sha256!==lastClarity)";assert marker in s
 extra="if(s.e20_sha256&&s.e20_sha256!==lastE20){lastE20=s.e20_sha256;e20Rows=s.e20_samples||[];$('e20-base-note').textContent='提亮方法目前以第'+s.e20_method_base_epoch+'轮作为候选基准，尚未判定为最好或设为默认。可以切换三句比较。';renderE20();}"
 s=s.replace(marker,extra+marker);s=s.replace("$('generate-button').textContent=s.gpu_training?'音色续训中，完成后恢复生成'", "$('generate-button').textContent=s.gpu_training?'正在处理音色，完成后恢复生成'")
 p.write_text(s,encoding='utf-8')
ast.parse((here/'nailv_proplus_voice.py').read_text(encoding='utf-8'));shutil.copy2(here/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py');shutil.copy2(p,ROOT/'outputs/奶绿V2ProPlus双阶段语音.html')
for name in ['nailv_proplus_voice.py','voice-proplus.html','publish_e20_ui.py','prepare_e20_continuation.py']:
 shutil.copy2(here/name,T/'scripts'/name);shutil.copy2(here/name,C/'scripts'/name)
print('e20 experiment page prepared; earlier audition sections archived, default remains GPT6+acoustic14.')
