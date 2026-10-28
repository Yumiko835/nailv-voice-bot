
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
receipt=read(T/'training-receipt.json');chosen=min(receipt['exports'],key=lambda r:r['validation_loss']);write(T/'selected-models.json',{'version':'v2ProPlus','gpt':chosen,'gpt_selection_basis':'Minimum loss across the10 original validation items; independent10 holdouts unused.','sovits_epoch':10,'sovits':None,'sovits_selection_basis':'Requested10-epoch final export, provisional until listening; every even-epoch checkpoint retained.','human_naturalness_verified':False})
texts={'daily':'嗯，今天先随便聊一会儿，你们刚才在说什么？','excited':'哇，真的假的？这也太好了吧，哈哈！','teasing':'你又来了，哪有你说得那么夸张啊。','gentle':'嗯，别着急，慢慢说。我在听呢。','lazy':'好困啊，让我再躺一会儿嘛。','tsundere':'哼，我才没有生气呢，你少在那里胡说。','surprised':'啊？你刚才说什么？真的假的，我都没反应过来。','serious':'我认真说，这件事情还是先弄清楚比较好。','sigh':'唉，怎么又是这样啊。算了，慢慢来吧。','explaining':'对，我刚才说的就是这个意思，你明白了吧？'}
samples=[{'id':k,'style':k,'text':v,'seed':42} for k,v in texts.items()]+[{'id':'excited-oral','style':'excited','reference_key':'excited_oral','text':texts['excited'],'seed':42},{'id':'repeated-mama','style':'daily','text':'妈妈妈妈，这么喜欢叫妈妈吗','seed':42}];write(T/'generated/test-requests.json',{'samples':samples})
print(json.dumps({'gpt_epoch':chosen['epoch'],'test_samples':len(samples),'prompts':11},ensure_ascii=False))
