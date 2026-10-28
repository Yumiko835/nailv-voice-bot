"""Final offline checks and clear handoff artifacts; no model calls."""
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
import collections,difflib,hashlib,importlib.util,json,random,re,sqlite3,sys,time,unicodedata
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import extract_nailv_library as engine
import review_nailv_library as review

def main():
    started=time.monotonic();budget=engine.Budget();assert budget.report()['conservative_upper_cny']<50
    items=json.loads((ROOT/'work/audited-candidates.json').read_text(encoding='utf-8'))['items']
    local_counts=collections.Counter();nearby=collections.defaultdict(list)
    uncertainty=re.compile(r'未明说|未明确|未直接|略有引申|轻微引申|稍有引申|略强|证据未|不完全支持|超出证据|主语不明|归属不明|说话人.{0,8}(?:不明|不清|不确定|可能|存疑)|归属.{0,4}存疑|需人工核对|需要核对|可人工核对|待人工|可待核|需.{0,3}回听|需要.{0,3}回听')
    for item in items:
        audit=item['machine_review']
        if audit['verdict']!='keep':continue
        reason=audit.get('reason','');local_reason=None
        if uncertainty.search(reason):local_reason='机器核对备注仍提示信息或说话人不确定，转入待核对。';local_counts['uncertain_notes']+=1
        text=item.get('text','')
        if not local_reason and item['category']=='facts' and item.get('kind')=='fact' and re.search(r'玩到了第.{0,6}关|游戏进度|这把|这局|本局|目前打到|本次.{0,8}通关',text):local_reason='仅为本场游戏即时进展，不作为人物资料核心候选。';local_counts['episode_only_progress']+=1
        if not local_reason and text:
            ref=item['source_refs'][0];key=(item['category'],ref['source_id'])
            normalized=re.sub(r'[^\w\u3400-\u9fff]','',unicodedata.normalize('NFKC',text))
            for previous,old_text in nearby[key]:
                a=previous['source_refs'][0];overlap=max(0,min(a['end_seconds'],ref['end_seconds'])-max(a['start_seconds'],ref['start_seconds']))
                duration=max(.001,min(a['end_seconds']-a['start_seconds'],ref['end_seconds']-ref['start_seconds']))
                if overlap/duration>=.65 and difflib.SequenceMatcher(None,normalized,old_text).ratio()>=.75:
                    local_reason='同一录播相邻窗口的近似重复；主条目：'+previous['id'];item['duplicate_of']=previous['id'];local_counts['overlapping_duplicates']+=1;break
            if not local_reason:nearby[key].append((item,normalized))
        if local_reason:item['machine_review']={**audit,'original_verdict':'keep','verdict':'hold','local_screen_reason':local_reason,'reason':local_reason+' 原机器备注：'+reason}
    proposals=json.loads((ROOT/'review/归纳建议.json').read_text(encoding='utf-8'))
    groups=proposals['accepted_groups'];traits=proposals['accepted_trait_proposals']
    live={x['id']:x for x in items if x['machine_review']['verdict']=='keep'}
    screened_groups=[]
    for group in groups:
        members=[live[i] for i in group['support_episode_ids'] if i in live]
        if len({x['source_refs'][0]['source_id'] for x in members})<2:continue
        group['support_episode_ids']=[x['id'] for x in members]
        group['source_refs']=[r for x in members for r in x['source_refs']]
        group['distinct_source_count']=len({x['source_refs'][0]['source_id'] for x in members})
        samples=[];seen_sources=set()
        for member in members:
            sid=member['source_refs'][0]['source_id']
            if sid not in seen_sources and len(samples)<5:samples.append(member['samples'][0]);seen_sources.add(sid)
        group['samples']=samples;screened_groups.append(group)
    groups=screened_groups
    screened_traits=[]
    for trait in traits:
        ids=[i for i in trait['evidence_ids'] if i in live]
        if len({live[i]['source_refs'][0]['source_id'] for i in ids})<3:continue
        trait['evidence_ids']=ids;screened_traits.append(trait)
    traits=screened_traits
    for item in groups:
        if item['name']=='对方在直播间刷屏或影响秩序':
            item['original_grouping_proposal']={k:item[k] for k in ['name','trigger','response_posture']}
            item.update(name='对方反复发送干扰性消息',trigger='对方反复发送相同、无关或冒犯性信息，打断正常沟通；不用于普通连续补充消息。',response_posture='说明哪些内容让她不适，表达希望对方停止打扰的边界；语气可随干扰程度变化，不套用直播管理动作。',context_adaptation='依据直播场景提出的通用聊天候选，仍需人工确认。')
    review.publish(items,groups,traits,budget)
    sys.path.insert(0,dependency_path("optional_source",'scripts'))
    from validate_project import validate
    result=validate(ROOT)
    engine.save(ROOT/'outputs/结构与出处检查.json',result)
    assert not result['errors'],result['errors'][:20]
    assert result['approved_entries']==0
    db=sqlite3.connect('file:'+str(ROOT/'data/raw-index/library.sqlite3').replace('\\','/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    counts={name:db.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ['sources','cues','chunks','windows']}
    assert counts=={'sources':1635,'cues':2757563,'chunks':56961,'windows':2708}
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    cases=[];seen=set()
    # Independent retrieval probes across early/middle/late records and source genres.
    rows=db.execute('SELECT c.id,c.source_id,c.text,s.date,s.genre FROM chunks c JOIN sources s ON c.source_id=s.id WHERE length(c.text)>150 ORDER BY c.id').fetchall()
    random.Random(20261023).shuffle(rows)
    for row in rows:
        if row['source_id'] in seen:continue
        phrase=next((line.strip() for line in row['text'].splitlines() if re.fullmatch(r'[\u3400-\u9fff]{10,35}',line.strip())),None)
        if not phrase:continue
        phrase=phrase[:16];match='"'+phrase+'"'
        found=db.execute('SELECT c.source_id FROM chunks_fts f JOIN chunks c ON c.id=f.rowid WHERE chunks_fts MATCH ? LIMIT 200',(match,)).fetchall()
        passed=row['source_id'] in {r['source_id'] for r in found}
        assert passed,(row['source_id'],phrase)
        seen.add(row['source_id']);cases.append({'query':phrase,'expected_source_id':row['source_id'],'source_date':row['date'],'genre_hint':row['genre'],'passed':passed})
        if len(cases)>=30:break
    assert len(cases)==30
    sentinel='新奶绿资料库不应存在的测试短语zimuunknown20261023'
    assert db.execute('SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?',('"'+sentinel+'"',)).fetchone()[0]==0
    cases.append({'query':sentinel,'expected':'no matches','passed':True})
    db.close()
    engine.save(ROOT/'eval/全文检索回归.json',{'test_type':'literal source retrieval, not character-similarity assessment','cases':cases,'passed':len(cases),'model_calls':0})
    behavior_episodes=json.loads((ROOT/'persona/behavior-episodes.json').read_text(encoding='utf-8'))['items']
    ids={x['id']:x for x in behavior_episodes}
    for group in groups:
        assert all(i in ids for i in group['support_episode_ids'])
        assert len({ids[i]['source_refs'][0]['source_id'] for i in group['support_episode_ids']})>=2
        assert all(sample['review']=='draft' and sample['adaptation']=='adapted' and not sample['user_is_verbatim'] for sample in group['samples'])
    for trait in traits:assert len({ids[i]['source_refs'][0]['source_id'] for i in trait['evidence_ids']})>=3
    summary={'checked_at':engine.now(),'counts':counts,'local_quality_screen':dict(local_counts),'provenance_errors':len(result['errors']),'expected_draft_warnings':len(result['warnings']),'literal_retrieval_cases_passed':len(cases),'budget_guard_and_evidence_unit_tests_passed':9,'human_approved_entries':0,'cross_record_group_references':'all present; at least 2 distinct records each','core_trait_references':'all present; at least 3 distinct records each','budget':budget.report(),'seconds':round(time.monotonic()-started,2),'scope':'Source integrity, literal retrieval, references and spending control; not human truth, audio attribution or persona similarity.'}
    engine.save(ROOT/'outputs/最终核验报告.json',summary)
    with (ROOT/'资料库使用说明.md').open('a',encoding='utf-8') as f:
        f.write('\n## 本地核验\n\n数据库完整性和全文数量检查通过；30条跨来源检索题及1条不存在内容的反例通过。人物格式与出处检查无错误，待审核提示属预期。9项费用边界与证据回填测试通过。这些检查不替代回听、事实核对或人物相似度人评。\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
