"""Source-attributed addresses and community language, with narrow contextual recall."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import json,re
from pathlib import Path
ROOT=Path(project_path(''))
ITEMS='data/community/items.json';MANIFEST='data/community/semantic.json';CONSENT='review/称呼与社区梗向量范围-20261024.json'
def data():return json.loads((ROOT/ITEMS).read_text(encoding='utf-8'))
def rows():return data()['items']
def suppressed_ids():return set(data()['runtime_superseded_ids'])
def match(alias,text):
 if alias.isascii():return bool(re.search(r'(?<![A-Za-z])'+re.escape(alias)+r'(?![A-Za-z])',text,re.I))
 return alias in text

def mama_address(text):
 # Calling the character is distinct from talking about an actual relative.
 if not re.search(r'妈妈|麻麻|妈咪',text):return False
 if re.search(r'亲生|生母|现实.{0,5}(?:母亲|亲子)|生了我',text):return False
 if re.search(r'(?:叫|喊|称)(?:你|您)(?:为|作)?(?:妈妈|麻麻|妈咪)',text):return True
 if re.search(r'(?<!是)(?:我|你|他|她|您)(?:的)?(?:妈妈|麻麻|妈咪)',text):return False
 if re.search(r'(?:你|我|他|她)(?:的)?(?:妈妈|妈咪).{0,12}(?:生病|去世|住院|手术|病了|癌|身体|生我|养我)',text):return False
 return True

def wrong_mama_refusal(reply):
 # A joke about repetitive calling is allowed; categorical address bans are not.
 return bool(re.search(r'(?:妈妈|麻麻|妈咪).{0,5}(?:这(?:个)?称呼)?(?:还是)?(?:算了|不接受|不能叫|不让叫|别叫|不喜欢)|(?:称呼|叫法).{0,7}(?:不敢接|不能接|不接受|算了)|(?:不许|不要|别|不能|不让)(?:你)?(?:再)?(?:叫|喊)(?:我)?(?:妈妈|麻麻|妈咪)|不是[。！!，,\s]*(?:这个)?别乱认',reply))
def retrieve(question,history=None,limit=6):
 all_rows=rows();q=question.strip();selected=[]
 address_mama=mama_address(q)
 literal_insult=bool(re.search(r'狗娘养|狗娘養|娘养的|娘養的',q))
 naming=bool(re.search(r'称呼|叫你|叫我|叫她|叫粉丝|叫观众|粉丝.{0,6}(?:叫|名)|观众.{0,6}叫|怎么称',q))
 for x in all_rows:
  hit=any(match(a,q) for a in x['aliases'])
  if x['id'].endswith('-mama'):hit=address_mama
  if x['id'].endswith('-niangyang') and literal_insult:hit=False
  if x['id'].endswith('-address-flexible'):hit=naming or address_mama
  if x['id'].endswith('-naitanghua') and naming:hit=True
  if hit:selected.append(x)
 # A short dependent question may continue a term discussion; don't carry vocabulary over a topic switch.
 dependent=bool(re.fullmatch(r'(?:那|还有|那还有|这个|那这个).{0,8}(?:呢|啥意思|什么意思)[？?]?',q) or re.search(r'^(?:这不就是|那不就是|这不是|不是吗|怎么还|咋还|你还|所以呢|是吗|对啊|那又|这就|又生气)',q))
 address_followup=bool(re.search(r'^(?:那|你|怎么|为什么|为啥|这个|这样|这).{0,16}(?:称呼|不让.{0,3}(?:叫|喊)|不敢接|不能认|(?:叫|喊)(?:呢|吗|啊|呀|[？?]))',q))
 if not selected and address_followup and history:
  for turn in reversed(history[-6:]):
   if turn.get('role')!='user':continue
   if mama_address(turn.get('content','')):
    selected=[x for x in all_rows if x['id'] in ('fact-community-mama','fact-community-address-flexible')]
   break
 if not selected and dependent and history:
  for turn in reversed(history[-6:]):
   if turn.get('role')!='user':continue
   prev=turn.get('content','')
   selected=[x for x in all_rows if x['kind']=='term' and any(match(a,prev) for a in x['aliases'])]
   if selected:break
   if not re.search(r'^(?:这|那|不是|怎么|咋|你还|所以|是吗|对啊|又)',prev):break
 return selected[:limit]
def routing_brief(question,history=None):
 return [{k:x[k] for k in ('id','text','kind','realm','usage_scope')} for x in retrieve(question,history)]
def grounded_history(question,history):
 # A demonstrated old factual error is not a source. Keep other conversation and all user messages.
 ids={x['id'] for x in retrieve(question,history)};out=[];previous=''
 for turn in history or []:
  text=turn.get('content','')
  if turn.get('role')=='user':previous=text
  if turn.get('role')=='assistant':
   if 'fact-community-naijie' in ids and re.search(r'奶姐.{0,10}(?:算了|不|老)|年纪|显老|喊老|往老',text):continue
   protected=bool(re.search(r'隐私|住址|真名|密钥|刷屏|辱骂|骚扰|亲生',previous))
   if 'fact-community-mama' in ids and mama_address(previous) and not protected and wrong_mama_refusal(text):continue
  out.append(turn)
 return out

# Vector integrity and serialization are identical to the isolated preference extension.
def text_set(items):
 from nailv_preference_knowledge import text_set as fingerprint
 return fingerprint(items)
def load_semantic_index():
 import hashlib,sys
 import publish_nailv_library as p
 if not (ROOT/MANIFEST).exists():return None
 active=sorted(rows(),key=lambda x:x['id']);consent=p.load(CONSENT);meta=p.load(MANIFEST);folder=(ROOT/meta['folder']).resolve()
 if not folder.is_relative_to((ROOT/'data/community/semantic').resolve()):raise RuntimeError('Invalid community index path')
 catalog=json.loads((folder/'catalog.json').read_text(encoding='utf-8'));m=catalog['metadata'];fingerprint=text_set(active)
 if consent.get('status')!='completed' or consent.get('text_set_sha256')!=fingerprint or m['text_set_sha256']!=fingerprint or m['embedding_model']!=p.MODEL or m['dimensions']!=p.DIM or m['endpoint']!=p.ENDPOINT:raise RuntimeError('Community index is stale')
 if m['item_count']!=len(active) or catalog['binary_endian']!=sys.byteorder or [(x['id'],x['text_sha256']) for x in catalog['items']]!=[(x['id'],p.digest(x['text'])) for x in active]:raise RuntimeError('Community catalog mismatch')
 binary=folder/'vectors.f32'
 if binary.stat().st_size!=len(active)*p.DIM*4 or hashlib.sha256(binary.read_bytes()).hexdigest()!=catalog['binary_sha256']:raise RuntimeError('Community vector integrity mismatch')
 return {'catalog':catalog,'binary':binary,'by_id':{x['id']:x for x in active},'label':'community_addresses'}
def build_vectors():
 import array,hashlib,math,sys
 import publish_nailv_library as p
 active=sorted(rows(),key=lambda x:x['id']);fingerprint=text_set(active)
 consent={'status':'authorized_by_existing_project_scope','provider':'Zhipu BigModel','recorded_at':p.now(),'authorization_basis':['那先帮我把所有的可用资料上传','去检索补充一下称呼','也可以去检索一下V圈的一些网络梗好让她也能听懂','上限100块'],'scope':'Only new curated address and community-definition summaries; not private chats, screenshots, source video or full subtitles.','text_fields_transmitted':['text'],'item_count':len(active),'text_set_sha256':fingerprint}
 p.save(CONSENT,consent);client=p.Embeddings(purpose='community');vectors=[]
 for i in range(0,len(active),32):vectors+=client.fetch([x['text'] for x in active[i:i+32]])
 folder=ROOT/'data/community/semantic'/fingerprint[:16];folder.mkdir(parents=True,exist_ok=True)
 with (folder/'vectors.f32').open('wb') as stream:
  for vec in vectors:
   norm=math.sqrt(sum(v*v for v in vec));stream.write(array.array('f',(v/norm for v in vec)).tobytes())
 cat={'metadata':{'embedding_model':p.MODEL,'dimensions':p.DIM,'endpoint':p.ENDPOINT,'item_count':len(active),'text_set_sha256':fingerprint,'created_at':p.now()},'items':[{'id':x['id'],'text':x['text'],'text_sha256':p.digest(x['text']),'category':'facts','kind':x['kind']} for x in active],'binary_sha256':hashlib.sha256((folder/'vectors.f32').read_bytes()).hexdigest(),'binary_endian':sys.byteorder}
 p.save(str((folder/'catalog.json').relative_to(ROOT)),cat);consent.update(status='completed',completed_at=p.now());p.save(CONSENT,consent)
 p.save(MANIFEST,{'folder':str(folder.relative_to(ROOT)).replace('\\','/'),'item_count':len(active),'text_set_sha256':fingerprint})
 assert len(load_semantic_index()['by_id'])==len(active)
 print(json.dumps({'community_vectors_ready':len(active)}),flush=True)
if __name__=='__main__':build_vectors()
