"""Apply an explicit, scoped user approval without rewriting the accepted vector edition."""

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
import copy,hashlib,json,re,shutil,sqlite3,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'));import publish_nailv_library as p
A='review/conditional-acceptance-20261024/'
def load(name):return p.load(A+name)
def signature(x):return hashlib.sha256(json.dumps({k:x.get(k) for k in ['id','text','source_record_date','source_refs']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def main():
    record=load('decision.json');baseline=load('before/active-items.json')['items'];candidates=load('before/candidate-items.json')['items'];raw={x['id']:x for x in candidates}
    approved=load('accepted-items.json')['items'];held=load('held-items.json')['items'];merged=load('merged-items.json')['items']
    assert len(record['decisions'])==len(raw)==2429
    for d in record['decisions']:assert signature(raw[d['candidate_id']])==d['input_signature']
    for x in baseline:
        if x['id'] in ['fact-self-age19','fact-self-birthday']:
            x.update({'human_review':True,'human_review_scope':'explicit user confirmation of birthday and fixed role age','core_confirmation_id':record['id']})
    items=baseline+approved;assert len({x['id'] for x in items})==len(items)
    p.save('data/self-supplement/items.json',{'version':'self-supplement-20261024','revision':'conditional-user-acceptance-20261024','items':items,'approval_id':record['id'],'note':'Original accepted edition retained; newly accepted candidates use edition-level user approval after a consistency filter, not original-audio verification.'})
    dest=R/'data/self-supplement/library.sqlite3';temp=dest.with_name('library.approval-next.sqlite3')
    shutil.copy2(R/A/'before/library.sqlite3',temp)
    db=sqlite3.connect(temp);db.execute('DELETE FROM items');db.execute('DELETE FROM item_fts')
    for x in items:
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?)',(x['id'],x['kind'],x['text'],json.dumps(x.get('entities',[]),ensure_ascii=False),json.dumps(x.get('topics',[]),ensure_ascii=False),x['source_record_date'],x['time_scope'],json.dumps(x['source_refs'],ensure_ascii=False),x['review']));db.execute('INSERT INTO item_fts VALUES(?,?)',(x['id'],x['text']))
    assert db.execute('SELECT count(*) FROM items').fetchone()[0]==len(items);db.commit();db.close();temp.replace(dest)
    p.save('review/self-supplement-20261024/subtitle-pending.json',{'items':held,'note':'Only explicitly conflicting or misattributed candidates remain excluded after the user-approved batch was applied.','approval_id':record['id']})
    p.save('review/self-supplement-20261024/merged-evidence.json',{'items':merged,'approval_id':record['id']})
    report=load('before/report.json');report.update({'active_supplement_items':len(items),'subtitle_candidates_pending_attribution':len(held),'additional_subtitle_drafts':0,'new_human_review':True,'candidate_user_approval':{'id':record['id'],'scope':record['scope'],'counts':record['counts']},'user_accepted_additions':len(approved),'duplicate_evidence_merged':len(merged),'conditional_exclusions':len(held),'kinds':dict(__import__('collections').Counter(x['kind'] for x in items))})
    p.save('outputs/人物资料补充报告.json',report)
    project=p.load('project.json');project['persona_supplement'].update({'items':len(items),'conditional_candidate_approval':record['id'],'user_accepted_candidate_count':len(approved),'remaining_exclusions':len(held),'original_audio_verification':False});project['text_pilot']['source_material']='Original accepted edition, lexical-v2 style, source-checked social supplement and user-accepted subtitle candidate edition after consistency checks.';p.save('project.json',project)
    semantic_ready=False
    if (R/'data/self-supplement/semantic.json').exists():
        import nailv_supplement_vectors as sv
        semantic_ready=p.load(sv.POINTER).get('text_set_sha256')==sv.text_set(sorted(items,key=lambda x:x['id']))
    semantic_note=(f'新增{len(items)}条资料已按用户授权交给智谱生成向量，合计{len(items)+7621}条支持按意思检索；索引与出处保存在本机。' if semantic_ready else '新增资料使用独立本地检索，尚未生成当前版本的补充向量。')
    if semantic_ready:
        report.update(semantic_indexed_supplement_items=len(items),total_semantic_items=len(items)+7621);p.save('outputs/人物资料补充报告.json',report)
    md=f'''# 人物资料补充 · 用户认可后接入

你已查看待核对候选，并同意“如果跟之前的内容不冲突都可以加进去”，随后明确确认“3月4日、永远19岁是对的”。

本批2,429条已与原有8,411条事实/经历和补充条目做本地近邻对照，并检查固定设定、时间、原文连续区间与疑似误归属。新增{len(approved)}条，重复{len(merged)}条已合并保留证据，冲突或明确误归属的{len(held)}条未加入。5条按原文澄清了代主理人、朋友玩笑或投稿语境。不同年份的偏好和经历保留日期，不一概当成冲突。

本轮补充目前共{len(items)}条接入独立文字试聊；加上原有7,621条事实/经历，共{len(items)+7621}条可用记录。原事实/经历、行为、措辞示范与7,621条语义向量没有改写。{semantic_note}

固定设定以3月4日生日、永远19岁为准，不随年份增长。原文、时间戳、编辑改动、合并去向、排除原因和本次认可记录都保留。你的认可按整批候选记录，不声称每段原声已经逐句听校；一致性检查也不等于对所有语义矛盾的形式化证明。

试聊：http://127.0.0.1:49850/\n核对资料：http://127.0.0.1:49850/knowledge

本轮认可与快照：review/conditional-acceptance-20261024/。图片文字及更广泛字幕还未逐一核完；这不影响本批已认可材料的接入。QQ和语音接入仍沿用原项目状态，本次更新的是独立文字试聊资料。
'''
    (R/'outputs/人物资料补充说明.md').write_text(md,encoding='utf-8')
    (R.parent/'08-文字试聊说明.txt').write_text('本批待核对资料已按你的认可接入。\n固定设定：3月4日生日，永远19岁。\n新增'+str(len(approved))+'条，重复'+str(len(merged))+'条合并，'+str(len(held))+'条冲突或误归属未加入。\n试聊：http://127.0.0.1:49850/\n资料与出处：http://127.0.0.1:49850/knowledge\n日后双击06-开始文字试聊.cmd可打开试聊，端口可能变化；资料页可从试聊页面进入。\n'+semantic_note+'\n',encoding='utf-8-sig')
    payload=json.dumps({'items':items+held+merged,'counts':{'active':len(items),**record['counts']},'collection':report['collection']},ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>奶绿 · 已认可资料</title><style>body{font:16px/1.75 'Microsoft YaHei',sans-serif;color:#243d34;background:#f4f7f5;max-width:1050px;margin:30px auto;padding:0 20px}input,select,button{font:inherit;padding:9px;margin:6px;border:1px solid #afc8ba;border-radius:6px}article,.note{background:white;padding:20px;border:1px solid #d4e1d9;border-radius:10px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f4;padding:14px;font-size:14px}.muted{color:#61766c;font-size:14px}a{color:#24694c}.held{border-color:#c99585}.badge{font-weight:600}</style><h1>奶绿 · 已认可资料</h1><p><a href="/">返回文字试聊</a></p><div class="note"><b>固定设定：3月4日生日，永远19岁。</b><p id="counts"></p><p>已按你“与之前内容不冲突就可以加入”的确认接入。不同时间的经历与喜好保留日期；朋友玩笑、花店世界观与本人现实经历保留各自语境。</p></div><p class="muted">认可按本批候选记录，不代表每段原声已逐句听校。图片文字和更广泛字幕还未全部核完。每条均可展开查看原文、时间及本次处理结果。</p><input id="q" placeholder="找人物、经历或关键词" aria-label="搜索人物资料"><select id="filter"><option value="active">已接入试聊</option><option value="accepted">本次认可后新增</option><option value="held">冲突或误归属，未加入</option><option value="merged">重复，已合并</option><option value="all">全部</option></select><span id="count"></span><div id="list"></div><button id="more">再看50条</button><script>const data=PAYLOAD;let shown=50;const $=x=>document.getElementById(x);$('counts').textContent=`本批新增 ${data.counts.accepted} 条，重复 ${data.counts.merged} 条已合并，${data.counts.held} 条未加入。当前补充库共 ${data.counts.active} 条已接入试聊。`;function draw(){let q=$('q').value.trim().toLowerCase(),f=$('filter').value;let rows=data.items.filter(x=>(f==='all'||(f==='active'&&x.active_in_text_pilot)||(f==='accepted'&&x.acceptance_id)||(f==='held'&&x.acceptance_disposition==='held')||(f==='merged'&&x.acceptance_disposition==='merged'))&&JSON.stringify([x.text,x.entities,x.topics]).toLowerCase().includes(q));$('count').textContent=` ${rows.length} 条`;$('list').replaceChildren();for(const x of rows.slice(0,shown)){const c=document.createElement('article'),t=document.createElement('p'),m=document.createElement('div');t.textContent=x.text;m.className='muted';m.textContent=(x.acceptance_disposition==='held'?'有冲突或误归属 · 未加入':x.acceptance_disposition==='merged'?'重复 · 已合并':x.acceptance_id?'你已认可 · 已接入试聊':x.human_review?'固定设定 · 你已确认':x.editorial_checked?'编辑核对 · 已接入试聊':'本人动态 · 已接入试聊')+' · 来源时间：'+x.source_record_date+' · '+({stable:'固定背景',historical:'过去的记录',planned:'当时的计划',uncertain:'保留不确定性'}[x.time_scope]||'保留语境');c.append(t,m);if(x.acceptance_disposition==='held')c.className='held';for(const note of [x.decision_reason,x.uncertainty,x.editorial_change?.reason,x.merged_into?'合并至：'+x.merged_into:''])if(note){const n=document.createElement('p');n.textContent=note;c.append(n)}const d=document.createElement('details'),s=document.createElement('summary');s.textContent='查看原文和出处';d.append(s);for(const r of x.source_refs){const a=document.createElement('a');a.href=r.origin||'#';a.target='_blank';a.rel='noopener noreferrer';a.textContent=r.source_id+(r.start_seconds!==undefined?' · '+r.start_seconds+' 秒':'');const pre=document.createElement('pre');pre.textContent=r.quote;d.append(a,pre)}c.append(d);$('list').append(c)}$('more').hidden=shown>=rows.length}$('q').oninput=$('filter').onchange=()=>{shown=50;draw()};$('more').onclick=()=>{shown+=50;draw()};draw();</script></html>'''.replace('PAYLOAD',payload)
    (R/'outputs/人物资料补充核对.html').write_text(page,encoding='utf-8');(R/'cache/check-knowledge.js').write_text(re.search(r'<script>([\s\S]*?)</script>',page).group(1),encoding='utf-8')
    print(json.dumps({'active_items':len(items),**record['counts']},ensure_ascii=False),flush=True)
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
