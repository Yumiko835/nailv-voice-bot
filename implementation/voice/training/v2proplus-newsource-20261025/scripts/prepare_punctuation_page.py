
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
D=Path(__file__).parent;O=T/'punctuation-tail-patch-20261025'
data=read(O/'generated/manifest.json');assert len(data['samples'])==9
rows=[]
for base in data['samples']:
    case=base['id'];title=base['audition_label']
    rows.append(base|base['control']|{'id':case+'-split','case':case,'case_title':title,
        'label':'A · 仅分句与末尾Token处理','acoustic_effects_applied':False})
    rows.append(base|{'id':case+'-full','case':case,'case_title':title,
        'label':'B · 三道补丁（尾音收束＋气音柔化）','acoustic_effects_applied':True})
write(O/'listening.json',{'samples':rows,'models':data['models'],'human_quality_verified':False,
    'comparison':'Identical segmented synthesis and gain; B adds clause-local effects before stitching.'})
write(O/'verification/manifest.json',{'samples':rows})
p=D/'voice-proplus.html';html=p.read_text(encoding='utf-8-sig');assert 'id="punctuation-patches"' not in html
section='''<section id="punctuation-patches"><h2>第14轮 · 分句、尾音与气音三道补丁</h2><p>本轮按逗号等标点逐段独立生成，中间插入0.25秒纯静音；采样默认使用top_k 15、温度0.8、重复惩罚1.35。GPT仍是第6轮，音色仍是原第14轮，没有重新训练。</p><p>A是仅做分句和末尾异常Token处理的版本；B在同一份声音上加入100毫秒尾音淡出、尾部动态低通和气音柔化。两者播放增益一致。请重点比较电流、停顿，以及轻声和句尾有没有被削掉。</p><label for="punctuation-case">选择日常台词</label><select id="punctuation-case"></select><div id="punctuation-samples" class="grid"></div><p class="small">全部为原生32kHz无损WAV。能量检测不能准确识别每个字，短句切分也可能改变自然节奏；是否改善以实际试听为准。下方旧样本保留。</p></section>'''
html=html.replace('<section id="tail-repair">',section+'<details><summary>上一版 · 拖音与温和收尾处理（未获采用）</summary><section id="tail-repair">',1)
marker='</section><details><summary>上一组 · 原第14轮24句试听</summary>'
assert html.count(marker)==1
html=html.replace(marker,'</section></details><details><summary>上一组 · 原第14轮24句试听</summary>',1)
html=html.replace('min="0.85" max="0.95" step="0.01" value="0.85"','min="0.75" max="0.95" step="0.01" value="0.80"',1)
html=html.replace("lastTailRepair='',tailRepairRows=[]", "lastTailRepair='',lastPunctuation='',punctuationRows=[],tailRepairRows=[]",1)
renderer="""function renderPunctuation(){const chosen=$('punctuation-case').value||'punc-01';$('punctuation-samples').replaceChildren();for(const p of punctuationRows){if(p.case!==chosen)continue;const card=el('article');card.append(el('h3',p.label),el('p',p.text),el('p',p.seconds.toFixed(2)+'秒'));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src='/voice-proplus-media/'+p.media;card.append(audio);if(p.content_note)card.append(el('p',p.content_note));$('punctuation-samples').append(card);}}$('punctuation-case').onchange=renderPunctuation;
"""
html=html.replace('function renderTailRepair()',renderer+'function renderTailRepair()',1)
update="""if(s.punctuation_sha256&&s.punctuation_sha256!==lastPunctuation){lastPunctuation=s.punctuation_sha256;punctuationRows=s.punctuation_samples||[];const previous=$('punctuation-case').value;$('punctuation-case').replaceChildren();const seen=new Set();for(const p of punctuationRows){if(seen.has(p.case))continue;seen.add(p.case);const option=el('option',p.case_title);option.value=p.case;$('punctuation-case').append(option);}if(seen.has(previous))$('punctuation-case').value=previous;else $('punctuation-case').value='punc-01';renderPunctuation();}"""
html=html.replace('if(s.tail_repair_sha256&&',update+'if(s.tail_repair_sha256&&',1)
html=html.replace("let info=s.progress.activity==='e14-tail-repair'?", "let info=s.progress.activity==='punctuation-tail-patches'?'正在核对分句与三道补丁':s.progress.activity==='e14-tail-repair'?",1)
p.write_text(html,encoding='utf-8')
print(json.dumps({'comparisons':len(rows),'sentences':9,'asr_manifest':str(O/'verification/manifest.json')},ensure_ascii=False))
