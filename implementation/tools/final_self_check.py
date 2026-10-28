
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from pathlib import Path
import hashlib,json,re,sys,urllib.request
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'));import publish_nailv_library as p
base='http://127.0.0.1:49850'
req=urllib.request.Request(base+'/api/chat',json.dumps({'message':'LLL选歌掷骰子那次，两轮你和发卡分别掷了多少？','history':[],'semantic':False},ensure_ascii=False).encode(),{'Content-Type':'application/json','Origin':base})
with urllib.request.urlopen(req,timeout=90) as response:out=json.load(response)
print(json.dumps({'reply':out['content']['reply'],'sources':[x['id'] for x in out['references']]},ensure_ascii=False),flush=True)
assert 'fact-self-lll-dice' in [x['id'] for x in out['references']]
items=p.load('data/self-supplement/items.json')['items'];pending=p.load('review/self-supplement-20261024/subtitle-pending.json')['items']
assert all(x['active_in_text_pilot'] for x in items) and all(not x['active_in_text_pilot'] for x in pending)
assert not {x['id'] for x in items}&{x['id'] for x in pending}
assert not any('论文致谢' in x['text'] for x in items)
previous=p.load('outputs/人物资料补充试聊核验.json');previous['edition_note']='Earlier experimental checks before speaker-attribution quarantine. Current retained-source checks are in 人物资料补充离线核验.json and 人物资料补充HTTP核验.json.';p.save('outputs/人物资料补充试聊核验.json',previous)
result={'active_items':len(items),'subtitle_pending':len(pending),'pending_excluded_from_pilot':True,'known_sc_misattribution_excluded':True,'dice_targeted_http_response':out['content']['reply'],'dice_expected':{'first_round':{'奶绿':6,'发卡':6},'second_round':{'奶绿':1,'发卡':2}},'no_automatic_similarity_or_human_approval':True,'runtime_hashes':{n:hashlib.sha256((R/'tools'/n).read_bytes()).hexdigest() for n in ['nailv_text_core.py','nailv_text_server.py','nailv_self_knowledge.py']}}
p.save('outputs/人物资料补充最终核验.json',result)
