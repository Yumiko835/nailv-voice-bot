
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
import os,sys,json,subprocess,importlib.metadata as md
from packaging.requirements import Requirement
from packaging.markers import default_environment
R=Path(project_path('runtime/cosyvoice2'))
os.environ.update(UV_CACHE_DIR=str(R/'cache/uv'),PIP_CACHE_DIR=str(R/'cache/pip'),TEMP=str(R/'cache/tmp'),TMP=str(R/'cache/tmp'),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
uv=Path(dependency_path("optional_source",'uv.exe'))
roots=json.loads((R/'dependency-request.json').read_text(encoding='utf-8'))['packages']
def install(requirements):
    subprocess.run([str(uv),'pip','install','--python',sys.executable,'--index-url','https://pypi.org/simple','--no-deps','--no-build-isolation',*requirements],check=True)
install(roots)
environment=default_environment();environment['extra']=''
for round in range(10):
    pending=[Requirement(r).name for r in roots];seen=set();missing={}
    while pending:
        name=pending.pop()
        if name.lower() in seen:continue
        seen.add(name.lower())
        try:dist=md.distribution(name)
        except md.PackageNotFoundError:missing[name]=name;continue
        for spec in dist.requires or []:
            requirement=Requirement(spec)
            if requirement.marker and not requirement.marker.evaluate(environment):continue
            try:version=md.version(requirement.name)
            except md.PackageNotFoundError:version=None
            if version is None or not requirement.specifier.contains(version,prereleases=True):
                assert requirement.name.lower() not in ['torch','torchaudio','transformers','numpy'],'Do not replace shared inference foundations: '+spec
                missing[requirement.name]=str(requirement)
            else:pending.append(requirement.name)
    if not missing:break
    print(json.dumps({'dependency_round':round+1,'missing':list(missing.values())}),flush=True)
    install(list(missing.values()))
else:raise RuntimeError('Dependency closure did not converge')
receipt={name:{'version':md.version(name),'root':str(md.distribution(name).locate_file(''))} for name in sorted(seen)}
(R/'installed-dependencies.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'dependencies_ready':len(receipt),'torch':md.version('torch'),'torch_path':str(md.distribution('torch').locate_file(''))}),flush=True)
