
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
import shutil
HERE=Path(__file__).parent
source=(A/'scripts/nailv_audio_export.py').read_text(encoding='utf-8').replace('NATIVE_SR=48000','NATIVE_SR=32000').replace("PIPELINE_REVISION='v5dev-native-pcm-edgefade-microgate-v3'","PIPELINE_REVISION='proplus-native-32k-pcm24-v1'").replace('sr not in [44100,NATIVE_SR]','sr not in [44100,48000,NATIVE_SR]').replace('frame=960','frame=640').replace('lead=7680;tail=15360','lead=5120;tail=10240').replace('V5 Dev','V2 ProPlus')
(HERE/'nailv_audio_export.py').write_text(source,encoding='utf-8')
for name in ['emotion_routing.py','nailv_connected_frontend.py','reference_micro_gate.py','low_peak_loading.py']:
 shutil.copy2(A/'scripts'/name,HERE/name)
for p in HERE.iterdir():
 if p.suffix in ['.py','.js']:shutil.copy2(p,T/'scripts'/p.name)
print('ProPlus native32k export and existing emotion router prepared.')
