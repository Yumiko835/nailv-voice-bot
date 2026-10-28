"""Character speech contract. No model, network or GPU work occurs on import."""
from __future__ import annotations

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(project_path(''))
POOL = ROOT / 'voice/comparison/cosyvoice2-20261026/prompts/manifest.json'
VERSION = 'cosy-performance-v1'
LABELS = {
    'daily': '日常闲聊', 'excited': '开心兴奋', 'teasing': '调侃戏谑',
    'lazy': '慵懒随性', 'tsundere': '傲娇抱怨', 'surprised': '惊讶疑惑',
    'serious': '认真严肃', 'sigh': '无奈叹气', 'explaining': '解释确认',
}
ALIASES = {**{v: k for k, v in LABELS.items()}, **{k: k for k in LABELS},
           '日常': 'daily', '闲聊': 'daily', '调侃': 'teasing', '开心': 'excited',
           '傲娇小抱怨': 'tsundere', '傲娇/小抱怨': 'tsundere',
           '解释／向粉丝确认': 'explaining', '解释/向粉丝确认': 'explaining',
           '向粉丝确认': 'explaining', '确认': 'explaining', '无奈': 'sigh',
           '惊讶': 'surprised', '疑惑': 'surprised', '严肃': 'serious', '慵懒': 'lazy'}
DISABLED = {'gentle', '温柔低语', '温柔', '温柔低语 · 候选A'}
EMOTION = re.compile(r'<emotion\s*:\s*([^<>\n]{1,60})\s*>', re.I)
CONTROL = re.compile(r'<[^>\n]*>|\[[^\]\n]*\]')
EVENT = re.compile(r'<(strong|laughter)>(.*?)</\1>|\[(breath|laughter)\]|<[^>\n]*>|\[[^\]\n]*\]', re.S)
END = re.compile(r'[。！？!?；;\n]')
ALLOWED_TOKENS = ('[breath]', '[laughter]', '<laughter>', '</laughter>', '<strong>', '</strong>')


def active_bank(pool: Path = POOL):
    bank = json.loads(pool.read_text(encoding='utf-8'))['prompts']
    return {k: v for k, v in bank.items() if k in LABELS and v.get('enabled', True)}


def system_suffix(history=None):
    options = '、'.join(LABELS[k] for k in active_bank())
    recent = [x for x in (history or []) if isinstance(x,dict) and x.get('role')=='assistant'][-2:]
    used = {event.get('kind') for x in recent for event in x.get('voice_events',[]) if isinstance(event,dict)}
    hint = '\n最近两轮已使用'+('笑声' if 'laughter' in used else '')+('、换气' if 'breath' in used else '')+'；本轮不惯性重复，只有语境确实需要才再用。' if used & {'laughter','breath'} else ''
    return f'''【本轮语音输出格式，覆盖前面“reply不写声音标签”的格式要求】
仍仅输出原有JSON，资料ID与delivery规则不变；把以下标记写在JSON的reply字符串内。
reply以<emotion:情绪名>开头，情绪只能从：{options} 中选一个，按你本轮回应的态度选，不机械照抄用户情绪。“温柔低语”已停用。
正文首先保持奶绿原有的用词、接话姿态、短起句与自然补半句；别为了演出改成播音、安慰模板或突然发嗲。可不加动作标签，动作不能改变话意或主客体。
确实需要一次自然换气才用[breath]，短轻笑用[laughter]；边笑边说的短语用<laughter>短语</laughter>；确有对比的短词用<strong>词</strong>。成对标签必须闭合、只包短语，不嵌套、不跨句。
每句话最多1～2个动作，整条最多4个，[breath]整条最多1次；别连续堆标签，别每轮都笑、每个逗号都吸气。标签不能代替标点。思考用自然词语和标点，[breath]不代替思考或所有叹气；不添加其它标签或括号舞台说明。
口癖与重复只在接招、找词或强调时自然出现；不要每句补嗯，不强行添加已撤回的气声。不用instruct2式的自然语言表演指令。{hint}'''


def strip_markup(text: str):
    text = CONTROL.sub('', EMOTION.sub('', text))
    return re.sub(r'[ \t]+', ' ', text).strip()


def fallback_emotion(text: str, question: str = '', history=None):
    # Select the reply's interaction, rather than blindly mirroring the user's mood.
    if re.search(r'我(?:不太|没)明白|真的假的|怎么会|怎么突然|啊[？?]|什么情况', text):
        return 'surprised'
    if re.search(r'恭喜|太好了|好耶|太厉害|成功啦|开心|赢了', text) and not re.search(r'不开心|别开心|不是.*开心', text):
        return 'excited'
    if re.search(r'逗你|你又懂了|我就当你懂|瞧把你|还挺会|就你会|学会了是吧|又开始了', text):
        return 'teasing'
    if re.search(r'没生气|才没有|少来|不许|别闹|真是服了|你还来', text):
        return 'tsundere'
    if re.search(r'唉|没办法|又要|还得|我能怎么办|说了半天|怎么又', text):
        return 'sigh'
    if re.search(r'原则|认真说|这件事.*重要|不能这样|界限|首先.*其次', text):
        return 'serious'
    if re.search(r'我的意思|我是说|对啊|所以|不是.*是|你说的是|就是这个意思|你明白', text):
        return 'explaining'
    if re.search(r'歇会|歇一会|懒得|不着急|随便聊|发会呆', text):
        return 'lazy'
    return 'daily'


def _choose(raw, clean, bank, question, history, force_emotion):
    warnings = []
    match = EMOTION.match(raw.lstrip())
    requested = force_emotion or (match.group(1).strip() if match else '')
    if requested in DISABLED:
        return 'daily', 'disabled_reference_fallback', ['温柔低语已停用，改用日常闲聊。']
    style = ALIASES.get(requested)
    if style in bank:
        return style, 'manual' if force_emotion else 'llm', warnings
    if requested:
        warnings.append('未知或不可用的情绪标签，已使用规则兜底。')
    style = fallback_emotion(clean, question, history)
    return (style if style in bank else 'daily'), 'rules_fallback', warnings


def parse_reply(raw: str, question: str = '', history=None, force_emotion=None, *, bank=None):
    """Return display text and a trusted, allowlisted zero-shot request separately."""
    if not isinstance(raw, str) or len(raw) > 4000:
        raise ValueError('回复格式或长度不合适。')
    bank = active_bank() if bank is None else bank
    if 'daily' not in bank:
        raise ValueError('缺少日常参考，暂时仅提供文字回复。')
    clean = strip_markup(raw)
    if not clean:
        raise ValueError('模型没有返回可显示的正文。')
    style, source, warnings = _choose(raw, clean, bank, question, history, force_emotion)
    body = EMOTION.sub('', raw).strip()
    fragments, events, cursor, count, breaths = [], [], 0, 0, 0
    sentence_counts = {}
    visible_prefix = ''
    last_event_end = -1
    for match in EVENT.finditer(body):
        plain = body[cursor:match.start()]
        fragments.append(plain)
        visible_prefix += plain
        sentence = len(END.findall(visible_prefix))
        paired, inner, single = match.group(1), match.group(2), match.group(3)
        token = single or paired
        paired_valid = bool(paired and inner.strip() and len(inner) <= 24 and not END.search(inner) and not CONTROL.search(inner))
        accepted = bool((single or paired_valid) and count < 4 and sentence_counts.get(sentence, 0) < 2)
        if single == 'breath' and (breaths >= 1 or not strip_markup(visible_prefix).strip('，,。！？!?；;… ')):
            accepted = False
        if match.start() == last_event_end:
            accepted = False
        if accepted:
            fragments.append(match.group())
            count += 1
            breaths += int(single == 'breath')
            sentence_counts[sentence] = sentence_counts.get(sentence, 0) + 1
            events.append({'kind': token, 'sentence': sentence, 'text': inner if paired else ''})
            last_event_end = match.end()
        else:
            # Invalid wrappers lose formatting, never their spoken words.
            fragments.append(strip_markup(inner) if paired else '')
            warnings.append('已移除未知、过密或格式不完整的演出标签。')
        if paired:
            visible_prefix += strip_markup(inner)
        cursor = match.end()
    fragments.append(body[cursor:])
    tts_text = re.sub(r'[ \t]+', ' ', ''.join(fragments)).strip()
    assert strip_markup(tts_text) == clean, 'Markup parser must preserve all spoken words and repetitions'
    prompt = bank[style]
    payload = {
        'version': VERSION, 'model': 'CosyVoice2-0.5B', 'mode': 'zero_shot',
        'emotion': LABELS[style], 'style': style, 'route_source': source,
        'tts_text': tts_text, 'spoken_text': clean,
        'prompt_speech': prompt['path'], 'prompt_text': prompt['text'],
        'reference_id': prompt['reference_id'], 'reference_sha256': prompt['sha256'],
        'text_frontend': False, 'events': events,
    }
    return {'clean_text': clean, 'tts_payload': payload, 'warnings': list(dict.fromkeys(warnings))}


def validate_reference(payload, bank=None):
    bank = active_bank() if bank is None else bank
    entry = bank[payload['style']]
    if payload['style'] not in LABELS or payload['style'] == 'gentle':
        raise ValueError('参考已停用。')
    path = Path(entry['path']).resolve()
    if not path.is_relative_to(POOL.parent.resolve()):
        raise ValueError('参考文件不在本项目允许的参考池中。')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != entry['sha256'] or payload['reference_sha256'] != digest or payload['prompt_text'] != entry['text'] or Path(payload['prompt_speech']).resolve() != path:
        raise ValueError('参考原声或逐字台词已变化，请重新加载参考。')
    return entry
