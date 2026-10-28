"""Portable public configuration. Never imports a GPU model or contacts a service."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent

def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key=key.strip();value=value.strip()
        if not key.replace('_','').isalnum():
            raise ValueError('Invalid environment variable name in .env')
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":
            value=value[1:-1]
        os.environ.setdefault(key,value)

load_env(REPO/'.env')
ROOT = Path(os.environ.get('NAILV_DATA_ROOT') or REPO/'.local/project').expanduser().resolve()

def project_path(relative: str='') -> Path:
    value=(ROOT/relative).resolve()
    if not value.is_relative_to(ROOT):
        raise ValueError('Project path escapes NAILV_DATA_ROOT')
    return value

def setting(name: str, default: str='') -> str:
    return os.environ.get('NAILV_'+name.upper(),default)

def dependency_path(name: str, relative: str='') -> Path:
    defaults={
        'gpt_sovits':REPO/'.local/deps/GPT-SoVITS',
        'ffmpeg':REPO/'.local/deps/ffmpeg/bin/ffmpeg.exe',
        'optional_source':REPO/'.local/optional-source',
    }
    base=Path(os.environ.get('NAILV_'+name.upper()+'_ROOT') or defaults.get(name,REPO/'.local/deps'/name)).expanduser().resolve()
    return base/relative

def secret_path(variable: str) -> Path:
    value=os.environ.get(variable)
    if not value:
        raise RuntimeError(variable+' is not configured; use an environment key or an external secret file')
    return Path(value).expanduser().resolve()

def metadata() -> dict:
    return {'source_root':str(REPO),'data_root':str(ROOT),'private_keys_printed':False}

def configure_cli() -> None:
    """Chinese JSON must also work on Western Windows redirected consoles."""
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8')
