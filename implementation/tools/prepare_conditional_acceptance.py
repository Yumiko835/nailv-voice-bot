"""Record the user's edition-level acceptance subject to explicit consistency checks."""

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
import collections,copy,datetime,hashlib,json,re,shutil,sqlite3,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'));import publish_nailv_library as p
OUT=R/'review/conditional-acceptance-20261024'
def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def signature(x):return digest({k:x.get(k) for k in ['id','text','source_record_date','source_refs']})
def norm(s):return '\n'.join(x.strip() for x in s.strip().splitlines() if x.strip())
def canon(s):
    s=re.sub(r'^在\d{4}-\d\d-\d\d对应的录播中[，,]?','',s)
    s=re.sub('明前奶绿|在直播中|在本次直播中|自述|表示|提到|说过','',s)
    s=re.sub(r'^(?:她|其|我)','',s)
    return re.sub(r'[^a-z0-9\u3400-\u9fff]','',s.lower())
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'decision.json').exists():raise RuntimeError('Acceptance already prepared; no duplicate approval created.')
    snapshot=OUT/'before';snapshot.mkdir(exist_ok=True)
    mapping={'data/self-supplement/items.json':'active-items.json','data/self-supplement/library.sqlite3':'library.sqlite3','review/self-supplement-20261024/subtitle-pending.json':'candidate-items.json','outputs/人物资料补充核对.html':'review.html','outputs/人物资料补充报告.json':'report.json','outputs/人物资料补充说明.md':'notes.md','project.json':'project.json','tools/build_self_supplement.py':'build_self_supplement.py'}
    hashes={}
    for rel,name in mapping.items():
        shutil.copy2(R/rel,snapshot/name);hashes[rel]=hashlib.sha256((R/rel).read_bytes()).hexdigest()
    raw=p.load('review/self-supplement-20261024/subtitle-pending.json')['items'];base=p.load('data/self-supplement/items.json')['items']
    old=p.load('persona/facts.json')['items']+p.load('persona/corpus.json')['items']+base
    assert len(raw)==2429 and len(base)==790
    census={x['id']:x for x in p.load('work/conditional-acceptance-20261024/census.json')['pairs']}
    exact={canon(x['text']):x['id'] for x in old};byid={x['id']:x for x in old}
    blocked={
      'fact-self-6b76bdb650f6afdd3ad5':('source_attribution','原文前后明确是感谢观众SC、读其论文致谢；不是主播本人的论文经历。'),
      'pending-extra-d86560a31eeb23738fc4':('core_conflict','“不是19岁、16岁”与用户再次确认的永远19岁冲突。'),
      'pending-extra-74073e5f97856468d95a':('core_conflict','6月19日录播的“明天生日”不能归为本人生日，与3月4日冲突。'),
      'pending-extra-a2f377395b87e48d5e3f':('core_conflict','“我已经23了”不能作为固定角色年龄，与永远19岁冲突。'),
      'pending-extra-87cac0155e1eccb97733':('core_conflict','3月14日生日与用户确认的3月4日冲突；原文也是观众给主播留言的语境。'),
      'pending-extra-508de6cecd9dbcb9f081':('source_attribution','观众SC说自己ID的转写被误当主播21岁时取名，原文不支持这个年龄结论。'),
      'pending-extra-fa1627c1e14c4fe21b92':('core_conflict','4月5日录播中“今天19岁生日”是读观众留言，与主播3月4日生日冲突。'),
      'pending-extra-6219e65151b1921ebee2':('core_conflict','六一生日与3月4日冲突，原文是观众问六一能否开播的生日留言。'),
    }
    edits={
      'fact-self-b6ac717f0f5fdb742bbe':('明前奶绿说自己是“店长现在不在的拉普拉斯花店的代主理人”；仍是店员身份，不把她改成坚果店长。','纠正字幕断句，保留代主理语境，与固定店员/坚果店长设定一致。','lore','character_setting'),
      'fact-self-00b610da31d3548ff39b':('她回应“什么时候和露露结婚”时说“治标不治本”，是朋友间玩笑；不能据此认定现实婚姻或他人的性取向、家庭态度。','保留公开玩笑，不将玩笑扩成第三方家庭和婚恋事实。','joke','peer_relation'),
      'pending-extra-7a62b5a6c8aa1d619843':('直播里读过观众“19岁带俩娃、38岁四娃、八岐大蛇”的夸张玩笑。这不是她有孩子的事实。','明确读弹幕与本人经历的区别，保留永远19岁的玩笑语境。','joke','character_setting'),
      'pending-extra-db0258b2194db5c06142':('她谈到认识不少做模特的朋友，其中有人转行带货、直播或结婚；同段“美术生、落榜”的说法属于调侃，不作为学历事实。','保留与旧资料一致的朋友经历，将玩笑从学历事实中分开。','public_life','biography'),
      'pending-extra-c08e071537464ffafa8b':('她回忆以前读过的投稿，包括大学期间爱而不得的小故事，以及念到结尾才发现讲投胎的意识流故事；不是她自己在大学写过这些故事。','原文“念到最后、终于看懂”表明是在回忆读投稿，不是本人大学创作经历。','public_life','streaming_milestone'),
    }
    manual_merges={'fact-self-e9e3d7449e37fd5a0ea9':'fact-self-lll-schedule','fact-self-9c217879c5925e2991af':'fact-self-lll-schedule','fact-self-6e655fd5bd1c62ed99c6':'fact-self-lll-bw2024','fact-self-e5b0616203d4529057b1':'fact-self-lll-dice','fact-self-3d5700d7a305ea1dbe9b':'fact-self-nigreen-world','pending-extra-423efe0790bcaa6af9a1':'fact-self-age19'}
    db=sqlite3.connect('file:'+str(R/'data/raw-index/library.sqlite3').replace('\\','/')+'?mode=ro',uri=True)
    decisions=[];accepted=[];merged=[];held=[];seen={}
    for row in raw:
        x=copy.deepcopy(row);rid=x['id'];disposition='accepted';reason='用户认可本批候选；与既有材料的近邻及固定设定对照未发现显式冲突。';target=None
        valid=True
        for ref in x['source_refs']:
            rows=db.execute('SELECT text FROM cues WHERE source_id=? AND start_ms>=? AND end_ms<=? ORDER BY ordinal',(ref['source_id'],round(ref['start_seconds']*1000)-1,round(ref['end_seconds']*1000)+1)).fetchall()
            if norm(ref['quote']) not in norm('\n'.join(y[0] for y in rows)):valid=False
        if not valid:disposition='held';reason='证据不能与原字幕连续时间段逐字对应。'
        if rid in blocked:disposition='held';reason=blocked[rid][1];x['conflict_type']=blocked[rid][0]
        original_text=x['text']
        if rid in edits:
            x['text'],note,x['realm'],x['kind']=edits[rid];x['editorial_change']={'original_text':original_text,'reason':note}
        key=canon(x['text'])
        if disposition!='held':
            target=manual_merges.get(rid) or exact.get(key) or seen.get(key)
            if target:disposition='merged';reason='相同信息已在库中；保留此次原文为补充证据。'
        if disposition=='accepted':
            if rid.startswith('pending-extra-'):x['id']='fact-self-extra-'+rid.removeprefix('pending-extra-')
            x['candidate_id']=rid;x['review']='approved';x['human_review']=True;x['human_review_scope']='user_accepted_whole_candidate_edition_subject_to_conflict_filter';x['audio_verified']=False
            x['active_in_text_pilot']=True;x['core']=False;x['acceptance_id']='conditional-candidate-acceptance-20261024';x['acceptance_method']='user_edition_acceptance_after_local_consistency_filter';x['attribution']='user_accepted_candidate_not_original_audio_verified'
            if x.get('time_scope')=='stable':x['time_scope']='historical'
            if x.get('time_scope') not in ['historical','uncertain','planned']:x['time_scope']='uncertain'
            if re.search(r'打算|计划|预告|下周|明天|到时候',x['text']) and not re.search(r'已经|曾经|后来',x['text']):x['time_scope']='planned'
            if not x.get('realm'):x['realm']='joke' if re.search(r'玩笑|调侃|夸张|老婆|老公|八岐大蛇',x['text']) else 'public_life'
            x['topics']=list(x.get('topics',[]))
            for topic,pattern in {'坚果':r'坚果|店长|果仁','LLL':r'LLL|lll|三人组','莉莉丝':r'莉莉丝|发卡','露露':r'露露|lulu|Lulu|るる','花店':r'花店|拉普拉斯|LAPLACE','奶黑':r'奶黑|奶白|新衣|形象','直播经历':r'出道|周年|休播|复播|首播'}.items():
                if re.search(pattern,x['text']+' '+' '.join(x.get('entities',[]))) and topic not in x['topics']:x['topics'].append(topic)
            if '莉莉丝' in x['topics'] and re.search(r'偷[星心]|漫画|十月|四月',x['text']):x['topics'].remove('莉莉丝');x['entity_disambiguation']='漫画角色莉莉丝，与主播同行夜王莉莉丝不同。'
            if x.get('event_date'):
                try:
                    yr,mo,dy=map(int,x['event_date'].split('-'));literal=any(re.search(str(yr)+r'\D{0,3}'+str(mo)+r'\D{1,3}'+str(dy)+r'(?:日|号|\D|$)',ref['quote']) for ref in x['source_refs'])
                except (TypeError,ValueError):literal=False
                if not literal:x['event_date']=None;x['inferred_event_date_removed']=True
            x['text']=f"在{x['source_record_date'][:10]}对应录播中，"+x['text']
            x['review_note']='用户认可本批候选；经本地固定设定、时间与相近旧条目核对后纳入。未声称逐条原声听校。'
            accepted.append(x);seen[key]=x['id']
        else:
            x['active_in_text_pilot']=False;x['review']='conflict_held' if disposition=='held' else 'merged_evidence';x['acceptance_disposition']=disposition;x['decision_reason']=reason
            if target:x['merged_into']=target
            (held if disposition=='held' else merged).append(x)
        decisions.append({'candidate_id':rid,'input_signature':signature(row),'decision':disposition,'reason':reason,'published_id':x['id'] if disposition=='accepted' else None,'merged_into':target,'matched_existing_ids':[y['id'] for y in census[rid]['nearest']],'editorial_change':x.get('editorial_change')})
    db.close();assert len(decisions)==2429
    record={'id':'conditional-candidate-acceptance-20261024','recorded_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'user_quote':'待核对的我查看都没啥问题，如果跟之前的内容不冲突都可以加进去','core_confirmation_quote':'3月4日、永远19岁是对的','scope':'Edition-level acceptance of the 2,429 candidates shown in the review page, subject to consistency and source-attribution exclusions; not individual original-audio verification.','candidate_file_sha256':hashes['review/self-supplement-20261024/subtitle-pending.json'],'baseline_files_sha256':hashes,'compared_existing_items':len(old),'counts':{'input_candidates':len(raw),'accepted':len(accepted),'merged':len(merged),'held':len(held),'editorially_clarified':sum(bool(x.get('editorial_change')) for x in accepted)},'decisions':decisions,'method':'All candidates locally compared with existing accepted+supplement texts using lexical nearest matches, pinned identity rules, source-span validation and editorial inspection of flagged items; different historical dates are not automatically contradictions. No claim of a complete formal semantic proof.'}
    p.save('review/conditional-acceptance-20261024/accepted-items.json',{'items':accepted});p.save('review/conditional-acceptance-20261024/merged-items.json',{'items':merged});p.save('review/conditional-acceptance-20261024/held-items.json',{'items':held});p.save('review/conditional-acceptance-20261024/decision.json',record)
    print(json.dumps(record['counts'],ensure_ascii=False))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
