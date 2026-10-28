"""Supplemental approved-text vectors, isolated from the original accepted index."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import array,hashlib,json,math,sys
from pathlib import Path

CONSENT='review/智谱补充向量授权-20261024.json'
POINTER='data/self-supplement/semantic.json'

def rows():
    import publish_nailv_library as pub
    data=pub.load('data/self-supplement/items.json')
    result=[x for x in data['items'] if x.get('active_in_text_pilot') and not pub.expired(x)]
    if any(x.get('review') not in ('approved','editorial_source_checked','machine_source_checked') or not x.get('source_refs') for x in result):
        raise RuntimeError('Supplement contains an unaccepted or sourceless item')
    if len({x['id'] for x in result})!=len(result):raise RuntimeError('Duplicate supplement IDs')
    return sorted(result,key=lambda x:x['id'])

def text_set(items):
    import publish_nailv_library as pub
    return pub.digest(json.dumps([(x['id'],pub.digest(x['text'])) for x in items],ensure_ascii=False))

def load_index():
    import publish_nailv_library as pub
    if not (pub.ROOT/POINTER).exists():return None
    pointer=pub.load(POINTER);consent=pub.load(CONSENT)
    if consent.get('status')!='completed' or consent.get('provider')!='Zhipu BigModel':raise RuntimeError('Supplement embedding consent is incomplete')
    folder=(pub.ROOT/pointer['folder']).resolve()
    if not folder.is_relative_to((pub.ROOT/'data/self-supplement/semantic').resolve()):raise RuntimeError('Invalid supplement index path')
    catalog=json.loads((folder/'catalog.json').read_text(encoding='utf-8'));meta=catalog['metadata'];active=rows()
    expected=text_set(active)
    if meta['embedding_model']!=pub.MODEL or meta['dimensions']!=pub.DIM or meta['endpoint']!=pub.ENDPOINT or meta['text_set_sha256']!=expected or consent['text_set_sha256']!=expected:
        raise RuntimeError('Supplement index is stale or uses a different embedding model')
    if meta['item_count']!=len(active) or catalog['binary_endian']!=sys.byteorder:raise RuntimeError('Supplement index shape mismatch')
    if [(x['id'],x['text_sha256']) for x in catalog['items']]!=[(x['id'],pub.digest(x['text'])) for x in active]:raise RuntimeError('Supplement catalog text mismatch')
    binary=folder/'vectors.f32'
    if binary.stat().st_size!=len(active)*pub.DIM*4 or hashlib.sha256(binary.read_bytes()).hexdigest()!=catalog['binary_sha256']:raise RuntimeError('Supplement vector integrity mismatch')
    result={'catalog':catalog,'binary':binary,'by_id':{x['id']:x for x in active}}
    from nailv_relationship_knowledge import load_semantic_index
    relationship=load_semantic_index()
    if relationship:
        if set(relationship['by_id'])&(set(result['by_id'])|set(x['id'] for x in pub.items())):raise RuntimeError('Relationship IDs overlap the accepted library')
        relationship['label']='relationship_xingtong';result['additional_indexes']=[relationship]
    from nailv_preference_knowledge import load_semantic_index as load_preferences
    preference=load_preferences()
    if preference:
        occupied=set(result['by_id'])|{x['id'] for x in pub.items()}
        for extra in result.get('additional_indexes',[]):occupied.update(extra['by_id'])
        if occupied & set(preference['by_id']):raise RuntimeError('Preference IDs overlap the accepted library')
        result.setdefault('additional_indexes',[]).append(preference)
    from nailv_community_knowledge import load_semantic_index as load_community
    community=load_community()
    if community:
        occupied=set(result['by_id'])|{x['id'] for x in pub.items()}
        for extra in result.get('additional_indexes',[]):occupied.update(extra['by_id'])
        if occupied & set(community['by_id']):raise RuntimeError('Community IDs overlap the accepted library')
        result.setdefault('additional_indexes',[]).append(community)
    return result

def retrieve(q,top_k,category,loaded):
    import publish_nailv_library as pub
    if loaded is None:return []
    scored=[]
    with loaded['binary'].open('rb') as stream:
        for row in loaded['catalog']['items']:
            vector=array.array('f');vector.frombytes(stream.read(pub.DIM*4))
            if len(vector)!=pub.DIM:raise RuntimeError('Truncated supplement index')
            if category and row['category']!=category:continue
            scored.append((sum(a*b for a,b in zip(q,vector)),row))
    result=[]
    for score,row in sorted(scored,key=lambda x:(-x[0],x[1]['id']))[:top_k]:
        original=loaded['by_id'][row['id']]
        result.append({**original,'category':row['category'],'score':round(score,6),'text_sha256':row['text_sha256'],'evidence_check_required':True,'retrieval_index':loaded.get('label','self_supplement')})
    for additional in loaded.get('additional_indexes',[]):result+=retrieve(q,top_k,category,additional)
    return sorted(result,key=lambda x:(-x['score'],x['id']))[:top_k]

def build():
    import publish_nailv_library as pub
    import concurrent.futures
    consent=pub.load(CONSENT);active=rows();fingerprint=text_set(active)
    if consent.get('status') not in ('explicitly_authorized_by_user','completed') or consent.get('provider')!='Zhipu BigModel' or consent['text_set_sha256']!=fingerprint:
        raise RuntimeError('Explicit consent for the current supplement is required')
    if set(x['id'] for x in active)&set(x['id'] for x in pub.items()):raise RuntimeError('Original and supplemental IDs overlap')
    client=pub.Embeddings(purpose='supplement')
    batches=[active[i:i+32] for i in range(0,len(active),32)]
    done=0
    def run(batch):client.fetch([x['text'] for x in batch]);return len(batch)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        iterator=iter(batches)
        pending={pool.submit(run,b) for b in [next(iterator,None) for _ in range(4)] if b is not None}
        while pending:
            finished,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                done+=future.result()
                batch=next(iterator,None)
                if batch is not None:pending.add(pool.submit(run,batch))
            pub.save('work/supplement-embedding-progress.json',{'items_done':done,'items_total':len(active),'model':pub.MODEL,'dimensions':pub.DIM,'updated_at':pub.now()})
            if done%320<32:print(json.dumps({'stage':'supplement_embedding','items_done':done,'items_total':len(active)}),flush=True)
    folder=pub.ROOT/'data/self-supplement/semantic'/fingerprint[:16];folder.mkdir(parents=True,exist_ok=True)
    binary=folder/'vectors.f32.part';catalog=[]
    with binary.open('wb') as stream:
        for item in active:
            vec=client.cached(item['text']);pub.Embeddings.check(vec)
            norm=math.sqrt(sum(x*x for x in vec));stream.write(array.array('f',(x/norm for x in vec)).tobytes())
            category='corpus' if item['kind'] in ('story','opinion','lll_event','biography','experience') else 'facts'
            catalog.append({'id':item['id'],'text':item['text'],'text_sha256':pub.digest(item['text']),'category':category,'kind':item['kind']})
    binary.replace(folder/'vectors.f32')
    meta={'character_id':'new-milkgreen','embedding_model':pub.MODEL,'dimensions':pub.DIM,'endpoint':pub.ENDPOINT,'item_count':len(active),'created_at':pub.now(),'text_set_sha256':fingerprint,'consent_file':CONSENT,'source_file':'data/self-supplement/items.json','review_scope':'User-authorized active edition; source-check and human/audio review scope remain as recorded in each original item.'}
    pub.save(str((folder/'catalog.json').relative_to(pub.ROOT)),{'metadata':meta,'items':catalog,'binary_sha256':hashlib.sha256((folder/'vectors.f32').read_bytes()).hexdigest(),'binary_endian':sys.byteorder})
    consent.update(status='completed',completed_at=pub.now(),embedded_items=len(active));pub.save(CONSENT,consent)
    pub.save(POINTER,{'folder':str(folder.relative_to(pub.ROOT)).replace('\\','/'),'item_count':len(active),'text_set_sha256':fingerprint,'model':pub.MODEL,'dimensions':pub.DIM,'created_at':pub.now()})
    loaded=load_index();assert len(loaded['by_id'])==len(active)
    total=len(pub.items())+len(active)
    config=pub.load('project.json');config['models']['embeddings']['supplement_index']={'manifest':POINTER,'item_count':len(active),'total_semantic_items':total,'model':pub.MODEL,'dimensions':pub.DIM};pub.save('project.json',config)
    report={'completed_at':pub.now(),'newly_indexed_items':len(active),'original_index_items':len(pub.items()),'total_semantic_items':total,'sent_fields':['text'],'original_source_files_transmitted':False,'vectors_stored_locally':True,'embedding_model':pub.MODEL,'dimensions':pub.DIM,'manifest':POINTER,'text_set_sha256':fingerprint,'consent_file':CONSENT,'source_dates_and_attribution_retained':True,'budget_guard_retained':True,'supplement_inputs_and_vector_rows_match':True,'qq_changed':False,'voice_changed':False}
    pub.save('outputs/补充资料语义索引报告.json',report)
    print(json.dumps({'stage':'supplement_index_complete','newly_indexed_items':len(active),'total_semantic_items':total,'model':pub.MODEL,'dimensions':pub.DIM}),flush=True)

if __name__=='__main__':build()
