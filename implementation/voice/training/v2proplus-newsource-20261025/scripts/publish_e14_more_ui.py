
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
import shutil, re

D = Path(__file__).parent
ROOT = Path(project_path(''))
T = ROOT / 'voice/training/v2proplus-newsource-20261025'
O = T / 'e14-more-sentences-20261025'
p = D / 'voice-proplus.html'
html = p.read_text(encoding='utf-8-sig')
assert 'id="e14-more"' not in html
html = html.replace('SoVITS音色已续训至20轮，每2轮保留权重。', 'SoVITS音色已比较至20轮，按你的试听选择采用原第14轮，不加插值或均衡。')
start = html.index('<article><h2 id="diagnosis">')
end = html.index('<section id="e20">', start)
html = html[:start] + '''<section id="e14-more"><h2>原第14轮 · 更多句子试听</h2><p>全部使用原SoVITS第14轮＋本次ProPlus GPT第6轮，不混合权重、不加均衡。沿用已确认的十种参考语气。以下是为试听编写的句子，不是主播原话。</p><p id="e14-more-status">正在准备新试听…</p><label for="e14-more-group">选择想听的一类</label><select id="e14-more-group"><option value="all">全部试听</option><option>日常闲聊</option><option>重复词与连读</option><option>咬字与句尾</option><option>稍长的聊天</option><option>十种语气</option></select><div id="e14-more-samples" class="grid"></div><p class="small">每条有独立编号。可以记录哪些句子自然、哪里仍有电音、拖音或漏字；自动检查不能判断听感。</p></section><details><summary>历史试听 · 20轮续训与提亮对照（已选择原14轮）</summary>''' + html[end:]
marker = '</section><details><summary>历史试听 · 第14轮及更早的对照</summary>'
assert html.count(marker) == 1
html = html.replace(marker, '</section></details><details><summary>历史试听 · 第14轮及更早的对照</summary>')
html = html.replace("lastE20='',e20Rows=[],busy=false", "lastE20='',lastExpandedE14='',expandedE14Rows=[],e20Rows=[],busy=false")
assert 'let lastManifest=' in html and 'expandedE14Rows=[]' in html
function = '''function renderExpandedE14(){const group=$('e14-more-group').value||'all';$('e14-more-samples').replaceChildren();for(const p of expandedE14Rows){if(group!=='all'&&p.group!==group)continue;const card=el('article');card.append(el('h3',p.audition_label),el('p',p.text),el('p',p.label+' · '+p.seconds.toFixed(1)+'秒'));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src='/voice-proplus-media/'+p.media;card.append(audio);$('e14-more-samples').append(card);}}$('e14-more-group').onchange=renderExpandedE14;
'''
html = html.replace('function renderE20()', function + 'function renderE20()', 1)
insert = '''if(s.expanded_e14_sha256&&s.expanded_e14_sha256!==lastExpandedE14){lastExpandedE14=s.expanded_e14_sha256;expandedE14Rows=s.expanded_e14_samples||[];$('e14-more-status').textContent='共'+expandedE14Rows.length+'句新生成试听 · 原生32kHz无损WAV。编号A至E分别覆盖五类句子。';renderExpandedE14();}'''
html = html.replace('if(s.e20_sha256&&', insert + 'if(s.e20_sha256&&', 1)
html = html.replace("'提亮方法目前以第'+s.e20_method_base_epoch+'轮作为候选基准，尚未判定为最好或设为默认。可以切换三句比较。'", "'本组为旧对照，提亮基准为第'+s.e20_method_base_epoch+'轮；你已选择原第14轮，以下候选均未采用。'")
assert '以下候选均未采用' in html
html = html.replace("let info=labels[s.progress.stage]||'正在处理V2 ProPlus';", "let info=s.progress.activity==='generating-original-e14-more-sentences'?'正在用原第14轮生成更多试听':labels[s.progress.stage]||'正在处理V2 ProPlus';")
p.write_text(html, encoding='utf-8')
backup = O / 'ui-backup'
backup.mkdir(parents=True, exist_ok=True)
for source, target in [(p,ROOT/'outputs/奶绿V2ProPlus双阶段语音.html'), (D/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py')]:
    saved = backup / target.name
    assert not saved.exists(), 'Do not replace rollback backup'
    shutil.copy2(target, saved)
    shutil.copy2(source, target)
    shutil.copy2(source, T/'scripts'/source.name)
print('Published original e14 listening UI and media allowlist; restart own server to load backend.')
