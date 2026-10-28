"""Background-only speech intent contract; no acting tags or extra model call."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from nailv_live_emotions import LABELS,normalize
VERSION='background-voice-intent-v2-practical-six'
SUFFIX='''后台语音语气分类（不改变reply的语言风格，不额外编台词）：
在已有delivery对象中另写emotion字段，只从六类选一个：daily(自然闲聊、随意接话)、teasing(调侃亲昵、接梗反话)、tsundere(轻嗔吐槽、抱怨制止)、explaining(解释确认、求证纠正)、excited(开心惊喜、积极庆祝)、serious(沉稳认真、克制低落)。
低落不是生气抱怨；想念、失去陪伴和认真往事用serious，不用tsundere或explaining。普通疑问和没听懂用explaining，只有带积极惊喜才excited。困倦松弛并入daily，不为配齐种类添加情绪词；调侃也不每次哈哈大笑。
根据你这条回复在当前对话中的表达姿态选，不照搬用户心情，不因没有感叹号就填daily。反话、装不承认、接招打趣、轻微抱怨也有各自语气；事实澄清不自动生气，普通自我介绍可以daily。表达有主次时选主导语气，真正没有明显情绪再daily，不强行演戏。
分类只写delivery.emotion；reply中不写情绪标签、动作标签、表演指令或分类说明。tone等原字段照常填写，温柔低语已停用。'''

def validate(value):
    if not isinstance(value,str):return None
    return normalize(value)
