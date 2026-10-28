"""Explicit prefix/dropdown first, contextual hints second. Spoken text stays intact after the control prefix."""

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
STYLES={'daily':'日常闲聊','excited':'开心兴奋','teasing':'调侃戏谑','gentle':'温柔低语','lazy':'慵懒随性','tsundere':'傲娇小抱怨','surprised':'惊讶疑惑','serious':'认真严肃','sigh':'无奈叹气','explaining':'解释／向粉丝确认'}
ALIASES={'日常':'daily','日常闲聊':'daily','口癖':'particles','口癖高发':'particles','开心':'excited','兴奋':'excited','开心兴奋':'excited','调侃':'teasing','戏谑':'teasing','调侃戏谑':'teasing','温柔':'gentle','低语':'gentle','温柔低语':'gentle','慵懒':'lazy','慵懒随性':'lazy','傲娇':'tsundere','抱怨':'tsundere','小抱怨':'tsundere','傲娇小抱怨':'tsundere','惊讶':'surprised','疑惑':'surprised','惊讶疑惑':'surprised','认真':'serious','严肃':'serious','认真严肃':'serious','无奈':'sigh','叹气':'sigh','无奈叹气':'sigh'}
PATTERNS={'particles':(r'嗯[，,。…]|唔|那个[，,]|就是说|呃|啊这',1.1),'excited':(r'哈哈|笑死|太好了|好开心|好耶|太棒|激动|[!！]{2,}',1.5),'teasing':(r'少来|才不|别闹|可真行|想得美|瞎说|给自己加戏|逗我|你又来了',1.6),'gentle':(r'晚安|好好休息|别着急|慢慢说|乖|没关系|轻声|温柔|低声',1.6),'lazy':(r'困了|好困|懒得|随便啦|躺着|刚睡醒|懒洋洋',1.6),'tsundere':(r'哼|讨厌|烦死|才没有|不许|笨蛋|嫌弃|小抱怨',1.6),'surprised':(r'不会吧|居然|什么[？?]|怎么会|真的吗|诶[？?]|[？?]{2,}',1.7),'serious':(r'认真|严肃|因为|所以|道理|解释一下|我的意思是|问题在于',1.3),'sigh':(r'唉|哎呀|没办法|算了吧|无奈|无语|哭笑不得|叹气',1.6)}
ALIASES.update({'口癖':'excited','口癖高发':'excited','particles':'excited','解释':'explaining','确认':'explaining','解释确认':'explaining','向粉丝确认':'explaining','解释／向粉丝确认':'explaining'})
PATTERNS.pop('particles');PATTERNS['explaining']=(r'你是说|你的意思是|也就是说|是不是这个意思|明白了吗|明白了吧|我刚才说的是|你理解的|跟你确认|对吧',1.6)
def route(text,style='auto',context=''):
 if not isinstance(text,str) or not 1<=len(text)<=600 or not text.strip():raise ValueError('请输入1～600字。')
 if not isinstance(context,str) or len(context)>2000:raise ValueError('上下文最多2000字。')
 original=text;prefix=re.match(r'^\s*[\[【]([^\]】]{1,12})[\]】][ \t]*',text)
 if prefix and prefix.group(1) in ALIASES:
  chosen=ALIASES[prefix.group(1)];spoken=text[prefix.end():]
  if not spoken.strip():raise ValueError('情绪标签后还需要输入要说的话。')
  return {'style':chosen,'label':STYLES[chosen],'text':spoken,'input_text':original,'control_prefix':prefix.group(),'automatic':False,'reason':['按你输入的情绪标签点播']}
 if style!='auto':
  chosen=ALIASES.get(style,style)
  if chosen not in STYLES:raise ValueError('未知情绪选项。')
  return {'style':chosen,'label':STYLES[chosen],'text':text,'input_text':original,'control_prefix':None,'automatic':False,'reason':['按手动情绪选项点播']}
 scores={k:0. for k in STYLES};scores['daily']=.8;why={k:[] for k in STYLES}
 for key,(pattern,weight) in PATTERNS.items():
  hits=re.findall(pattern,text);past=re.findall(pattern,context);scores[key]=min(len(hits),3)*weight+min(len(past),2)*weight*.25;why[key]=hits[:3] or (['结合上下文线索'] if past else [])
 if re.search('不开心|没精神|难过|伤心|笑不出来',text):scores['excited']-=3;scores['gentle']+=2
 chosen=max(scores,key=scores.get);return {'style':chosen,'label':STYLES[chosen],'text':text,'input_text':original,'control_prefix':None,'automatic':True,'reason':why[chosen] or ['线索不明确，使用日常参考'],'scores':scores,'limitation':'Text/punctuation/context heuristics suggest a candidate emotion; manual override takes precedence. Emotion likeness still needs listening.'}
