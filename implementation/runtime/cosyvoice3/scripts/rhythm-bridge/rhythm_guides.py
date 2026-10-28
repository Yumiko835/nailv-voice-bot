"""Try three unchanged-model GPT seeds for a clearer S02 rhythm guide."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import sys, subprocess
from pathlib import Path
support = Path(__file__).parent.parent / 'cosyvoice3-20261026'
if not (support / 'common.py').exists(): support = Path(__file__).parent.parent
sys.path.insert(0, str(support))
from common import *
setup()
sys.path.insert(0, str(OLD_R / 'scripts'))
import cosy_chat_backend as coordination
G = ROOT / 'voice/training/v2proplus-newsource-20261025'
H = G / 'rhythm-bridge-20261026'
case = next(r for r in read(O / 'cross-engine-20261026/plain-requests.json')['samples'] if r['id'] == 'S02')
requests = {'samples': [case | {'id': f'S02-guide-{seed}', 'base_case': 'S02', 'seed': seed,
                               'temperature': .85, 'repetition_penalty': 1.35} for seed in [1942, 2942, 3942]]}
write(H / 'requests.json', requests)
flags = {'check': True, 'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
if not (H / 'generated/manifest.json').exists():
    with coordination.gpu_lease('rhythm-bridge-clearer-GPT-guide'):
        subprocess.run([str(ROOT.parent.parent / dependency_path("gpt_sovits",'.venv/Scripts/python.exe')),
                        '-B', str(G / 'scripts/synthesize.py'), '--requests', str(H / 'requests.json'),
                        '--reference-manifest', str(G / 'cross-engine-20261026/reference-manifest.json'),
                        '--out', str(H / 'generated')], **flags)
subprocess.run([str(OLD_R / '.venv/Scripts/python.exe'), '-B', str(R / 'scripts/audio_critic.py'),
                '--manifest', str(H / 'generated/manifest.json'), '--out', str(H / 'critic')], **flags)
