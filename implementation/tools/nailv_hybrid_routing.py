"""Transparent style heuristics with explicit override; never rewrite the spoken text."""

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
STYLES={'daily':'日常自然','particles':'口语与语气词','excited':'开心活泼','gentle':'温柔偏慢','teasing':'调侃接话'}
def choose_style(text,style='auto'):
 if not isinstance(text,str) or not text.strip():raise ValueError('请输入要说的话。')
 if not isinstance(style,str):raise ValueError('语气选项无效。')
 if style!='auto':
  if style not in STYLES:raise ValueError('语气选项无效。')
  return {'style':style,'label':STYLES[style],'reason':['按你手动指定的语气'],'automatic':False,'text':text}
 scores={k:0. for k in STYLES};scores['daily']=.7;reasons={k:[] for k in STYLES}
 def add(style,pattern,weight):
  hits=re.findall(pattern,text)
  if hits:scores[style]+=min(len(hits),3)*weight;reasons[style]+=[str(h) for h in hits[:3]]
 add('gentle',r'晚安|累了|好累|累死|难过|伤心|想哭|哭了|呜呜|唉|没关系|别着急|慢慢说|慢慢来|好好休息|轻声|温柔|低声|安慰|不开心|没精神',1.5)
 add('excited',r'哈哈|笑死|太好了|好耶|激动|好开心|真开心|太棒了|哇[！!]|[!！]{2,}',1.3)
 add('excited',r'[!！]',.3)
 add('teasing',r'瞎说|得了吧|可真行|才不|就你|别闹|想得美|凭什么|不至于|你又来|少来|胡说|扣帽子',1.15)
 add('particles',r'嗯[，,。.…]|唔|啊这|那个[，,]|就是说|哎呀|诶[，,]|[呀呢吧呗嘛啦][，,。！？!?…]',.55)
 if re.search('不开心|没精神|笑不出来|难过|伤心',text):scores['excited']-=2
 if scores['gentle']>=1.5 or scores['excited']>=1.3 or scores['teasing']>=1.15:scores['particles']*=.35
 chosen=max(scores,key=scores.get)
 return {'style':chosen,'label':STYLES[chosen],'reason':reasons[chosen] or ['未出现明确语气线索，使用日常参考'],'automatic':True,'scores':scores,'text':text,'limitation':'标点和口头词仅是线索，不能可靠判断真实心情；可手动指定。'}
def speech_chunks(text,limit=95):
 if not isinstance(text,str) or not 1<=len(text)<=600:raise ValueError('每次请输入1～600个字。')
 # Keep every original character and punctuation. Chunk only when needed for long utterances.
 if len(text)<=limit:return [text]
 units=re.findall(r'[^。！？!?\n]+[。！？!?\n]*|[。！？!?\n]+',text);out=[];acc=''
 for unit in units:
  if len(acc)+len(unit)>limit and acc:out.append(acc);acc=''
  if len(unit)>180:
   parts=re.findall(r'[^，,；;]+[，,；;]*|[，,；;]+',unit)
   for part in parts:
    if len(acc)+len(part)>limit and acc:out.append(acc);acc=''
    if len(part)>180:raise ValueError('这句话太长，请在自然停顿处加标点再生成。')
    acc+=part
  else:acc+=unit
 if acc:out.append(acc)
 assert ''.join(out)==text,'Spoken text must remain byte-for-byte unchanged.'
 return out
