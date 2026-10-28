
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
import shutil,ast
HERE=Path(__file__).parent
for p in HERE.iterdir():
 if p.suffix in ['.py','.js','.html']:shutil.copy2(p,T/'scripts'/p.name)
shutil.copy2(HERE/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py');shutil.copy2(HERE/'voice-proplus.html',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html');server=ROOT/'tools/nailv_text_server.py';backup=T/'before-server-update';backup.mkdir(exist_ok=True)
if not (backup/server.name).exists():shutil.copy2(server,backup/server.name)
s=server.read_text(encoding='utf-8')
if 'import nailv_proplus_voice as proplus_voice' not in s:
 s=s.replace('import nailv_newsource_voice as newsource_voice','import nailv_newsource_voice as newsource_voice\nimport nailv_proplus_voice as proplus_voice')
 needle="            elif self.path=='/voice-newsource':";assert needle in s
 routes="            elif self.path=='/voice-proplus':self.send((core.ROOT/'outputs/奶绿V2ProPlus双阶段语音.html').read_text(encoding='utf-8'),html=True)\n            elif self.path=='/api/voice-proplus/status':self.send(proplus_voice.status())\n            elif self.path.startswith('/api/voice-proplus/job/'):\n                try:self.send(proplus_voice.job(self.path.rsplit('/',1)[-1]))\n                except ValueError as exc:self.send({'error':str(exc)},404)\n            elif self.path.startswith('/voice-proplus-media/'):self.send_media('/voice-proplus-media/',proplus_voice.media_files())\n"
 s=s.replace(needle,routes+needle)
 needle="                elif self.path=='/api/voice-newsource/generate':";assert needle in s;s=s.replace(needle,"                elif self.path=='/api/voice-proplus/generate':self.send(proplus_voice.start_job(data))\n"+needle)
 old="('新素材V5Dev训练与试听.html' if newsource_voice.status()['active_default'] else '奶绿V5Dev混合语音.html')";assert old in s;s=s.replace(old,"('奶绿V2ProPlus双阶段语音.html' if proplus_voice.status()['ready'] else '新素材V5Dev训练与试听.html' if newsource_voice.status()['active_default'] else '奶绿V5Dev混合语音.html')")
ast.parse(s);server.write_text(s,encoding='utf-8');print('http://127.0.0.1:49850/voice-proplus')
