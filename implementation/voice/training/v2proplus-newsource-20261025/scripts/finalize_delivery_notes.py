
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
path=T/'使用说明.md';text=path.read_text(encoding='utf-8');text=text.replace('共10种情绪、11段参考。','共10种情绪，10段启用参考；另1段口癖备用条保留但暂不启用。').replace('| 开心兴奋 · 口癖备用 |','| 开心兴奋 · 口癖备用（留档，暂不启用） |');path.write_text(text,encoding='utf-8')
proof=read(T/'delivery-verification.json');assert proof['all11_test_players_available'] and proof['real_online_manual_prefix_override_passed'];verify_protected()
for p in Path(__file__).parent.iterdir():
 if p.suffix in ['.py','.js','.html']:shutil.copy2(p,T/'scripts'/p.name)
write(T/'delivery-ready.json',{'both_stages_complete':True,'GPT_epochs':10,'SoVITS_epochs':10,'default_GPT_epoch':6,'default_SoVITS_epoch':10,'active_emotions':10,'active_existing_references':10,'preserved_disabled_optional_reference':1,'listening_samples':11,'source_audio_text_and_V5_models_unchanged':True,'online_generation_verified':True,'human_audio_quality_pending':True,'instructions':str(path)})
print(json.dumps(read(T/'delivery-ready.json'),ensure_ascii=False))
