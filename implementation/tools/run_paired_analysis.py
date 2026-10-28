
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import concurrent.futures,json,sys
from pathlib import Path
ROOT=Path(project_path(''));sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as p
from nailv_study_client import StudyClient
tasks=p.load('work/style-v3-20261024/paired-analysis-tasks.json')['tasks']
def run(model,task):
    result=StudyClient(model).call(task['messages'],'paired-'+task['id'],6000,.3)
    p.save('work/style-v3-20261024/comparison/'+model+'-'+task['id']+'.json',result)
    return {'model':model,'task':task['id'],'items':len(result['content'].get('items',[]))}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(run,model,task) for task in tasks for model in [setting("chat_model","deepseek-flash"),'deepseek-v4-pro']]
    for future in concurrent.futures.as_completed(futures):print(json.dumps(future.result(),ensure_ascii=False),flush=True)
