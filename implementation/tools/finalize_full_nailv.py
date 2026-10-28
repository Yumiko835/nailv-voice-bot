"""Reconcile full coverage, incremental review, readable delivery and local browser state."""
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
import hashlib, html, json, sys
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import extract_nailv_library as engine


def read(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8'))


def main():
    coverage=read('outputs/全量提炼覆盖核验.json')
    assert coverage['all_input_processed'] and coverage['covered_cues_without_overlap']==2757563
    assert coverage['fully_processed_sources']==1631 and coverage['completed_windows']==2708
    plan=read('work/full-extraction-plan.json');budget=engine.Budget().report()
    assert budget['conservative_upper_cny']<50 and budget['unsettled_requests']==0
    before=ROOT/plan['snapshot']
    prior=json.loads((before/'review/机器核对全部结果.json').read_text(encoding='utf-8'))['items'];prior_ids={x['id'] for x in prior}
    all_items=read('review/机器核对全部结果.json')['items']
    for item in all_items:
        if item['id'] not in prior_ids:item['collection_batch']='full-extraction-supplement-20261023'
    new_items=[x for x in all_items if x['id'] not in prior_ids]
    retained=[x for x in new_items if x['machine_review']['verdict']=='keep']
    counts={key:sum(x['category']==key for x in retained) for key in ['facts','corpus','behaviors']}
    for rel in ['persona/facts.json','persona/corpus.json','persona/behavior-episodes.json','review/待回听或争议候选.json','review/已排除候选.json','review/机器核对全部结果.json']:
        data=read(rel)
        for item in data['items']:
            if item['id'] not in prior_ids:item['collection_batch']='full-extraction-supplement-20261023'
        engine.save(ROOT/rel,data)
    batch=read('outputs/全量补充批次报告.json')
    batch.update(new_candidate_count=len(new_items),new_retained_count=len(retained),new_retained_by_category=counts,new_held_count=sum(x['machine_review']['verdict']=='hold' for x in new_items),new_rejected_count=sum(x['machine_review']['verdict']=='reject' for x in new_items),new_retained_ids=[x['id'] for x in retained])
    engine.save(ROOT/'outputs/全量补充批次报告.json',batch)
    extraction=read('outputs/候选提炼报告.json')
    summary=read('outputs/资料库制作报告.json')
    summary.update(full_corpus_extraction_complete=True,coverage=coverage,supplement=batch,prior_user_feedback={'quote':'看完了，我觉得都是对的','scope':'previous partial edition','record':'review/先前版本用户反馈.json'},budget=budget)
    engine.save(ROOT/'outputs/资料库制作报告.json',summary)
    final=read('outputs/最终核验报告.json')
    final.update(full_input_coverage=coverage,supplemental_retained_counts=counts,budget=budget,prior_edition_feedback_preserved=True)
    engine.save(ROOT/'outputs/最终核验报告.json',final)
    project=read('project.json');project['phase']='full-corpus-extraction-complete-candidate-review'
    project['extraction_coverage']={'complete':True,'sources':1631,'windows':2708,'cues':2757563,'report':'outputs/全量提炼覆盖核验.json'}
    project['review']['prior_edition_feedback']='review/先前版本用户反馈.json'
    engine.save(ROOT/'project.json',project)
    guide=ROOT/'资料库使用说明.md'
    with guide.open('a',encoding='utf-8') as f:
        f.write(f'\n## 这次补全的结果\n\n已补跑487个窗口。全部1,631份非空录播、2,708个窗口、2,757,563行字幕均经过模型分析，按行号区间合并核验，无漏段。4条空记录没有文字可提炼。\n\n本次新增候选{len(new_items)}条，经独立核对及本地筛选，保留事实/偏好/名词{counts["facts"]}条、经历/观点{counts["corpus"]}条、互动片段{counts["behaviors"]}条。存疑内容不并入保留区。\n\n`outputs/本次补全新增资料.html`单独列出新内容样例；在阅读器“人物候选”里可勾选“只看本次补充”。已认可的上一版、原报告及其文件哈希均留在`review/versions/`，用户反馈另有记录。新内容没有自动继承上一次认可。\n')
    sources={s['id']:s for s in read('sources/manifest.json')['sources']}
    selected=[]
    for cat in ['facts','corpus','behaviors']:
        used=set()
        for item in sorted([x for x in retained if x['category']==cat],key=lambda x:(-x['model_confidence'],x['id'])):
            sid=item['source_refs'][0]['source_id']
            if sid in used:continue
            used.add(sid);selected.append(item)
            if len(used)>=10:break
    esc=lambda x:html.escape(str(x),quote=True)
    cards=[]
    for n,item in enumerate(selected,1):
        body=f'<section><small>本次补全新增 · 待核对</small><h2>{n}. {esc(item.get("text") or item.get("name"))}</h2><code>{esc(item["id"])}</code>'
        if item.get('samples'):
            sample=item['samples'][0]
            body+=f'<p>情境概括（非逐字问题）：{esc(sample["user"])}</p><pre>{esc(sample["reply"])}</pre><p>回应姿态：{esc(item["response_posture"])}</p>'
        for ref in item['source_refs'][:3]:
            src=sources[ref['source_id']];url=src['origin']+('&' if '?' in src['origin'] else '?')+'t='+str(int(ref.get('start_seconds',0)))
            body+=f'<details><summary>{esc(src["record_date"][:10])} · {esc(src["title"])} · {int(ref["start_seconds"])}秒</summary><pre>{esc(ref["quote"])}</pre><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">核对录播原处</a></details>'
        cards.append(body+'</section>')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新奶绿：全量补充资料</title><style>body{max-width:1000px;margin:30px auto;padding:0 24px;background:#f4f7f5;color:#243c35;font:16px/1.8 system-ui,sans-serif}h1{font-size:28px}h2{font-size:20px}section{background:white;border:1px solid #cddfd4;border-radius:10px;padding:22px;margin:20px 0}small{color:#896120}code{font-size:12px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f2;padding:15px;font:14px/1.8 system-ui,sans-serif}summary{cursor:pointer}a{color:#17647a}</style>'
    page+=f'<h1>全部字幕已完成分段提炼</h1><p>1,631份非空录播 / 2,708个长文本窗口 / 2,757,563行字幕：逐行覆盖，无漏段。</p><p>本次补跑487个窗口，保留新增人物候选{len(retained)}条。以下{len(selected)}条样例来自本次补充，未重复先前样例。全量处理不等于全部音源都经回听核实；字幕说话人、错字或语义仍可有误。</p>'+''.join(cards)+'</html>'
    (ROOT/'outputs/本次补全新增资料.html').write_text(page,encoding='utf-8')
    (ROOT.parent/'05-查看本次补全新增资料.url').write_text('[InternetShortcut]\nURL='+ (ROOT/'outputs/本次补全新增资料.html').as_uri()+'\n',encoding='utf-8')
    print(json.dumps({'full_input_complete':True,'final_counts':{k:summary[k] for k in ['retained_draft_facts','retained_draft_corpus','retained_behavior_episodes','proposed_behavior_groups','proposed_core_traits','held_candidates','rejected_candidates']},'new_retained':counts,'budget':budget,'samples':len(selected)},ensure_ascii=False))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
