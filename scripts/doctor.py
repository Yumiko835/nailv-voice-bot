"""Read-only asset inventory. Does not import torch, connect QQ or call an API."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_config import REPO,ROOT,dependency_path

def report():
    assets=json.loads((REPO/'config/assets.example.json').read_text(encoding='utf-8'))
    checks=[]
    for item in assets['required_runtime_assets']:
        path=ROOT/item['relative_path']
        checks.append({'name':item['name'],'exists':path.exists(),'required_for':item['required_for']})
    return {'scope':'file presence only; not model loading or human listening','python':sys.version.split()[0],'assets':checks,'ready_for_full_bot':all(x['exists'] for x in checks),'cloud_calls':0,'CUDA_initialized':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--require-ready',action='store_true');args=parser.parse_args();result=report()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(1 if args.require_ready and not result['ready_for_full_bot'] else 0)
