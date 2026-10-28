"""Update the existing free reader to expose full coverage and only-new filtering."""

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

p=Path(project_path('tools/browse_nailv_library.py'))
text=p.read_text(encoding='utf-8')
edits={
 '人物条目均为待核对草稿。字幕可能含读弹幕、歌曲、视频或连麦者的话；搜到原文不等于确认是她本人说的。':'已完成全部有字字幕的分段提炼。先前部分版的认可已记录；本次新增内容仍需核对。字幕可能含他人话语、歌词及识别错字，全文出现过不等于她本人的事实。',
 '<div class="stats" id="stats"></div>':'<div class="stats" id="stats"></div><p class="muted" id="coverage-note"></p>',
 '“模型保留”仍未通过人工审核。可以把条目ID与问题告诉制作助手，继续修改；本页面只读。':'先前部分版和本次补全的资料各自留有记录。勾选“只看本次补充”可查看新增内容；存疑与排除区单独保存，不当作人物事实。',
 '<input id="candidate-query"':'<label><input type="checkbox" id="new-only" style="min-width:auto;flex:none">只看本次补充</label><input id="candidate-query"',
 "const values=[[d.raw.source_records,'来源记录'],[d.raw.chunk_count,'可搜索片段'],[d.candidate_count,'模型保留的草稿'],[d.approved_count,'人工通过']];":"const values=[[d.raw.records_with_text,'有字录播'],[d.coverage?.completed_windows,'已分析长文本'],[d.candidate_count,'人物资料候选'],[d.production.held_candidates,'存疑候选（单独保留）']];$('coverage-note').textContent=d.coverage?.all_input_processed?'全部 '+d.coverage.total_windows+' 段均已分析；'+Number(d.coverage.covered_cues_without_overlap).toLocaleString()+' 行字幕覆盖核验，无漏段。4条空记录没有文字可提炼。':'正在读取覆盖报告。';",
 "q:$('candidate-query').value,offset:candidateOffset":"q:$('candidate-query').value,new_only:$('new-only').checked?'1':'0',offset:candidateOffset",
 "$('category').onchange=()=>{candidateOffset=0;loadCandidates().catch(showError)};":"$('category').onchange=()=>{candidateOffset=0;loadCandidates().catch(showError)};$('new-only').onchange=()=>{candidateOffset=0;loadCandidates().catch(showError)};",
 "'production':read('outputs/资料库制作报告.json',{}),":"'production':read('outputs/资料库制作报告.json',{}),'coverage':read('outputs/全量提炼覆盖核验.json',{}),",
 "                if needle:items=[x for x in items if needle in json.dumps(x,ensure_ascii=False).casefold()]":"                if arg('new_only')=='1':items=[x for x in items if x.get('collection_batch')=='full-extraction-supplement-20261023']\n                if needle:items=[x for x in items if needle in json.dumps(x,ensure_ascii=False).casefold()]",
}
if 'id="new-only"' not in text:
    for old,new in edits.items():
        assert text.count(old)==1,(old[:80],text.count(old))
        text=text.replace(old,new)
    compile(text,str(p),'exec')
    p.write_text(text,encoding='utf-8')
print('Reader updated; browsing remains local and free.')
