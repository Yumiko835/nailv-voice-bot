"""Finish every source window, reuse prior calls and audit only added/changed material."""
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
import collections, concurrent.futures, hashlib, json, shutil, sys, time
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import extract_nailv_library as engine
import review_nailv_library as review


def fingerprint(messages):
    return hashlib.sha256(json.dumps({'model':engine.MODEL,'messages':messages,'max_tokens':4096},ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def prepare():
    marker=ROOT/'work/full-extraction-plan.json'
    if marker.exists():return json.loads(marker.read_text(encoding='utf-8'))
    stamp=engine.now().replace(':','-')
    folder=ROOT/'review/versions'/('partial-before-full-'+stamp)
    files=['project.json','persona/identity.md','persona/facts.json','persona/corpus.json','persona/behaviors.json','persona/behavior-episodes.json','review/机器核对全部结果.json','review/待回听或争议候选.json','review/已排除候选.json','review/归纳建议.json','outputs/资料库制作报告.json','outputs/候选提炼报告.json','outputs/先核对这些资料.html','outputs/API用量与预算.json','资料库使用说明.md']
    hashes={}
    for rel in files:
        src=ROOT/rel;dst=folder/rel
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        hashes[rel]=hashlib.sha256(src.read_bytes()).hexdigest()
    plan={'created_at':engine.now(),'snapshot':str(folder.relative_to(ROOT)),'files_sha256':hashes,'user_feedback':{'quote':'看完了，我觉得都是对的','scope':'User accepted the presented partial edition; no claim of individual audio verification. New additions remain draft.','later_instruction':'先把人物资料提炼全提炼完吧'},'authorized_total_cny':50,'automatic_stop_cny':49,'scope':'All 2708 windows, including short, music and watchalong inputs; ambiguous speakers, lyrics and third-party content must be excluded or held, not treated as character facts.'}
    engine.save(marker,plan)
    engine.save(ROOT/'review/先前版本用户反馈.json',plan)
    return plan


def cached_ok():
    results={}
    for path in sorted((ROOT/'work/model-results').glob('extract-*.json')):
        row=json.loads(path.read_text(encoding='utf-8'))
        if row.get('status')=='ok':results.setdefault(row['job'],set()).add(row.get('fingerprint'))
    return results


def coverage():
    valid=cached_ok();db=engine.connect();per_source=collections.defaultdict(list);by_genre=collections.Counter();complete=[];missing=[]
    for row in db.execute('SELECT * FROM windows ORDER BY source_id,lo'):
        w=dict(row);_,_,messages=engine.render_job(w,db)
        if fingerprint(messages) in valid.get('extract-'+w['id'],set()):
            complete.append(w['id']);per_source[w['source_id']].append((w['lo'],w['hi']));by_genre[w['genre']]+=1
        else:missing.append(w['id'])
    covered=0;fully_covered=0;gaps=[]
    sources=list(db.execute('SELECT id,cue_count FROM sources WHERE cue_count>0'))
    for source in sources:
        upto=0;count=0
        for a,b in sorted(per_source[source['id']]):
            if a>upto:gaps.append({'source_id':source['id'],'lo':upto,'hi':a})
            count+=max(0,b-max(a,upto));upto=max(upto,b)
        if upto<source['cue_count']:gaps.append({'source_id':source['id'],'lo':upto,'hi':source['cue_count']})
        covered+=count
        if count==source['cue_count']:fully_covered+=1
    total_cues=db.execute('SELECT count(*) FROM cues').fetchone()[0];total_windows=db.execute('SELECT count(*) FROM windows').fetchone()[0];db.close()
    report={'checked_at':engine.now(),'total_nonempty_sources':len(sources),'fully_processed_sources':fully_covered,'empty_source_records':4,'total_windows':total_windows,'completed_windows':len(complete),'missing_windows':missing,'completed_windows_by_genre':dict(by_genre),'total_cues':total_cues,'covered_cues_without_overlap':covered,'uncovered_cue_intervals':gaps,'all_input_processed':not missing and covered==total_cues and not gaps,'meaning':'Every subtitle cue was included in a successful model extraction input. This is not a claim that every possible fact was extracted or that speakers were verified by listening.'}
    engine.save(ROOT/'outputs/全量提炼覆盖核验.json',report)
    return report


def extract_all(budget,workers=12):
    client=engine.APIClient(budget);valid=cached_ok();db=engine.connect();pending_windows=[]
    for row in db.execute('SELECT * FROM windows ORDER BY source_id,window_order'):
        window=dict(row);_,_,messages=engine.render_job(window,db)
        if fingerprint(messages) not in valid.get('extract-'+window['id'],set()):pending_windows.append(window)
    db.close();print(json.dumps({'stage':'full_extract_start','remaining_windows':len(pending_windows),'budget':budget.report()},ensure_ascii=False),flush=True)
    stats=collections.Counter();started=time.monotonic()
    def run(window):
        conn=engine.connect()
        try:_,_,messages=engine.render_job(window,conn)
        finally:conn.close()
        return client.call('extract-'+window['id'],'extract',messages,4096,41.)['status']
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        iterator=iter(pending_windows);running={pool.submit(run,w) for w in [next(iterator,None) for _ in range(workers)] if w is not None};stopped=False
        while running:
            done,running=concurrent.futures.wait(running,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                status=future.result();stats[status]+=1
                if status in ('budget_limit','stopped') or stats['error']>=3:stopped=True
                if not stopped:
                    w=next(iterator,None)
                    if w is not None:running.add(pool.submit(run,w))
            progress={'stage':'full_extract','completed_new':sum(stats.values()),'total_new':len(pending_windows),'statuses':dict(stats),'elapsed_seconds':round(time.monotonic()-started),'budget':budget.report()}
            engine.save(ROOT/'work/full-extraction-progress.json',progress)
            if sum(stats.values())%20==0 or stopped:print(json.dumps(progress,ensure_ascii=False),flush=True)
    engine.materialize();result=coverage()
    report=json.loads((ROOT/'outputs/候选提炼报告.json').read_text(encoding='utf-8'))
    report.update(full_corpus_model_review=result['all_input_processed'],coverage_report='outputs/全量提炼覆盖核验.json',coverage_definition=result['meaning'])
    engine.save(ROOT/'outputs/候选提炼报告.json',report);engine.save(ROOT/'outputs/API用量与预算.json',budget.report())
    print(json.dumps({'stage':'all_input_extraction_finished','coverage':result,'budget':budget.report()},ensure_ascii=False),flush=True)
    return result


def candidate_hash(item):
    keys=['id','category','text','name','trigger','response_posture','source_refs','samples']
    return hashlib.sha256(json.dumps({k:item[k] for k in keys if k in item},ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def finish_review(budget,plan):
    items=json.loads((ROOT/'work/all-candidates.json').read_text(encoding='utf-8'))['items']
    prior=json.loads((ROOT/plan['snapshot']/'review/机器核对全部结果.json').read_text(encoding='utf-8'))['items']
    previous={x['id']:x for x in prior};reuse={};new=[]
    # Ignore review flags when comparing content. Keep prior conservative holds.
    for item in items:
        old=previous.get(item['id'])
        if old and candidate_hash(item)==candidate_hash(old) and old.get('machine_review',{}).get('model'):
            reuse[item['id']]=old
        else:new.append(item)
    print(json.dumps({'stage':'incremental_audit_start','reused_candidates':len(reuse),'new_or_changed_candidates':len(new),'budget':budget.report()},ensure_ascii=False),flush=True)
    client=engine.APIClient(budget)
    audited=review.audit_candidates(client,new,workers=10)
    extra={x['id']:x for x in audited}
    combined=[reuse[x['id']] if x['id'] in reuse else extra[x['id']] for x in items]
    engine.save(ROOT/'work/audited-candidates.json',{'items':combined})
    kept=[x for x in combined if x['machine_review']['verdict']=='keep']
    groups,traits=review.propose_patterns(client,kept)
    engine.save(ROOT/'outputs/全量补充批次报告.json',{'created_at':engine.now(),'previous_candidates':len(prior),'all_candidates':len(items),'reused_machine_decisions':len(reuse),'new_or_changed_machine_checks':len(new),'prior_user_feedback':'review/先前版本用户反馈.json','new_material_review':'draft; prior feedback does not approve new additions','proposed_groups_before_local_screen':len(groups),'proposed_traits_before_local_screen':len(traits)})
    engine.save(ROOT/'outputs/API用量与预算.json',budget.report())
    print(json.dumps({'stage':'full_incremental_review_finished','budget':budget.report()},ensure_ascii=False),flush=True)


def main():
    plan=prepare();budget=engine.Budget();result=extract_all(budget)
    if not result['all_input_processed']:raise RuntimeError('Not all inputs completed; coverage report retained. No full-completion claim.')
    finish_review(budget,plan)


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
