"""Voice-only delivery planning: preserve the approved LLM words exactly."""
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
import re
import nailv_cosy_performance as perf

VERSION='cosy-delivery-v2'
PROFILES={'baseline':'上一版','flow':'语流连贯','expressive':'语流与情绪稍加强'}


def _recent_laugh(history):
    recent=[x for x in (history or []) if isinstance(x,dict) and x.get('role')=='assistant'][-1:]
    return any(isinstance(e,dict) and e.get('kind')=='laughter' for x in recent
               for e in (x.get('voice_events') if isinstance(x.get('voice_events'),list) else []))


def plan(payload, profile='expressive', history=None):
    if profile not in PROFILES:raise ValueError('未知的语音表达方案。')
    result=dict(payload)
    text=payload['tts_text'];original=text;style=payload['style'];notes=[]
    if profile=='expressive':
        # Prefer a small smiling phrase over an isolated, stock laugh event.
        if style in ('teasing','excited') and '<laughter>' not in text:
            choices=('不过行吧','可以啊你','我就当你懂了吧','你最好是真懂了','行吧','太好了','终于过了','我也没招儿')
            chosen=next((x for x in choices if x in text),None)
            existing='[laughter]' in text
            if chosen and existing and '<strong>' not in text:
                text=text.replace('[laughter]','',1)
                text=text.replace(chosen,'<laughter>'+chosen+'</laughter>',1)
                notes.append('把笑意限制在一个短语，不把全句变成大笑。')
        # Short contrast only; do not emphasize every word or every sentence.
        if text==original and '<strong>' not in text and '<laughter>' not in text:
            targets={
                'teasing':('没这么讲','我什么时候','你自己','你又懂了'),
                'explaining':('看看就看看','买不买','这个意思','不是那个'),
                'tsundere':('没生气','才没有','别闹','少来'),
                'surprised':('怎么会','真的假的','什么情况'),
            }.get(style,())
            chosen=next((x for x in targets if x in text),None)
            if chosen:
                text=text.replace(chosen,'<strong>'+chosen+'</strong>',1)
                notes.append('只突出一个对比短词，其余保持自然语流。')
    parsed=perf.parse_reply('<emotion:'+payload['emotion']+'>'+text,force_emotion=style)
    if parsed['clean_text']!=payload['spoken_text']:
        raise AssertionError('Voice delivery must not rewrite, add, delete or deduplicate the LLM words')
    result.update(tts_text=parsed['tts_payload']['tts_text'],events=parsed['tts_payload']['events'],
                  delivery_profile=profile,delivery_version=VERSION,delivery_notes=notes,
                  chunk_mode='legacy' if profile=='baseline' else 'thought',
                  fragment_interval=.18 if profile=='baseline' else 0.,
                  character_guard={'llm_words_unchanged':True,'llm_emotion_unchanged':True,
                      'reference_unchanged':True,'no_unscripted_laugh_or_breath':True,
                      'new_emphasis_max_phrases':1,'human_ooc_verdict':'pending'})
    return result


def chunks(text,mode='thought',limit=72):
    """Pack short reactions with their next clause; preserve punctuation and controls."""
    if mode not in ('legacy','thought'):raise ValueError('未知分句方式。')
    if not text or not perf.strip_markup(text):raise ValueError('没有要说的正文。')
    # Valid paired controls produced by the parser never span terminal punctuation.
    units=re.findall(r'[^。！？；;!?\n]+[。！？；;!?\n]*|[。！？；;!?\n]+',text)
    assert ''.join(units)==text
    if mode=='legacy':
        if any(len(perf.strip_markup(x))>80 for x in units):raise ValueError('上一版单句超过80字，请缩短。')
        return units
    if not 16<=limit<=80:raise ValueError('意群长度上限不合适。')
    # Avoid cuts inside a paired tag. Split only at unwrapped punctuation.
    atom=re.compile(r'<(?:strong|laughter)>.*?</(?:strong|laughter)>|\[(?:breath|laughter)\]|.',re.S)
    short=[]
    for unit in units:
        if len(perf.strip_markup(unit))<=limit:
            short.append(unit);continue
        tokens=atom.findall(unit);part=[];size=0
        for token in tokens:
            n=len(perf.strip_markup(token))
            while size+n>limit and part:
                split=next((i+1 for i in range(len(part)-1,-1,-1) if part[i] in '，,、：:'),len(part))
                short.append(''.join(part[:split]));part=part[split:];size=len(perf.strip_markup(''.join(part)))
            part.append(token);size+=n
        if part:short.append(''.join(part))
    out=[];pending=''
    for unit in short:
        if pending and len(perf.strip_markup(pending+unit))>limit:
            out.append(pending);pending=''
        pending+=unit
    if pending:out.append(pending)
    assert ''.join(out)==text
    assert all(len(perf.strip_markup(x))<=80 for x in out)
    return out
