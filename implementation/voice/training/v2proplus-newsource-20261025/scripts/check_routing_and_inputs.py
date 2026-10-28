
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
import importlib.util
sys.path.insert(0,str(Path(__file__).parent));from emotion_routing import route,STYLES
bank=read(T/'prompts/manifest.json');assert set(bank['prompts'])==set(STYLES) and len(bank['prompts'])+len(bank['alternates'])==11;assert bank['prompts']['daily']['id']=='daily_legacy' and bank['prompts']['gentle']['id']=='gentle_a' and bank['prompts']['surprised']['id']=='surprised_b'
cases=[('晚安，好好休息吧。','gentle'),('哈哈，太好了！！','excited'),('啊？怎么会这样？','surprised'),('唉，真没办法。','sigh'),('对吧，我刚才说的是这个意思。','explaining')]
for text,expected in cases:assert route(text)['style']==expected,(text,route(text))
spoken='啊啊，那个那个，我说完了呢。'
for alias,style in [('日常','daily'),('开心','excited'),('调侃','teasing'),('温柔','gentle'),('慵懒','lazy'),('傲娇','tsundere'),('惊讶','surprised'),('严肃','serious'),('无奈','sigh'),('解释','explaining')]:
 r=route('['+alias+'] '+spoken,style='daily');assert r['style']==style and r['text']==spoken,'Manual prefix must take precedence without removing spoken repetitions'
for p in [*bank['prompts'].values(),*bank['alternates'].values()]:
 assert sha(p['path'])==p['sha256'] and sha(p['micro_gate_plan']['path'])==p['micro_gate_plan']['sha256']
verify_protected();summary={'emotion_styles':10,'reused_reference_clips':11,'recent_reference_choices_correct':True,'manual_prefix_overrides_dropdown':True,'spoken_fillers_and_repeats_retained':True,'auto_routing_scenarios':len(cases),'source_data_and_model_hashes_unchanged':True,'audio_listening_not_tested':True};write(T/'routing-input-verification.json',summary);print(json.dumps(summary,ensure_ascii=False))
