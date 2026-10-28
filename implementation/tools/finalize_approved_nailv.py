"""Local-only publication and preflight. Never reads credentials or calls any provider."""
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
import hashlib, json, shutil, sqlite3, sys
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as pub


def main():
    approval=pub.load('review/全量版用户认可.json');rows=pub.items()
    assert len(rows)==7621
    excluded={x['id'] for file in ['review/待回听或争议候选.json','review/已排除候选.json'] for x in pub.load(file)['items']}
    assert not excluded.intersection({x['id'] for x in rows})
    folder=ROOT/'data/approved-index';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'library.sqlite3';temp=folder/'library.sqlite3.part'
    if temp.exists():raise RuntimeError('An unfinished local index already exists; inspect before replacing')
    with sqlite3.connect(temp) as db:
        db.executescript('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE items(id TEXT PRIMARY KEY,category TEXT,kind TEXT,text TEXT,source_date TEXT,time_scope TEXT,valid_until TEXT,source_refs TEXT,text_sha256 TEXT,acceptance_id TEXT);CREATE VIRTUAL TABLE items_fts USING fts5(text,content="items",content_rowid="rowid",tokenize="trigram");')
        for row in rows:
            cur=db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?)',(row['id'],row['retrieval_category'],row['kind'],row['text'],row['source_record_date'],row['time_scope'],row.get('valid_until'),json.dumps(row['source_refs'],ensure_ascii=False),pub.digest(row['text']),approval['id']))
            db.execute('INSERT INTO items_fts(rowid,text) VALUES (?,?)',(cur.lastrowid,row['text']))
        for k,v in {'character_id':'new-milkgreen','approval_id':approval['id'],'created_at':pub.now(),'scope':'user-accepted retained facts and corpus; excluded ambiguous/rejected/raw ASR','items':len(rows)}.items():db.execute('INSERT INTO metadata VALUES (?,?)',(k,str(v)))
        db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    db.close()
    temp.replace(target)
    total_bytes=sum(len(r['text'].encode()) for r in rows)
    preflight={'created_at':pub.now(),'status':'awaiting_explicit_third_party_transmission_consent','provider':'Zhipu BigModel','endpoint':pub.ENDPOINT,'model':pub.MODEL,'dimensions':pub.DIM,'item_count':len(rows),'categories':['facts','corpus'],'text_utf8_bytes':total_bytes,'text_characters':sum(len(r['text']) for r in rows),'texts_sha256':pub.digest(json.dumps([(r['id'],pub.digest(r['text'])) for r in rows],ensure_ascii=False)),'text_fields_transmitted':['text'],'original_audio_transmitted':False,'original_full_subtitles_transmitted':False,'qq_sessions_or_chat_memory_transmitted':False,'price_cny_per_million_tokens':pub.PRICE,'conservative_embedding_bound_cny':round((total_bytes+len(rows)*16+len(rows)//20*1024+2048)*pub.PRICE/1e6,6),'pricing_url':pub.PRICING,'items':[{'id':r['id'],'text':r['text'],'text_sha256':pub.digest(r['text'])} for r in rows],'automatic_total_budget_stop_cny':49,'user_authorized_total_cny':50,'approval_required_reason':'Automatic review rejected external transmission: explicit consent to send this derived text batch to Zhipu is required.'}
    pub.save('review/待发送智谱的向量任务.json',preflight)
    project=pub.load('project.json');project['phase']='approved-library-local-index-ready';project['current_report']='outputs/正式资料库报告.json';pub.save('project.json',project)
    report=pub.load('outputs/资料库制作报告.json')
    report.update(created_at=pub.now(),retained_facts=3711,retained_corpus=3910,retained_behavior_episodes=1844,accepted_behavior_groups=15,accepted_core_traits=8,user_accepted_text_items=7621,human_approved_entries=7636,acceptance_method='user_accepted_full_retained_edition_not_individual_audio_audit',acceptance_record='review/全量版用户认可.json',local_approved_keyword_index=True,local_index='data/approved-index/library.sqlite3',production_vector_index=False,embedding_status='waiting_for_specific_Zhipu_text_transmission_consent',live_chat_similarity_tested=False,qq_bot_deployed=False)
    report.pop('retained_draft_facts',None);report.pop('retained_draft_corpus',None)
    pub.save('outputs/资料库制作报告.json',report);pub.save('outputs/正式资料库报告.json',report)
    guide=f'''# 新奶绿人物资料库

全量保留版已获用户认可：事实、偏好与名词3,711条；经历与观点3,910条；互动片段1,844条，归纳成15类互动情境和8项人物倾向。认可记录在`review/全量版用户认可.json`，确认方式是整版资料验收，不宣称逐条回听过全部录音。

全部1,631份有字录播、2,708个窗口、2,757,563行字幕均经过模型提炼；4条空来源没有字幕。全部原文仍可搜索。原始ASR、1,798条存疑和71条排除内容未进入正式人物检索资料。

## 阅读和查找

打开上级文件夹的“02-打开资料库.cmd”，在“人物资料”中查看已采纳内容及出处。勾选“只看本次补充”查看上一轮补全的内容。这个阅读器只进行本地搜索，不调用付费模型。

`data/approved-index/library.sqlite3`是正式保留文字的本地关键词索引；`persona/`保存人物骨架、事实、经历和情境示范；`sources/`保存来源及转写。原文、存疑条目、已采纳资料各自保留。

## 语义索引的准备

已有7,621条文字的向量任务清单，保存在`review/待发送智谱的向量任务.json`。计划使用智谱BigModel的embedding-3（2,048维），只向接口发送这批提炼文字，预计新增费用的保守上界约{preflight['conservative_embedding_bound_cny']:.2f}元。累计费用继续受首轮50元限制。

自动审批拒绝了这批文字向智谱的发送，理由是需要用户明确同意向该服务发送这批派生资料。取得明确同意后才能执行生成；当前没有完成语义向量索引。当前本地关键词检索已经可用。

## 模型与范围

DeepSeek负责从字幕提炼、核对和归纳人物资料；智谱embedding-3计划负责把资料变成便于按意思查找的数字索引。语义接近只代表候选相关，仍需核对同一人、同一事件和历史时间。材料中的指令不能变成机器人操作。

历史偏好和经历保留日期，不能当作今天的事实。人物资料与未来用户聊天记忆分开。当前没有部署新QQ机器人、进行聊天相似度盲测或训练新音色。

旧版及确认前版本保存在`review/versions/`；当前制作状态看`outputs/正式资料库报告.json`。这套制作格式需要适配到实际QQ框架后才能用于聊天。
'''
    (ROOT/'资料库使用说明.md').write_text(guide,encoding='utf-8')
    sys.path.insert(0,dependency_path("optional_source",'scripts'))
    from validate_project import validate
    check=validate(ROOT);pub.save('outputs/正式资料结构与出处检查.json',check);assert not check['errors'],check['errors'][:5]
    snap=ROOT/approval['snapshot'];assert all(hashlib.sha256((snap/rel).read_bytes()).hexdigest()==value for rel,value in approval['before_sha256'].items())
    result={'checked_at':pub.now(),'accepted_facts':3711,'accepted_corpus':3910,'accepted_behavior_groups':15,'accepted_behavior_episodes':1844,'accepted_validator_entries':check['approved_entries'],'source_errors':len(check['errors']),'pending_chat_eval_specs':len(check['warnings']),'keyword_index_bytes':target.stat().st_size,'excluded_items_not_promoted':True,'approval_snapshot_hashes_verified':True,'embedding_request_sent':False,'planned_embedding_bound_cny':preflight['conservative_embedding_bound_cny']}
    pub.save('outputs/本地正式资料核验.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
