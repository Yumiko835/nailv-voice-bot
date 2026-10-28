
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import collections,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(project_path(''));sys.path.insert(0,str(ROOT/'tools'));import publish_nailv_library as p
inputs=p.load('work/style-v3-20261024/selection-input.json')['items'];by={x['id']:x for x in inputs}
kept=[];dropped=[];seen=set()
ACTS={'calling','kiss','affection','comfort','blessing','celebrate','banter','clarify','refusal','opinion','daily','other'}
for file in sorted((ROOT/'work/style-v3-20261024/selection-results').glob('*.json')):
    obj=json.loads(file.read_text(encoding='utf-8'))
    for choice in obj['content'].get('items',[]):
        source=by.get(choice.get('id'));reason=''
        if not source:reason='unknown input ID'
        elif not choice.get('take'):reason='model skipped'
        else:
            lo,hi=choice.get('lo'),choice.get('hi');lines=source['reply_lines']
            if type(lo)!=int or type(hi)!=int or not 0<=lo<=hi<len(lines) or hi-lo>=8:reason='invalid span'
            else:
                quote='\n'.join(lines[lo:hi+1]);flat=''.join(quote.split())
                if not 1<=len(flat)<=160:reason='excessive or empty quote'
                elif not any(quote in ref['quote'] for ref in source['source_refs']):reason='not a continuous source span'
                elif re.search(r'谢谢.{0,30}(?:SC|舰长|总督|礼物)|(?:[A-Za-z]{4,}\s*){3}',quote,re.I):reason='SC-reading or lyric contamination'
                elif re.search(r'(?:那个|但是|因为|就是我|我我我|然后我)$',flat):reason='unfinished ending'
                elif source['id'].startswith('raw-calling') and not re.fullmatch(r'(?:mua|木马|木啊|木嘛|么|哎|嗯|啵|亲|[\s，,。.…！!?？、])+',quote,re.I):reason='raw-calling attribution too uncertain; keep only unambiguous short sounds'
                elif flat in seen:reason='duplicate wording'
                else:
                    seen.add(flat);act=choice.get('act') if choice.get('act') in ACTS else 'other'
                    kept.append({'id':'style3-'+hashlib.sha256(source['id'].encode()).hexdigest()[:18],'source_item_id':source['id'],'context_paraphrase':source['user_context'],'reply_excerpt':quote,'reply_is_verbatim':True,'wording_note':str(choice.get('wording',''))[:160],'avoid':str(choice.get('avoid',''))[:160],'act':act,'source_request_tags':source.get('tags',[]),'specific_problem':bool(re.search('考试|面试|手术|生病|发热|加班|上班辛苦|难过|失恋|工作|医院|出差|飞行',source['user_context'])),'source_refs':source['source_refs'],'source_record_date':source['source_record_date'],'span_in_input_reply':[lo,hi],'source_review':'approved episode' if not source['id'].startswith('raw-calling') else 'ASR slice checked for continuous short response; audio not checked','style_review':'experimental source-backed style selection; user likeness judgment pending','audio_verified':False})
        if reason:dropped.append({'input_id':choice.get('id'),'reason':reason})
assert len(kept)>=150
p.save('style/v3/表达选段库.json',{'version':'lexical-v3','created_at':p.now(),'method':'Flash selection followed by exact continuous-source and ambiguity filters; no fabricated request/response pairs','input_items':len(inputs),'items':kept,'acts':dict(collections.Counter(x['act'] for x in kept)),'human_similarity_verdict':'pending actual user comparison'})
p.save('work/style-v3-20261024/style-selection-drops.json',{'items':dropped,'counts':dict(collections.Counter(x['reason'] for x in dropped))})
print(json.dumps({'selected':len(kept),'source_span_checks_passed':True,'acts':dict(collections.Counter(x['act'] for x in kept)),'dropped':len(dropped)},ensure_ascii=False))
