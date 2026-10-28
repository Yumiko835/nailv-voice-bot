
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
import ast,hashlib,json,re,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'))
import publish_nailv_library as p
if (R/'review/conditional-acceptance-20261024/decision.json').exists():
    from publish_conditional_acceptance import main as apply_accepted
    apply_accepted();sys.exit(0)
project=p.load('project.json');report=p.load('outputs/人物资料补充报告.json')
project['text_pilot']['source_material']='Original accepted edition plus lexical-v2 style and separate source-checked self-supplement-20261024; new supplement has no human approval yet.'
project['persona_supplement']={'version':'self-supplement-20261024','items':report['active_supplement_items'],'path':'data/self-supplement/items.json','index':'data/self-supplement/library.sqlite3','core_facts':report['always_present_core'],'human_review':False,'source_collection_complete':True,'all_raw_subtitle_windows_semantically_exhausted':False,'review_page':'outputs/人物资料补充核对.html','report':'outputs/人物资料补充报告.json'}
p.save('project.json',project)
notice='''本轮人物资料补充已接入独立文字试聊。
试聊：http://127.0.0.1:49850/
资料与出处：http://127.0.0.1:49850/knowledge
补充了固定人设、人物关系、公开往事与活动；保留上一版措辞示范。
新资料有编辑核对与模型检查两种状态，尚未标成你已逐条认可。
原有7,621条已认可事实/经历和向量保留；其他旧QQ机器人未更改。
日后双击“06-开始文字试聊.cmd”会自动打开试聊，端口可能变化；资料页点击页面上的“查看本轮资料与出处”。
完整说明在：资料库/outputs/人物资料补充说明.md。
'''
(R.parent/'08-文字试聊说明.txt').write_text(notice,encoding='utf-8-sig')
for file,code in [('text-chat',(R/'tools/nailv_text_server.py').read_text(encoding='utf-8')),('knowledge',(R/'outputs/人物资料补充核对.html').read_text(encoding='utf-8'))]:
    if file=='text-chat':
        tree=ast.parse(code);code=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAGE' for t in n.targets))
    script=re.search(r'<script>([\s\S]*?)</script>',code).group(1)
    (R/'cache'/('check-'+file+'.js')).write_text(script,encoding='utf-8')
p.save('outputs/人物资料补充运行模块哈希.json',{f:hashlib.sha256((R/'tools'/f).read_bytes()).hexdigest() for f in ['nailv_text_core.py','nailv_text_server.py','nailv_self_knowledge.py']})
print('Project metadata, user instructions and JS syntax-check inputs updated.')
