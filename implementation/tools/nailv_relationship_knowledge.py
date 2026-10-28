"""Source-limited relationship facts with alias recall and a separate small vector index."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import array,hashlib,json,math,re,sys
from pathlib import Path
ROOT=Path(project_path(''))
ITEMS='data/relationships-xingtong/items.json';MANIFEST='data/relationships-xingtong/semantic.json';CONSENT='review/星瞳补充向量授权-20261024.json'
def rows():return json.loads((ROOT/ITEMS).read_text(encoding='utf-8'))['items']
def text_set(items):
    import publish_nailv_library as p
    return p.digest(json.dumps([(x['id'],p.digest(x['text'])) for x in sorted(items,key=lambda x:x['id'])],ensure_ascii=False))
def retrieve(question,history=None,limit=4):
    import nailv_self_knowledge as sk
    expanded,topics=sk.expand(question,history)
    if '星瞳' not in topics and not re.search('星瞳|星彤|欣桐|绿瞳|绿同|瞳姐',question):return []
    priorities=['distance','social-effort']
    if re.search('绝不认输|宣战|断章|切片|剪辑',question):priorities=['bad-edit','distance','dont-brigade']
    elif re.search('和好|复合|昵称|ID',question,re.I):priorities=['nickname','distance','cp-imagination']
    elif re.search('卡黄|二选一',question):priorities=['cp-choice','cp-imagination','distance']
    elif re.search('分手|恋爱|谈过|结婚|情侣|CP|cp|磕|炒|绿瞳',question):priorities=['cp-imagination','cp-headache','distance','cp-fire']
    elif re.search('联动|认识|联系|私聊',question):priorities=['social-effort','past-contact','distance']
    elif re.search('仇|讨厌|生气|敌|闹掰|不和',question):priorities=['distance','dont-brigade','dont-cue']
    elif re.search('唱|歌',question):priorities=['song','bad-edit','distance']
    elif re.search('BW|展台|展会',question,re.I):priorities=['bw','distance']
    lookup={x['id'].removeprefix('fact-relation-xingtong-'):x for x in rows()}
    return [lookup[x] for x in priorities if x in lookup][:limit]

def load_semantic_index():
    import publish_nailv_library as p
    if not (p.ROOT/MANIFEST).exists():return None
    data=json.loads((p.ROOT/ITEMS).read_text(encoding='utf-8'))['items'];consent=p.load(CONSENT)
    meta=p.load(MANIFEST);folder=(p.ROOT/meta['folder']).resolve()
    if not folder.is_relative_to((p.ROOT/'data/relationships-xingtong/semantic').resolve()):raise RuntimeError('Invalid relationship index path')
    catalog=json.loads((folder/'catalog.json').read_text(encoding='utf-8'));m=catalog['metadata']
    if consent.get('status')!='completed' or m['text_set_sha256']!=text_set(data) or m['embedding_model']!=p.MODEL or m['dimensions']!=p.DIM or m['endpoint']!=p.ENDPOINT:raise RuntimeError('Relationship semantic index is stale')
    if catalog['binary_endian']!=sys.byteorder or [(x['id'],x['text_sha256']) for x in catalog['items']]!=[(x['id'],p.digest(x['text'])) for x in sorted(data,key=lambda x:x['id'])]:raise RuntimeError('Relationship catalog mismatch')
    binary=folder/'vectors.f32'
    if binary.stat().st_size!=len(data)*p.DIM*4 or hashlib.sha256(binary.read_bytes()).hexdigest()!=catalog['binary_sha256']:raise RuntimeError('Relationship vector integrity mismatch')
    return {'catalog':catalog,'binary':binary,'by_id':{x['id']:x for x in data}}

def build_vectors():
    import publish_nailv_library as p
    active=sorted(rows(),key=lambda x:x['id']);fingerprint=text_set(active)
    consent={'status':'authorized_by_existing_project_scope','provider':'Zhipu BigModel','recorded_at':p.now(),'scope':'13 primary-source-checked relationship texts added at user request, under earlier instruction to send all usable character material for embeddings.','authorization_basis':['那先帮我把所有的可用资料上传','奶绿与星瞳的关系目前还缺少，比如别人炒他俩cp的回应之类的','上限100块'],'item_count':len(active),'text_fields_transmitted':['text'],'text_set_sha256':fingerprint,'private_chats_transmitted':False,'source_audio_transmitted':False}
    p.save(CONSENT,consent);client=p.Embeddings(purpose='relationship');vectors=client.fetch([x['text'] for x in active])
    folder=p.ROOT/'data/relationships-xingtong/semantic'/fingerprint[:16];folder.mkdir(parents=True,exist_ok=True)
    with (folder/'vectors.f32').open('wb') as stream:
        for vec in vectors:
            norm=math.sqrt(sum(x*x for x in vec));stream.write(array.array('f',(x/norm for x in vec)).tobytes())
    cat={'metadata':{'embedding_model':p.MODEL,'dimensions':p.DIM,'endpoint':p.ENDPOINT,'item_count':len(active),'text_set_sha256':fingerprint,'created_at':p.now()},'items':[{'id':x['id'],'text':x['text'],'text_sha256':p.digest(x['text']),'category':'facts','kind':x['kind']} for x in active],'binary_sha256':hashlib.sha256((folder/'vectors.f32').read_bytes()).hexdigest(),'binary_endian':sys.byteorder}
    p.save(str((folder/'catalog.json').relative_to(p.ROOT)),cat);consent.update(status='completed',completed_at=p.now());p.save(CONSENT,consent)
    p.save(MANIFEST,{'folder':str(folder.relative_to(p.ROOT)).replace('\\','/'),'items':len(active),'text_set_sha256':fingerprint})
    assert len(load_semantic_index()['by_id'])==len(active)
    print(json.dumps({'relationship_vectors_ready':len(active)}),flush=True)

if __name__=='__main__':build_vectors()
