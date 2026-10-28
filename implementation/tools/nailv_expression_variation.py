"""Short conversation wording cooldown. Changes expression, never the reply's attitude."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import collections,re
MOTIFS=[r'(?:扣.{0,5}帽子|帽子.{0,5}扣.{0,3}(?:上|来|头))',r'蹬鼻子.{0,3}上脸',r'顺(?:着)?[杆竿](?:子)?(?:.{0,4}(?:爬|上))?']
def recent_replies(history):
 return [x.get('content','') for x in (history or []) if x.get('role')=='assistant'][-3:]
def protected(question):
 # An explanation, quotation or requested use of a word is allowed to contain that word.
 return bool(re.search(r'解释|什么意思|什么含义|怎么理解|词义|这个词|这句话|用.{0,12}(?:造句|说一句)',question))
def cooldown(question,history):
 if protected(question):return []
 old=recent_replies(history);result=[]
 for pattern in MOTIFS:
  for text in old:
   for match in re.finditer(pattern,text):
    phrase=match.group()
    if phrase not in question and phrase not in result:result.append(phrase)
 # Also catch previously unanticipated recurring clauses. Two different replies must share it.
 counts=collections.Counter()
 for text in old:
  grams=set()
  for span in re.findall(r'[\u3400-\u9fff]{5,}',text):
   for size in range(5,min(10,len(span))+1):grams.update(span[i:i+size] for i in range(len(span)-size+1))
  counts.update(grams)
 candidates=sorted((g for g,n in counts.items() if n>=2 and g not in question
  and re.match(r'(?:你(?:们|这人)?|别|我懒得|我可真|我倒是)',g)
  and re.search(r'怎么|又|就|别|倒是|可真|懒得|这人',g)
  and not re.search(r'生日|岁|奶糖花|奶姐|奶宝|奶神|奶比|妈妈|三月|四日|叫我|叫你',g)),key=lambda g:(-len(g),g))
 for phrase in candidates:
  if not any(phrase in x for x in result):result.append(phrase)
 return result[:10]
def repeats(reply,question,history):
 old=recent_replies(history)
 if protected(question):return []
 result=[x for x in cooldown(question,history) if x in reply]
 for pattern in MOTIFS:
  if re.search(pattern,question):continue
  if re.search(pattern,reply) and any(re.search(pattern,x) for x in old):
   result.extend(m.group() for m in re.finditer(pattern,reply))
 return list(dict.fromkeys(result))
def reference_penalty(excerpt,question,history):
 return 28 if repeats(excerpt,question,history) else 0
