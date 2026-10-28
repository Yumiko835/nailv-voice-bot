"""Compact live-chat taxonomy; original study/reference pools stay intact."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import re

VERSION='practical-six-v1'
LABELS={'daily':'自然闲聊','teasing':'调侃亲昵','tsundere':'轻嗔吐槽',
        'explaining':'解释确认','excited':'开心惊喜','serious':'沉稳认真'}
LEGACY_LABELS={'日常闲聊':'daily','开心兴奋':'excited','调侃戏谑':'teasing',
    '慵懒随性':'lazy','傲娇抱怨':'tsundere','傲娇小抱怨':'tsundere',
    '惊讶疑惑':'surprised','认真严肃':'serious','无奈叹气':'sigh','解释确认':'explaining'}

def normalize(value,text=''):
    if not isinstance(value,str):return None
    value={**LEGACY_LABELS,**{v:k for k,v in LABELS.items()}}.get(value,value)
    if value=='lazy':return 'daily'
    if value=='sigh':
        return 'serious' if re.search(r'难过|想起他|失去|舍不得|惦记|惦念|低落|遗憾',text) else 'tsundere'
    if value=='surprised':
        return 'excited' if re.search(r'太好了|好耶|恭喜|好厉害|居然|天哪|不会吧[！!]|真的[！!]',text) else 'explaining'
    return value if value in LABELS else None

def configure(perf):
    """Process-local configuration, so the accepted CV2 app is untouched."""
    original=perf.active_bank
    perf.active_bank=lambda *a,**kw:{k:v for k,v in original(*a,**kw).items() if k in LABELS}
    perf.LABELS=dict(LABELS)
    perf.ALIASES.update({**{v:k for k,v in LABELS.items()},**{k:k for k in LABELS}})
    # Old dropdown values remain accepted while a page is open during reload.
    perf.ALIASES.update({'lazy':'daily','慵懒随性':'daily','慵懒':'daily',
        'sigh':'tsundere','无奈叹气':'tsundere','无奈':'tsundere',
        'surprised':'explaining','惊讶疑惑':'explaining','疑惑':'explaining'})
