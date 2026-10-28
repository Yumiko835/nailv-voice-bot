"""Start/stop only project-owned processes, with PID reuse protection."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import argparse
import json
import os
import subprocess
import time
from pathlib import Path
import psutil

ROOT=Path(project_path(''));R=ROOT/'runtime/astrbot'
STATE=R/'processes.json';LOG=R/'logs';LOG.mkdir(parents=True,exist_ok=True)
PY=R/'.venv/Scripts/python.exe'
ITEMS={
 'astrbot':([str(PY),'-B','-X','utf8',str(R/'scripts/run_astrbot.py')],R/'app','run_astrbot.py'),
 'napcat':([str(ROOT/'runtime/napcat/node-app/node.exe'),str(ROOT/'runtime/napcat/node-app/nailv-napcat.cjs'),'-q',setting("bot_qq","")],ROOT/'runtime/napcat/node-app','nailv-napcat.cjs'),
 'voice':([str(ROOT/'runtime/cosyvoice2/.venv/Scripts/python.exe'),'-B','-X','utf8',str(ROOT/'runtime/cosyvoice3/scripts/rhythm-bridge/live_bridge_server.py')],ROOT,'live_bridge_server.py')}

def matched(item):
    try:
        proc=psutil.Process(item['pid'])
        cmd=' '.join(proc.cmdline())
        return proc if abs(proc.create_time()-item['created'])<1 and str(ROOT) in cmd and item['marker'] in cmd else None
    except psutil.Error:return None

def save(state):STATE.write_text(json.dumps(state,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop','status']);parser.add_argument('--components',nargs='+',choices=list(ITEMS),default=list(ITEMS));a=parser.parse_args()
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    for name in a.components:
        item=state.get(name,{});proc=matched(item) if item else None
        if a.action=='start' and not proc:
            command,cwd,marker=ITEMS[name]
            # Avoid spawning an untracked duplicate from earlier work.
            others=[p for p in psutil.process_iter(['pid','cmdline','name']) if p.pid!=os.getpid() and p.info['name'].lower() in ('python.exe','pythonw.exe','node.exe') and
                    marker in ' '.join(p.info['cmdline'] or []) and str(ROOT) in ' '.join(p.info['cmdline'] or [])]
            if others:raise RuntimeError('Existing untracked '+name+' process: inspect first')
            env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',TEMP=str(R/'tmp'),TMP=str(R/'tmp'))
            if name=='napcat':
                profile=ROOT/'runtime/napcat/node-app/qq-profile'
                for variable,tail in [('USERPROFILE','home'),('APPDATA','roaming'),('LOCALAPPDATA','local')]:
                    dest=profile/tail;dest.mkdir(parents=True,exist_ok=True);env[variable]=str(dest)
            with (LOG/(name+'.log')).open('ab') as log:
                child=subprocess.Popen(command,cwd=str(cwd),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            proc=psutil.Process(child.pid);state[name]={'pid':child.pid,'created':proc.create_time(),'marker':marker};save(state)
        elif a.action=='stop' and proc:
            family=proc.children(recursive=True)
            # All descendants must still be under this independently owned process.
            for child in reversed(family):
                try:child.terminate()
                except psutil.NoSuchProcess:pass
            proc.terminate();psutil.wait_procs([*family,proc],timeout=10)
            state.pop(name,None);save(state);proc=None
        print(json.dumps({'component':name,'running':bool(proc and proc.is_running()),'pid':proc.pid if proc else None}))

if __name__=='__main__':main()
