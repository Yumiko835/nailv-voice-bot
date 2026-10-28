"""User-approved edition, bounded Zhipu embeddings and evidence-only semantic retrieval."""
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
import argparse, array, collections, concurrent.futures, hashlib, json, math, os, shutil, sqlite3, sys, threading, time, urllib.request, uuid
from datetime import datetime, timezone, timedelta
from contextlib import closing
from pathlib import Path

ROOT=Path(project_path(''))
KEY_FILE=Path(secret_path("ZHIPU_API_KEY_FILE"))
ENDPOINT='https://open.bigmodel.cn/api/paas/v4/embeddings'
MODEL='embedding-3'
DIM=2048
# Live queries share the existing text-pilot stop; bulk indexing keeps its own guard.
import nailv_call_limits as call_limits
LIVE_STOP_CNY=call_limits.authorized_total()-.01
PRICE=.5
PRICING='https://docs.bigmodel.cn/cn/guide/models/embedding/embedding-3'


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def load(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8-sig'))
def save(rel,data):
    target=ROOT/rel;target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.part');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(target)


def expired(item):
    value=item.get('valid_until')
    if not value:return False
    when=datetime.fromisoformat(value.replace('Z','+00:00'))
    if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
    return when<datetime.now(timezone.utc)


def approve():
    marker=ROOT/'review/全量版用户认可.json'
    if marker.exists():return load('review/全量版用户认可.json')
    assert load('outputs/全量交付核验.json')['coverage']['all_input_processed']
    rels=['project.json','persona/identity.md','persona/facts.json','persona/corpus.json','persona/behaviors.json','persona/behavior-episodes.json','outputs/资料库制作报告.json','outputs/全量交付核验.json','outputs/先核对这些资料.html','outputs/本次补全新增资料.html','资料库使用说明.md']
    stamp=now().replace(':','-');snapshot=Path('review/versions')/('full-before-acceptance-'+stamp)
    hashes={}
    for rel in rels:
        src=ROOT/rel;dst=ROOT/snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        hashes[rel]=hashlib.sha256(src.read_bytes()).hexdigest()
    accepted_ids={};review_id='full-edition-user-acceptance-'+stamp
    for category in ['facts','corpus','behaviors','behavior-episodes']:
        data=load('persona/'+category+'.json');accepted_ids[category]=[]
        for item in data['items']:
            assert item['review']=='draft'
            assert category=='behaviors' or item['machine_review']['verdict']=='keep'
            item.update(review='approved',acceptance_id=review_id,acceptance_method='user_accepted_full_retained_edition',audio_verified=False)
            for sample in item.get('samples',[]):sample.update(review='approved',acceptance_id=review_id,audio_verified=False)
            accepted_ids[category].append(item['id'])
        save('persona/'+category+'.json',data)
    record={'id':review_id,'recorded_at':now(),'user_quote':'看完了，全部没问题','scope':'User acceptance of the retained full edition after reviewing the library; no claim that every recording was individually listened to.','accepted_ids':accepted_ids,'accepted_identity':True,'excluded_held_count':1798,'excluded_rejected_count':71,'excluded_raw_asr':True,'audio_verification':'not_performed','snapshot':str(snapshot),'before_sha256':hashes}
    text=(ROOT/'persona/identity.md').read_text(encoding='utf-8')
    text=text.replace('本文件依据本批录播字幕归纳。先前部分版已获得用户整体认可，反馈单独存档；全量补充后的新内容及新归纳仍为待核对候选，未逐条回听确认音源。','本全量版的人物骨架和保留资料已获用户认可，反馈及版本快照独立保存。认可方式为整版资料验收；没有逐条回听确认全部录音音源。')
    text=text.replace('## 跨录播出现的候选互动倾向','## 跨录播出现的互动倾向')
    text=text.replace('候选事实都保留来源日期。','人物事实都保留来源日期。')
    text=text.replace('ASR原文保留可能的错字，正式使用前核对音源与上下文。','ASR原文保留可能的错字；归属不明、争议和已排除内容单独存放。没有证据时不补写事实。')
    text=text.replace('人工通过条目为0；QQ未接入；语义向量索引尚未发布。全文关键词检索仅用于研究和核对。','全量保留版已获用户认可；经历与观点、事实与偏好进入正式检索材料。互动示范按情境使用。QQ未接入；语义索引的实际生成状态见制作报告。原始全文仍是未逐条核实的字幕。')
    (ROOT/'persona/identity.md').write_text(text,encoding='utf-8')
    config=load('project.json');config['phase']='approved-edition-building-index'
    config['review'].update(identity='approved',edition_acceptance='review/全量版用户认可.json',acceptance_method='user_accepted_full_retained_edition',audio_verification='not_performed',character_similarity='text_material_accepted_live_chat_not_evaluated')
    config['models']['embeddings'].update(provider='Zhipu',model=MODEL,base_url=ENDPOINT.rsplit('/',1)[0],dimensions=DIM,version='provider does not expose a pinned embedding revision')
    save('project.json',config);save('review/全量版用户认可.json',record)
    print(json.dumps({'stage':'edition_accepted','counts':{k:len(v) for k,v in accepted_ids.items()},'held_and_rejected_unchanged':True},ensure_ascii=False),flush=True)
    return record


def items():
    result=[]
    for category in ['facts','corpus']:
        for item in load('persona/'+category+'.json')['items']:
            if item['review']=='approved' and not expired(item):result.append({**item,'retrieval_category':category})
    return sorted(result,key=lambda x:x['id'])


class Embeddings:
    """Unknown billed failures keep their reservation. No automatic retries."""
    def __init__(self,purpose='index'):
        if purpose not in ('index','query','supplement','relationship','preference','community'):raise ValueError('Unknown embedding purpose')
        if purpose=='supplement':
            from nailv_supplement_vectors import CONSENT,rows,text_set
            extra=load(CONSENT)
            if extra.get('status') not in ('explicitly_authorized_by_user','completed') or extra.get('provider')!='Zhipu BigModel' or extra.get('text_set_sha256')!=text_set(rows()):raise RuntimeError('Supplement text transmission is not authorized')
        if purpose=='relationship':
            from nailv_relationship_knowledge import CONSENT,rows,text_set
            extra=load(CONSENT)
            if extra.get('status') not in ('authorized_by_existing_project_scope','completed') or extra.get('text_set_sha256')!=text_set(rows()):raise RuntimeError('Relationship embedding scope is not authorized')
        if purpose=='preference':
            from nailv_preference_knowledge import CONSENT,rows,text_set
            extra=load(CONSENT)
            if extra.get('status') not in ('authorized_by_existing_project_scope','completed') or extra.get('text_set_sha256')!=text_set(rows()):raise RuntimeError('Preference embedding scope is not authorized')
        if purpose=='community':
            from nailv_community_knowledge import CONSENT,rows,text_set
            extra=load(CONSENT)
            if extra.get('status') not in ('authorized_by_existing_project_scope','completed') or extra.get('text_set_sha256')!=text_set(rows()):raise RuntimeError('Community embedding scope is not authorized')
        self.purpose=purpose
        self.stop_cny=LIVE_STOP_CNY if purpose in ('query','supplement','relationship','preference','community') else 49.
        consent=load('review/待发送智谱的向量任务.json')
        if consent.get('status') not in ('explicitly_authorized_by_user','completed') or consent.get('transmission_consent',{}).get('provider')!='Zhipu BigModel':raise RuntimeError('Explicit consent for Zhipu text transmission is required')
        self.lock=threading.Lock();self.path=ROOT/'work/embedding-usage.jsonl';self.events={}
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                row=json.loads(line);self.events[row['request_id']]=row
        sys.path.insert(0,str(ROOT/'tools'))
        from extract_nailv_library import Budget
        self.previous=Budget().report()
        self.previous['conservative_upper_cny']+=call_limits.analysis_spent()
        self.key=(os.environ.get('EMBED_API_KEY') or KEY_FILE.read_text(encoding='utf-8-sig')).strip()
        if not self.key:raise RuntimeError('Existing embedding key is empty')
        self.cache=ROOT/'cache/embeddings.sqlite3';self.cache.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.cache)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors(cache_key TEXT PRIMARY KEY,model TEXT,dimensions INTEGER,text_sha256 TEXT,vector BLOB)')
    def account(self,row):return row.get('cost_cny',row['reserved_cny'])
    def report(self):
        with self.lock:
            cost=sum(self.account(x) for x in self.events.values())
            return {'embedding_model':MODEL,'dimensions':DIM,'price_cny_per_million_input_tokens':PRICE,'pricing_url':PRICING,'pricing_checked_date':'2026-10-23','embedding_requests':len(self.events),'embedding_unsettled_requests':sum(x['state']!='completed' for x in self.events.values()),'embedding_input_tokens':sum(x.get('input_tokens',0) for x in self.events.values()),'embedding_accounted_cny':round(cost,6),'deepseek_conservative_cny':self.previous['conservative_upper_cny'],'combined_conservative_cny':round(cost+self.previous['conservative_upper_cny'],6),'authorized_cny':call_limits.authorized_total(),'internal_stop_cny':self.stop_cny,'note':'Actual provider invoice may be lower. Unknown embedding usage retains its full input reservation.'}
    def event(self,row):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        self.events[row['request_id']]=row
    def key_for(self,text):return digest(json.dumps([ENDPOINT,MODEL,DIM,text],ensure_ascii=False))
    def cached(self,text):
        with closing(sqlite3.connect(self.cache,timeout=30)) as db,db:row=db.execute('SELECT vector FROM vectors WHERE cache_key=?',(self.key_for(text),)).fetchone()
        if row is None:return None
        vector=array.array('f');vector.frombytes(row[0]);self.check(vector);return vector
    @staticmethod
    def check(vector):
        if len(vector)!=DIM or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in vector) or not any(vector):raise ValueError('Invalid embedding dimensions, values or zero norm')
    def fetch(self,texts):
        if not texts:return []
        if len(texts)>64 or any(len(t.encode('utf-8'))+16>3072 for t in texts):raise ValueError('Embedding input bound exceeded')
        output=[self.cached(t) for t in texts];indexes=[i for i,v in enumerate(output) if v is None]
        if not indexes:return output
        fresh=[texts[i] for i in indexes];bound=sum(len(t.encode('utf-8'))+16 for t in fresh)+1024;reserved=bound*PRICE/1e6
        with self.lock:
            current=sum(self.account(x) for x in self.events.values())
            if self.previous['conservative_upper_cny']+current+reserved>self.stop_cny or current+reserved>1:raise RuntimeError('Embedding budget reached; no request sent')
            rid=uuid.uuid4().hex;event={'request_id':rid,'state':'reserved','created_at':now(),'input_bound_tokens':bound,'reserved_cny':reserved,'input_count':len(fresh),'model':MODEL,'dimensions':DIM};self.event(event)
        payload={'model':MODEL,'dimensions':DIM,'input':fresh}
        req=urllib.request.Request(ENDPOINT,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key})
        try:
            with urllib.request.urlopen(req,timeout=20 if self.purpose=='query' else 90) as response:data=json.load(response)
            if data.get('model',MODEL)!=MODEL:raise RuntimeError('Provider returned a different embedding model')
            usage=data.get('usage',{});tokens=usage.get('total_tokens',usage.get('prompt_tokens'))
            if not isinstance(tokens,int) or tokens<0 or tokens>bound:raise RuntimeError('Embedding usage missing or exceeds reservation')
            with self.lock:self.event({**event,'state':'completed','settled_at':now(),'input_tokens':tokens,'cost_cny':tokens*PRICE/1e6,'returned_model':data.get('model',MODEL)})
            rows=data.get('data',[])
            if len(rows)!=len(fresh) or {x.get('index') for x in rows}!=set(range(len(fresh))):raise RuntimeError('Missing or duplicate embedding response rows')
            vectors=[]
            for row in sorted(rows,key=lambda x:x['index']):
                vec=row['embedding'];self.check(vec);vectors.append(array.array('f',vec))
            with closing(sqlite3.connect(self.cache,timeout=30)) as db,db:
                db.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?,?)',[(self.key_for(t),MODEL,DIM,digest(t),vec.tobytes()) for t,vec in zip(fresh,vectors)])
            for i,vec in zip(indexes,vectors):output[i]=vec
            return output
        except Exception as exc:
            # Do not log headers, keys or response bodies. Reservation stays billed if usage is unknown.
            raise RuntimeError('Embedding request '+rid+' failed: '+type(exc).__name__) from None


def build():
    approval=approve();rows=items();client=Embeddings();batches=[];batch=[];size=0
    for row in rows:
        if batch and (len(batch)>=32 or size+len(row['text'].encode())>6000):batches.append(batch);batch=[];size=0
        batch.append(row);size+=len(row['text'].encode())
    if batch:batches.append(batch)
    started=time.monotonic();done=0
    print(json.dumps({'stage':'embedding_start','approved_text_items':len(rows),'batches':len(batches),'budget':client.report()},ensure_ascii=False),flush=True)
    # Verify provider/model/dimensions with one real batch before parallelizing the remainder.
    client.fetch([r['text'] for r in batches[0]]);done+=len(batches[0])
    def run(b):client.fetch([r['text'] for r in b]);return len(b)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        iterator=iter(batches[1:]);pending={pool.submit(run,b) for b in [next(iterator,None) for _ in range(4)] if b is not None}
        while pending:
            finished,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                done+=future.result();b=next(iterator,None)
                if b is not None:pending.add(pool.submit(run,b))
            progress={'stage':'embedding','items_done':done,'items_total':len(rows),'seconds':round(time.monotonic()-started),'budget':client.report()}
            save('work/embedding-progress.json',progress)
            if done%320<32:print(json.dumps(progress,ensure_ascii=False),flush=True)
    folder=ROOT/'data/index';folder.mkdir(parents=True,exist_ok=True)
    meta={'embedding_model':MODEL,'provider':'Zhipu','endpoint':ENDPOINT,'api_revision':'v4; model revision not exposed by provider','dimensions':DIM,'created_at':now(),'character_id':'new-milkgreen','acceptance_id':approval['id'],'item_count':len(rows),'indexed_categories':['facts','corpus'],'text_set_sha256':digest(json.dumps([(r['id'],digest(r['text'])) for r in rows],ensure_ascii=False)),'vector_precision':'float32 cache; JSON rounded to 9 decimal places','raw_asr_included':False,'held_and_rejected_included':False,'source_dates_are_historical':True}
    temp=folder/'index.json.part';binary=folder/'vectors.f32.part';catalog=[]
    with temp.open('w',encoding='utf-8') as f,binary.open('wb') as bf:
        f.write('{"metadata":'+json.dumps(meta,ensure_ascii=False)+',"items":[')
        for n,row in enumerate(rows):
            vector=client.cached(row['text']);assert vector is not None
            norm=math.sqrt(sum(x*x for x in vector));unit=array.array('f',(x/norm for x in vector));bf.write(unit.tobytes())
            entry={'id':row['id'],'text':row['text'],'text_sha256':digest(row['text']),'category':row['retrieval_category'],'kind':row['kind'],'vector':[round(float(x),9) for x in vector]}
            if n:f.write(',')
            json.dump(entry,f,ensure_ascii=False,separators=(',',':'))
            catalog.append({k:v for k,v in entry.items() if k!='vector'})
        f.write(']}\n')
    temp.replace(folder/'index.json');binary.replace(folder/'vectors.f32')
    save('data/index/catalog.json',{'metadata':meta,'items':catalog,'binary_sha256':hashlib.sha256((folder/'vectors.f32').read_bytes()).hexdigest(),'binary_endian':sys.byteorder})
    config=load('project.json');config['features']['retrieval']=True;config['phase']='approved-library-indexed';save('project.json',config)
    report={'created_at':now(),'items':len(rows),'fact_items':sum(r['retrieval_category']=='facts' for r in rows),'corpus_items':sum(r['retrieval_category']=='corpus' for r in rows),'dimensions':DIM,'embedding_model':MODEL,'index_bytes':(folder/'index.json').stat().st_size,'binary_bytes':(folder/'vectors.f32').stat().st_size,'seconds':round(time.monotonic()-started),'budget':client.report(),'text_hash_and_approval_guard':True,'semantic_candidates_need_evidence_check':True,'qq_deployed':False}
    save('outputs/正式语义索引报告.json',report);save('outputs/总费用与预算.json',client.report())
    print(json.dumps({'stage':'embedding_complete','report':report},ensure_ascii=False),flush=True)


def query(text,top_k=8,category=None):
    cat=load('data/index/catalog.json');meta=cat['metadata']
    current=items();expected=digest(json.dumps([(r['id'],digest(r['text'])) for r in current],ensure_ascii=False))
    if meta['embedding_model']!=MODEL or meta['dimensions']!=DIM or expected!=meta['text_set_sha256']:raise RuntimeError('Index is stale; rebuild before retrieval')
    if cat['binary_endian']!=sys.byteorder:raise RuntimeError('Binary byte order differs; rebuild locally')
    from nailv_supplement_vectors import load_index,retrieve
    extra_index=load_index()
    if extra_index and set(extra_index['by_id'])&set(r['id'] for r in current):raise RuntimeError('Semantic index IDs overlap')
    client=Embeddings(purpose='query');q=client.fetch([text])[0];norm=math.sqrt(sum(v*v for v in q));q=[x/norm for x in q]
    blob=ROOT/'data/index/vectors.f32'
    if hashlib.sha256(blob.read_bytes()).hexdigest()!=cat['binary_sha256']:raise RuntimeError('Vector binary hash mismatch')
    scored=[]
    with blob.open('rb') as f:
        for row in cat['items']:
            v=array.array('f');v.frombytes(f.read(DIM*4))
            if len(v)!=DIM:raise RuntimeError('Truncated binary index')
            if category and row['category']!=category:continue
            score=sum(a*b for a,b in zip(v,q));scored.append((score,row))
        if f.read(1):raise RuntimeError('Unexpected binary index tail')
    by_id={r['id']:r for r in current};out=[]
    for score,row in sorted(scored,key=lambda r:(-r[0],r[1]['id']))[:top_k]:
        original=by_id[row['id']]
        out.append({**row,'score':round(score,6),'source_refs':original['source_refs'],'time_scope':original['time_scope'],'source_record_date':original['source_record_date'],'evidence_check_required':True})
    out=sorted(out+retrieve(q,top_k,category,extra_index),key=lambda x:(-x['score'],x['id']))[:top_k]
    save('outputs/总费用与预算.json',client.report())
    return {'query':text,'retrieval_only':True,'automatic_factual_answer':False,'historical_material_not_current_state':True,'results':out,'budget':client.report()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['approve','build','query']);parser.add_argument('--query');parser.add_argument('--top-k',type=int,default=8);parser.add_argument('--category',choices=['facts','corpus']);args=parser.parse_args()
    if args.action=='approve':approve()
    elif args.action=='build':build()
    else:
        if not args.query:parser.error('--query required')
        print(json.dumps(query(args.query,min(max(args.top_k,1),20),args.category),ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
