
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
import json
D=Path(__file__).parent
ROOT=Path(project_path(''))
T=ROOT/'voice/training/v2proplus-newsource-20261025';O=T/'e14-tail-repair-20261025'
p=D/'voice-proplus.html';html=p.read_text(encoding='utf-8-sig')
assert 'id="tail-repair"' not in html
section='''<section id="tail-repair"><h2>拖音与换气、尾音电流 · 本轮对照</h2><p>继续使用原SoVITS第14轮＋GPT第6轮。先听“慢慢来”的原版与重新生成版，再比较同一份合成的轻处理和稍强处理；两档均未设为默认。</p><p>新增异常循环检测，遇到过长的同一声音单元会重新生成，不靠加速或剪掉尾字。以下收尾处理只在选中的低能量片段渐变衰减；请同时留意轻声字是否受损、电流是否减少。</p><label for="tail-repair-case">选择同一句对照</label><select id="tail-repair-case"><option value="slow">B03 · 慢慢来（先比较拖音）</option><option value="pause">C03 · 短句停顿（听句尾）</option><option value="breath">E04 · 温柔换气（听气息与尾音）</option></select><div id="tail-repair-samples" class="grid"></div><p class="small">原生32kHz无损WAV，无移调、变速或重采样。处理前后使用同一播放增益；无硬静音，不整段切除高频。数字检查和自动转写不能代替试听。</p></section>'''
html=html.replace('<section id="e14-more">',section+'<details><summary>上一组 · 原第14轮24句试听</summary><section id="e14-more">',1)
marker='</section><details><summary>历史试听 · 20轮续训'
assert html.count(marker)==1
html=html.replace(marker,'</section></details><details><summary>历史试听 · 20轮续训',1)
html=html.replace("lastExpandedE14='',expandedE14Rows=[]", "lastExpandedE14='',lastTailRepair='',tailRepairRows=[],expandedE14Rows=[]",1)
renderer="""function renderTailRepair(){const chosen=$('tail-repair-case').value||'slow';$('tail-repair-samples').replaceChildren();for(const p of tailRepairRows){if(p.case!==chosen)continue;const card=el('article');card.append(el('h3',p.label),el('p',p.text),el('p',p.seconds.toFixed(2)+'秒'));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src='/voice-proplus-media/'+p.media;card.append(audio);$('tail-repair-samples').append(card);}}$('tail-repair-case').onchange=renderTailRepair;
"""
html=html.replace('function renderExpandedE14()',renderer+'function renderExpandedE14()',1)
update="if(s.tail_repair_sha256&&s.tail_repair_sha256!==lastTailRepair){lastTailRepair=s.tail_repair_sha256;tailRepairRows=s.tail_repair_samples||[];renderTailRepair();}"
html=html.replace('if(s.expanded_e14_sha256&&',update+'if(s.expanded_e14_sha256&&',1)
html=html.replace("let info=s.progress.activity==='generating-original-e14-more-sentences'?", "let info=s.progress.activity==='e14-tail-repair'?'正在核对拖音与尾音处理':s.progress.activity==='generating-original-e14-more-sentences'?",1)
p.write_text(html,encoding='utf-8')
data=json.loads((O/'listening-v2.json').read_text(encoding='utf-8'))
filtered=[r for r in data['samples'] if isinstance(r.get('treatment'),dict)]
verify=O/'filtered-content-check';verify.mkdir(exist_ok=True)
(verify/'manifest.json').write_text(json.dumps({'samples':filtered},ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared new listening section and six derivative content checks; deployment remains separate.')
