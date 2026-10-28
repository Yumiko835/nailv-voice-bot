"""Project-local fix: retain lexical boundaries for repeated two-character kinship nouns.

No punctuation, samples, model weights or spoken characters are inserted/removed.
Other projects use their original frontend.
"""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import types
KINSHIP={'妈妈','爸爸','奶奶','爷爷','姐姐','哥哥','妹妹','弟弟','宝宝','叔叔','伯伯','公公','婆婆'}
def install():
 from text import chinese2
 modifier=chinese2.tone_modifier
 if getattr(modifier,'_nailv_connected_fix',False):return
 original=modifier._merge_reduplication
 def merge(self,seg):
  result=[]
  for word,pos in seg:
   if result and word==result[-1][0] and word not in KINSHIP:result[-1][0]+=word
   else:result.append([word,pos])
  return result
 modifier._nailv_original_merge=original;modifier._merge_reduplication=types.MethodType(merge,modifier);modifier._nailv_connected_fix=True
def restore():
 from text import chinese2
 modifier=chinese2.tone_modifier
 if getattr(modifier,'_nailv_connected_fix',False):modifier._merge_reduplication=modifier._nailv_original_merge;modifier._nailv_connected_fix=False
