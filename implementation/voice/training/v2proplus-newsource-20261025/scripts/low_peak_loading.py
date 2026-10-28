"""Process-local load-order fix. Same final FP16 tensors, no source/model-file edits."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import inspect,textwrap,hashlib

def install(engine):
    records=[]
    for name in ['init_vits_weights','init_t2s_weights','init_bert_weights','init_cnhuhbert_weights']:
        original=textwrap.dedent(inspect.getsource(getattr(engine.TTS,name)))
        source=original
        # Avoid the temporary full-FP32 GPU copy immediately before .half().
        source=source.replace('.to(self.configs.device)',
            '.to(device=self.configs.device, dtype=(torch.float16 if self.configs.is_half and str(self.configs.device)!="cpu" else torch.float32))')
        if name=='init_t2s_weights':
            source=source.replace('map_location=self.configs.device, weights_only=False','map_location="cpu", weights_only=False')
        if name=='init_bert_weights':
            source=source.replace('AutoModelForMaskedLM.from_pretrained(base_path)',
                'AutoModelForMaskedLM.from_pretrained(base_path, torch_dtype=(torch.float16 if self.configs.is_half and str(self.configs.device)!="cpu" else torch.float32))')
        assert source!=original, 'Load-order hook did not match the installed engine: '+name
        namespace={};exec(compile(source,'<newsource-low-peak-loading:'+name+'>','exec'),engine.__dict__,namespace)
        setattr(engine.TTS,name,namespace[name])
        records.append({'method':name,'original_source_sha256':hashlib.sha256(original.encode()).hexdigest(),'process_local_source_sha256':hashlib.sha256(source.encode()).hexdigest()})
    return {'applied':True,'purpose':'Avoid temporary FP32 CUDA copies; retain the same final FP16 inference precision','weights_changed_on_disk':False,'shared_GPT_SoVITS_source_changed':False,'methods':records}
