"""Local wrappers and handoff for the independent, tested text pilot."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import json,sys
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import nailv_text_core as core


def main():
    report=core.pub.load('outputs/文字试聊生成检查.json');assert report['generated_responses']==24
    parent=ROOT.parent
    for original,new in [('Start-Library.ps1','Start-TextChat.ps1'),('Stop-Library.ps1','Stop-TextChat.ps1')]:
        code=(parent/original).read_text(encoding='utf-8-sig')
        for a,b in [('tools/browse_nailv_library.py','tools/nailv_text_server.py'),('logs/reader.json','logs/text-chat.json'),('new-milkgreen-library','new-milkgreen-text-pilot'),('reader.out.log','text-chat.out.log'),('reader.err.log','text-chat.err.log'),('library/logs/reader.err.log','library/logs/text-chat.err.log'),('Library reader:','Text pilot:'),('local library reader','local text pilot'),('Library database','Text pilot data')]:code=code.replace(a,b)
        (parent/new).write_text(code,encoding='utf-8-sig')
    for name,script in [('06-开始文字试聊.cmd','Start-TextChat.ps1'),('07-停止文字试聊.cmd','Stop-TextChat.ps1')]:
        (parent/name).write_text('@echo off\r\npowershell.exe -NoProfile -File "%~dp0'+script+'"\r\nif errorlevel 1 pause\r\n',encoding='ascii')
    config=core.pub.load('project.json');config['phase']='experimental-text-pilot-ready';config['features']['text']=True;config['runtime']['platform']='local_text_pilot';config['review']['text_style']='trial_awaiting_user_comparison';config['review']['character_similarity']='awaiting_text_pilot_blind_choices';config['text_pilot']={'entry':'tools/nailv_text_server.py','bind_host':'127.0.0.1','history':'browser-memory-only; live messages not written to local chat files','chat_provider':'DeepSeek','semantic_lookup':'opt-in; query sent to Zhipu only when selected','source_material':'accepted persona plus separately marked experimental style observations','stage_budget_cap_cny':2,'comparison':'eval/text-pilot/blind.json','voice':False,'qq':False};core.pub.save('project.json',config)
    funds=core.pub.load('outputs/总费用与预算.json');fresh=core.budget_report();funds.update(deepseek_conservative_cny=fresh['deepseek']['conservative_upper_cny'],combined_conservative_cny=fresh['combined_conservative_cny'],updated_at=core.pub.now(),text_pilot_stage_cap_cny=2);core.pub.save('outputs/总费用与预算.json',funds)
    note='''新奶绿：资料库与文字试聊

06-开始文字试聊.cmd：打开独立的AI文字试聊页面。
07-停止文字试聊.cmd：只关闭这个文字试聊服务。

页面有“自由试聊”和“盲选对照”。八道对照题各有三种回复，顺序已打乱；选最像的一项，或选“都不像”，点击“记录我的选择”后才保存意见。

实时回复使用DeepSeek，消息与最近对话会发给该服务；当前只生成文字。自由聊天不写入本地聊天记录文件，刷新后清空。
默认在本地查已认可资料；勾选“按意思检索”后，本条问题也会发送给智谱进行向量化。
浏览预先生成的对照不产生新的API调用。真人风格像不像，需要你自己试聊和判断；程序检查通过不代表人评已经通过。

文字试聊的API调用计入此前50元总预算，本阶段另设2元调用限额，达到限额会停止新请求。
表达习惯观察见“资料库/style/表达风格观察.md”。它是试验观察，不会改写已经认可的人物事实。
语气、语速、轻笑和叹气目前只会显示为表达建议，尚未合成为声音。

02-打开资料库.cmd：查看全文、已采纳资料与出处，不调用付费模型。
04-停止资料库浏览器.cmd：只停止资料阅读器。

本项目与最初奶绿bot、灰泽满bot相互独立，目前没有接新QQ、训练新音色或自动向任何QQ发消息。
'''
    (parent/'08-文字试聊说明.txt').write_text(note,encoding='utf-8-sig');(parent/'先看这里-新奶绿.txt').write_text(note,encoding='utf-8-sig')
    guide=ROOT/'文字试聊说明.md';guide.write_text('# 新奶绿文字试聊\n\n'+note+'\n\n技术检查与24条生成记录见`outputs/文字试聊生成检查.json`。盲选版本对应表保存在`eval/text-pilot/key.json`，用户选择前不在网页显示。只有你在页面提交的选择会写进`review/text-pilot/`，不会自动写成“风格已经通过”。\n\n修改表达建议后可重建公开对照；不要将自由聊天或他人的私人记忆放入人物资料索引。服务启动和停止仅核对并管理本项目的进程。\n',encoding='utf-8')
    print(json.dumps({'text_pilot_ready':True,'comparison_cases':8,'responses':24,'human_review':'pending','budget':fresh,'root':str(parent)},ensure_ascii=False))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
