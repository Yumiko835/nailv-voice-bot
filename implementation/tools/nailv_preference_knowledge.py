"""Source-checked taste cards: category/name recall, temporal scope, separate vectors."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import array,collections,hashlib,json,math,re,secrets,sys
from pathlib import Path
ROOT=Path(project_path(''))
ITEMS='data/preferences/items.json';MANIFEST='data/preferences/semantic.json';CONSENT='review/偏好补充向量范围-20261024.json'
CATEGORIES={'singer':r'歌手|乐队|音乐人|听谁|爱听|听的歌|喜欢.{0,8}歌|听什么歌|听哪些歌',
 'celebrity':r'明星|演员|女星|男星|艺人|偶像|追星',
 'voice_actor':r'声优|配音|\bCV\b',
 'character':r'角色|纸片人|二次元.*(?:谁|喜欢)|本命|单推',
 'work':r'作品|动漫|动画|番剧|电影|电视剧|小说|漫画|游戏|看什么|看哪些'}
DEPENDENT=re.compile(r'^(?:那|为啥|为什么|还有|她|他|这个|这部|这个人|你.{0,3}为什么)|前一|前面|上一|后面那|最后那')
STRONG={'favorite':10,'strong_like':9,'music_favorite':8,'music_like':7,'like':6,'past_favorite':5,'past_like':4,'portrayal_like':4,'appreciate':3}
def rows():return json.loads((ROOT/ITEMS).read_text(encoding='utf-8'))['items']
def text_set(items):
 import publish_nailv_library as p
 return p.digest(json.dumps([(x['id'],p.digest(x['text'])) for x in sorted(items,key=lambda x:x['id'])],ensure_ascii=False))
def contains(name,text):
 if len(name)<2:return bool(re.search(r'(?:演员|明星|喜欢|关于)'+re.escape(name)+r'(?:[吗呢啊，。？?\s]|$)',text))
 if name.isascii():return bool(re.search(r'(?<![A-Za-z])'+re.escape(name)+r'(?![A-Za-z])',text,re.I))
 return name.casefold() in text.casefold()
def entities_in(text,data):
 return {x['entity'] for x in data if any(contains(n,text) for n in [x['entity'],*x.get('aliases',[])])}
def request(question,history=None):
 data=rows();entities=entities_in(question,data)
 media={k for k,v in {'anime':r'动漫|动画|番剧','film':r'电影','drama':r'电视剧|韩剧|日剧|美剧','novel':r'小说','comic':r'漫画','game':r'游戏'}.items() if re.search(v,question)}
 works={x['work'] for x in data if x.get('work') and len(x['work'])>=2 and contains(x['work'],question)}
 if contains('JOJO',question):works.add('JOJO的奇妙冒险')
 cats={k for k,v in CATEGORIES.items() if re.search(v,question,re.I)}
 # More specific classes take precedence over generic 角色/偶像 terms.
 if 'voice_actor' in cats:cats={'voice_actor'}
 elif 'singer' in cats:cats.discard('celebrity')
 if re.search(r'动漫角色|动画角色|游戏角色|作品里.{0,6}角色',question):cats.discard('work')
 dependent=False
 if not entities and DEPENDENT.search(question) and history:
  latest_user=next((x.get('content','') for x in reversed(history[-6:]) if x.get('role')=='user'),'')
  previous=entities_in(latest_user,data)
  if len(previous)==1:entities=previous;dependent=True
  elif re.search(r'为什么|为啥|哪一点|哪个地方|她|他|这个',question):
   latest_assistant=next((x.get('content','') for x in reversed(history[-4:]) if x.get('role')=='assistant'),'')
   previous=entities_in(latest_assistant,data)
   if len(previous)==1:entities=previous;dependent=True
  if not cats and not entities and re.search(r'还有|别的|其他',question):
   cats={k for k,v in CATEGORIES.items() if re.search(v,latest_user,re.I)};dependent=bool(cats)
 broad=bool(cats and re.search(r'谁|哪些|什么|几个|几位|有没有|都|喜欢|最爱|本命|爱看|爱听|推荐',question))
 active=bool(entities or broad or dependent or works)
 return {'entities':entities,'works':works,'media':media,'categories':cats,'broad':broad,'active':active,'dependent':dependent}
def retrieve(question,history=None,limit=6):
 data=rows();scope=request(question,history)
 if not scope['active']:return [],scope
 if scope['works'] and 'character' in scope['categories']:
  pool=[x for x in data if x['preference_category']=='character' and x.get('work') in scope['works']]
 elif scope['entities']:pool=[x for x in data if x['entity'] in scope['entities'] or any(e in x.get('aliases',[]) for e in scope['entities'])]
 else:pool=[x for x in data if x['preference_category'] in scope['categories'] and x['preference_strength'] in STRONG and (x['preference_category']!='work' or not scope['media'] or set(x.get('work_media',[])) & scope['media'])]
 recent=' '.join(x.get('content','') for x in (history or [])[-6:] if x.get('role')=='assistant')
 seed=secrets.token_hex(6)
 def score(x):
  s=STRONG.get(x['preference_strength'],2)
  if scope['entities']:s+=20
  if any(contains(n,question) for n in x.get('aliases',[])):s+=15
  if re.search('为什么|为啥|原因|哪里|哪点',question) and len(x['text'])>60:s+=3
  if re.search('以前|小时候|过去',question) and x['preference_strength'].startswith('past'):s+=4
  if not scope['entities'] and contains(x['entity'],recent):s-=15
  return (-s,hash(seed+x['id']))
 pool.sort(key=score);selected=[];counts=collections.Counter()
 for x in pool:
  if counts[x['entity']] >= (3 if scope['entities'] else 1):continue
  selected.append(x);counts[x['entity']]+=1
  if len(selected)>=limit:break
 return selected,scope

def load_semantic_index():
 import publish_nailv_library as p
 if not (p.ROOT/MANIFEST).exists():return None
 data=rows();consent=p.load(CONSENT);meta=p.load(MANIFEST);folder=(p.ROOT/meta['folder']).resolve()
 if not folder.is_relative_to((p.ROOT/'data/preferences/semantic').resolve()):raise RuntimeError('Invalid preference index path')
 catalog=json.loads((folder/'catalog.json').read_text(encoding='utf-8'));m=catalog['metadata']
 if consent.get('status')!='completed' or consent.get('text_set_sha256')!=text_set(data) or m['text_set_sha256']!=text_set(data) or m['embedding_model']!=p.MODEL or m['dimensions']!=p.DIM or m['endpoint']!=p.ENDPOINT:raise RuntimeError('Preference semantic index is stale')
 if catalog['binary_endian']!=sys.byteorder or [(x['id'],x['text_sha256']) for x in catalog['items']]!=[(x['id'],p.digest(x['text'])) for x in sorted(data,key=lambda x:x['id'])]:raise RuntimeError('Preference catalog mismatch')
 binary=folder/'vectors.f32'
 if binary.stat().st_size!=len(data)*p.DIM*4 or hashlib.sha256(binary.read_bytes()).hexdigest()!=catalog['binary_sha256']:raise RuntimeError('Preference vector integrity mismatch')
 return {'catalog':catalog,'binary':binary,'by_id':{x['id']:x for x in data},'label':'preferences'}
def build_vectors():
 import publish_nailv_library as p
 active=sorted(rows(),key=lambda x:x['id']);fingerprint=text_set(active)
 consent={'status':'authorized_by_existing_project_scope','provider':'Zhipu BigModel','recorded_at':p.now(),'scope':'Only editorial source-checked public preference summaries; historical raw source and chat logs are not transmitted.','authorization_basis':['那先帮我把所有的可用资料上传','目前还没有奶绿喜欢的歌手，明星，和作品里的角色等之类的，再去检索一遍','上限100块'],'item_count':len(active),'text_fields_transmitted':['text'],'text_set_sha256':fingerprint,'private_chats_transmitted':False,'source_audio_transmitted':False}
 p.save(CONSENT,consent);client=p.Embeddings(purpose='preference')
 vectors=[]
 for i in range(0,len(active),32):vectors+=client.fetch([x['text'] for x in active[i:i+32]])
 folder=p.ROOT/'data/preferences/semantic'/fingerprint[:16];folder.mkdir(parents=True,exist_ok=True)
 with (folder/'vectors.f32').open('wb') as stream:
  for vec in vectors:
   norm=math.sqrt(sum(x*x for x in vec));stream.write(array.array('f',(x/norm for x in vec)).tobytes())
 cat={'metadata':{'embedding_model':p.MODEL,'dimensions':p.DIM,'endpoint':p.ENDPOINT,'item_count':len(active),'text_set_sha256':fingerprint,'created_at':p.now()},'items':[{'id':x['id'],'text':x['text'],'text_sha256':p.digest(x['text']),'category':'facts','kind':'preference'} for x in active],'binary_sha256':hashlib.sha256((folder/'vectors.f32').read_bytes()).hexdigest(),'binary_endian':sys.byteorder}
 p.save(str((folder/'catalog.json').relative_to(p.ROOT)),cat);consent.update(status='completed',completed_at=p.now());p.save(CONSENT,consent)
 p.save(MANIFEST,{'folder':str(folder.relative_to(p.ROOT)).replace('\\','/'),'item_count':len(active),'text_set_sha256':fingerprint})
 assert len(load_semantic_index()['by_id'])==len(active)
 print(json.dumps({'preference_vectors_ready':len(active)}),flush=True)
if __name__=='__main__':build_vectors()
