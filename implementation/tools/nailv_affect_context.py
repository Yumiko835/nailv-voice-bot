"""User-corrected affect for this character's pet; no invented pet facts."""

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

VERSION='character-affect-v1'
RULE='''人物情绪补充（用户已校正）：谈起自己的猫坚果/店长，以及失去陪伴、寻找无果的往事，基调是克制的低落、惦念和难过；即使说明事实，也不是若无其事地解释、质问粉丝或开玩笑。不要为了悲伤加哭腔、呻吟、长省略号、强行叹气或句末嗯。用自然短句，不写表演动作。未有新证据不能把旧寻找记录说成“到现在也没找到/至今仍不清楚”，不编死亡、现况和新的经历。delivery.emotion用serious，intensity用soft，nonverbal用none；语音后台避开带质问感的叹气条。普通食品坚果、别人的猫、泛指工作店长不套这条规则。'''

def pet_loss_context(text,question='',history=None):
    current=' '.join([question or '',text or ''])
    if re.search(r'坚果.{0,15}(?:营养|零食|过敏|热量|腰果|杏仁|核桃)|(?:吃|买|袋|包|混合).{0,5}坚果',current) and not re.search(r'你的猫|你养|猫咪|布偶|找不到|没找到|失踪',current):
        return False
    if re.search(r'我(?:的)?(?:名字|昵称|网名)(?:就)?叫坚果|我(?:家|的).{0,3}(?:猫|狗).{0,5}(?:叫|是)坚果',current):return False
    if '坚果' in current:return True
    if '店长' in current and re.search(r'布偶|猫|寻找|找(?:过|不|没)|陪伴|失去|还活着|以前养',current):return True
    if re.search(r'他呢|他还|还想他|后来呢|然后呢|现在呢|那时候|找到了吗|还难过|想他吗',current):
        for turn in reversed((history or [])[-4:]):
            if isinstance(turn,dict) and pet_loss_context(str(turn.get('content',''))):return True
    return False

def routing_profile(text,question='',history=None):
    return 'pet_loss' if pet_loss_context(text,question,history) else None

def guard_reply(text,question='',history=None,used_ids=None):
    """Mirror the existing pet-record time boundary for AstrBot's native path.

    This is a narrow fallback, not a second cloud request or a new pet fact.
    """
    active=pet_loss_context(text,question,history)
    unsupported=bool(active and re.search(r'(?:到现在|至今|现在也|现在仍).{0,15}(?:没找到|没有找到|没消息|没有消息|说不好|不清楚|不知道)',text))
    if unsupported:
        return '那时候我找过他，没有找到。说起店长，还是会想起以前那些事。',True
    return text,False
