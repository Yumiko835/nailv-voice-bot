"""Finish current publication metadata and free reader labels after real index verification."""

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
import json,sys

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as pub


def main():
    checks=pub.load('outputs/正式资料结构与出处检查.json');regression=pub.load('eval/语义检索回归.json');budget=pub.load('outputs/总费用与预算.json');index=pub.load('outputs/正式语义索引报告.json')
    assert not checks['errors'] and checks['approved_entries']==7636
    assert regression['stale_source_guard_passed'] and regression['held_and_rejected_absent']
    assert index['items']==7621 and budget['embedding_unsettled_requests']==0
    manifest=pub.load('review/待发送智谱的向量任务.json');assert manifest['transmission_consent']['user_quote']=='允许发送给智谱并生成索引'
    manifest.update(status='completed',completed_at=pub.now(),index_report='outputs/正式语义索引报告.json',budget=budget);pub.save('review/待发送智谱的向量任务.json',manifest)
    summary=pub.load('outputs/正式资料库报告.json')
    summary.update(created_at=pub.now(),production_vector_index=True,embedding_status='complete',semantic_items=7621,semantic_model='embedding-3',semantic_dimensions=2048,semantic_test_hit_at_10=regression['hit_at_10'],semantic_test_total=regression['total_cases'],budget=budget,semantic_retrieval_returns='evidence candidates, not verified factual answers',source_and_index_validation_errors=0,pending_chat_eval_specs=6,keyword_reader_paid_model_calls=False)
    pub.save('outputs/正式资料库报告.json',summary);pub.save('outputs/资料库制作报告.json',summary)
    reader=ROOT/'tools/browse_nailv_library.py';text=reader.read_text(encoding='utf-8')
    edits={
      '已完成全部有字字幕的分段提炼。先前部分版的认可已记录；本次新增内容仍需核对。字幕可能含他人话语、歌词及识别错字，全文出现过不等于她本人的事实。':'全量保留版已获用户认可，7,621条文字已生成正式语义索引。这里的浏览与关键词搜索仍在本地完成。原始字幕、存疑与排除内容各自保存；整版认可不代表逐条回听过全部音源。',
      '>人物候选<':'>人物资料<',
      '先前部分版和本次补全的资料各自留有记录。勾选“只看本次补充”可查看新增内容；存疑与排除区单独保存，不当作人物事实。':'已采纳资料和原始证据可在下方查看。勾选“只看本次补充”查看全量补充批次；存疑与排除区单独保存，不并入正式索引。',
      "[d.candidate_count,'人物资料候选']":"[d.approved_count,'已采纳资料（含互动分类）']",
      "'人工通过':'草稿 · 待核对','pill draft'":"'用户认可':(r.machine_review?.verdict==='reject'?'已排除':'存疑 · 待核对'),'pill'+(r.review==='approved'?'':' draft')",
      "+' 条。草稿状态不代表事实或说话人已确认。'":"+' 条。'",
      '候选姿态：':'回应姿态：',
      '>查看候选<':'>查看资料<',
      '筛选人物候选':'筛选人物资料',
    }
    if '>人物候选<' in text:
        for old,new in edits.items():
            assert text.count(old)==1,(old[:80],text.count(old));text=text.replace(old,new)
        compile(text,str(reader),'exec');reader.write_text(text,encoding='utf-8')
    # Older one-shot scripts must not silently turn an accepted edition back into drafts.
    old=ROOT/'tools/review_nailv_library.py';source=old.read_text(encoding='utf-8')
    signature='def publish(items,groups,traits,budget):\n'
    guard="    if (ROOT/'review/全量版用户认可.json').exists():raise RuntimeError('Accepted edition exists. Create and review a separate revision before replacing published material.')\n"
    if guard not in source:
        assert source.count(signature)==1;source=source.replace(signature,signature+guard);compile(source,str(old),'exec');old.write_text(source,encoding='utf-8')
    guide=f'''# 新奶绿人物资料库：正式保留版

全量保留资料已获用户认可，确认及备份见`review/全量版用户认可.json`、`review/versions/`。确认方式是整版资料验收，没有声称逐条回听过全部录音。

全部1,631份有字录播、2,708个窗口、2,757,563行字幕均经过模型提炼，4条空记录无文字。正式材料有事实/偏好/名词3,711条、经历/观点3,910条、互动片段1,844条、互动情境15类、人物倾向8项。原始ASR、1,798条存疑和71条排除内容不在正式人物索引中。

## 怎么查看

双击上级文件夹的“02-打开资料库.cmd”，在“人物资料”中查看已采纳条目、来源原文和时间戳。普通搜索在本地执行，不调用付费模型。语义索引供后续聊天程序检索相关材料，当前阅读器继续提供免费的关键词搜索。

## 已生成的检索文件

- `data/approved-index/library.sqlite3`：7,621条已认可文字的本地关键词索引。
- `data/index/index.json`：7,621条文字的智谱embedding-3向量，2,048维，带来源条目ID、文本哈希、模型及生成时间。
- `data/index/vectors.f32`、`catalog.json`：供查询程序快速读取的本地紧凑索引，约60MB。
- `persona/`：人设骨架、事实、经历、互动分类及示范；`sources/`：来源及转写；`review/`：认可记录、旧版和存疑区。

向量生成已获得明确的智谱传输授权，记录在`review/待发送智谱的向量任务.json`；只发送了已提炼文字。Key仍由原有本机文件或环境变量`EMBED_API_KEY`提供，未复制进新项目。

## 费用与检查

向量生成与检索测试合计按返回用量计费约{budget['embedding_accounted_cny']:.4f}元；加上前面的DeepSeek调用，累计保守计入约{budget['combined_conservative_cny']:.4f}元，低于50元授权上限。真实扣费以服务商账单为准。

文本出处、向量维度和哈希检查无错误；小范围改写检索题前10项命中{regression['hit_at_10']}/{regression['total_cases']}。源文本改变会阻止使用旧索引。该测试不是未知问题准确率或聊天相似度评测。

## 用于聊天时

DeepSeek负责提炼、核对及归纳；智谱embedding-3负责按意思查找相关材料。角色骨架少量常驻；事实按相关性检索；互动示范按情境选取；用户聊天记忆另存。语义接近不能替代事实核验，要核对同一人、事件与时间，不能把历史偏好说成今天的状态。

当前没有部署新QQ机器人、训练新音色或完成聊天相似度盲测；6条聊天评测题仍待实际运行和判定。制作格式需要适配到选定的QQ框架，不能直接覆盖灰泽满或最初奶绿bot的同名文件。

## 后续维护

`tools/publish_nailv_library.py query --query "要查的问题"`可做语义召回；它会向智谱发送这一查询文字并产生少量向量API费用，返回带出处的候选，不自动补写事实。修改资料、更换向量模型或维度后要重新审核并重建索引。

旧的提炼发布脚本已阻止覆盖当前认可版。需要继续扩充时另建修订批次，保留原版与确认记录。当前完整状态见`outputs/正式资料库报告.json`。
'''
    (ROOT/'资料库使用说明.md').write_text(guide,encoding='utf-8')
    receipt={'created_at':pub.now(),'approved_entries':checks['approved_entries'],'approved_text_indexed':7621,'approved_supporting_episodes':1844,'approval_record':'review/全量版用户认可.json','transmission_consent_record':'review/待发送智谱的向量任务.json','index_hash_guards':True,'held_rejected_raw_asr_not_indexed':True,'source_and_vector_errors':0,'semantic_regression_hit_at_10':regression['hit_at_10'],'semantic_regression_total':12,'chat_similarity_not_tested':True,'qq_not_deployed':True,'budget':budget}
    pub.save('outputs/正式资料库交付核验.json',receipt);print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
