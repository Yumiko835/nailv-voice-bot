"""Read-only low-peak loading of the exact local CPU SenseVoice weights.

FunASR's generic loader deep-copies its entire checkpoint. The critic needs no
key remapping here; validate every key and shape and copy once into the model.
No quantization, changed weights, external model fetching or package edits.
"""

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

def install():
    import sys
    sys.path.insert(0,project_path('runtime/sensevoice-curation/packages'))
    import torch
    from funasr.auto import auto_model
    original=auto_model.load_pretrained_model
    if getattr(original,'_local_low_peak',False):return
    expected=Path(project_path('runtime/models/sensevoice-small/model.pt')).resolve()
    def load(path,model,**kwargs):
        if Path(path).resolve()!=expected:return original(path,model,**kwargs)
        state=torch.load(str(expected),map_location='cpu',weights_only=True)
        for key in ['state_dict','model_state_dict','model']:
            if key in state:state=state[key]
        target=model.state_dict()
        if set(state)!=set(target) or any(state[k].shape!=target[k].shape for k in target):
            raise RuntimeError('Local SenseVoice checkpoint keys/shapes differ; low-memory loading refused.')
        # Use owned CPU allocations; Windows mmap trials were not stable.
        model.load_state_dict(state,strict=True)
    load._local_low_peak=True;auto_model.load_pretrained_model=load
