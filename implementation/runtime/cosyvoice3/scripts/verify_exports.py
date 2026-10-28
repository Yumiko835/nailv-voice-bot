
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
import torch,gc
base=torch.load(BASE/'llm.pt',map_location='cpu',weights_only=True,mmap=True);checkpoints=read(T/'checkpoints.json');receipts=[]
for r in checkpoints['models']:
    merged=torch.load(r['merged'],map_location='cpu',weights_only=True,mmap=True);adapter=torch.load(r['adapter'],map_location='cpu',weights_only=True)
    assert set(base)==set(merged) and adapter['base_sha256']==sha(BASE/'llm.pt')
    changed={name+'.weight':v for name,v in adapter['adapters'].items()};frozen=0
    for key,value in base.items():
        if key in changed:
            v=changed[key];expected=value.float()+v['scale']*(v['B'].float()@v['A'].float());assert torch.equal(expected,merged[key]),key
        else:assert torch.equal(value,merged[key]),key;frozen+=1
    assert sha(r['merged'])==r['sha256']
    receipts.append({'fraction':r['dataset_pass_fraction'],'keys':len(base),'exact_adapter_updates':len(changed),'unchanged_tensors':frozen,'passed':True});del merged,adapter;gc.collect()
download=read(T/'download-receipt.json');frozen_networks=[]
for name in ['flow.pt','hift.pt','speech_tokenizer_v3.onnx']:
    expected=next(x['sha256'] for x in download['files'] if x['file']==name);assert sha(BASE/name)==expected;frozen_networks.append(name)
write(T/'export-verification.json',{'models':receipts,'official_frozen_files_sha256_unchanged':frozen_networks,'passed':True});print(json.dumps({'exports_verified':len(receipts)}),flush=True)
