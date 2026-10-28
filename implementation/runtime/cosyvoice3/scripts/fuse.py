
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from common import *
setup()
import torch
d=read(T/'checkpoints.json');lookup={r.get('dataset_pass_fraction'):r for r in d['models']};assert .5 in lookup and 1. in lookup
if any(r.get('variant_id')=='fusion' for r in d['models']):print('Fusion exists; preserved.');raise SystemExit
parents=[torch.load(lookup[f]['adapter'],map_location='cpu',weights_only=True) for f in [.5,1.]]
assert parents[0]['base_sha256']==parents[1]['base_sha256']==sha(BASE/'llm.pt')
adapters={}
for name in parents[0]['adapters']:
    a,b=[p['adapters'][name] for p in parents]
    adapters[name]={'A':torch.cat([a['A'],b['A']],dim=0),
                    'B':torch.cat([.7*a['scale']*a['B'],.3*b['scale']*b['B']],dim=1),'scale':1.}
folder=T/'checkpoints';adapter=folder/'adapter-fusion-half70-full30.pt';torch.save({'adapters':adapters,'base_sha256':parents[0]['base_sha256'],'epoch':'fusion','parents':[lookup[.5]['sha256'],lookup[1.]['sha256']],'weights':[.7,.3]},adapter)
state=torch.load(BASE/'llm.pt',map_location='cpu',weights_only=True,mmap=True)
for name,v in adapters.items():state[name+'.weight']=state[name+'.weight'].float()+v['scale']*(v['B']@v['A'])
out=folder/'llm-fusion-half70-full30.pt';torch.save(state,out)
d['models'].append({'variant_id':'fusion','dataset_pass_fraction':None,'label':'融合：半轮70% + 一轮30%','adapter':str(adapter),'merged':str(out),'sha256':sha(out),'parents':[lookup[.5]['sha256'],lookup[1.]['sha256']],'weights':[.7,.3],'human_similarity_verified':False});write(T/'checkpoints.json',d);print('CV3-only adapter-delta fusion exported.',flush=True)
