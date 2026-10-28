"""Offline source-package checks; narrow heuristics, not a complete secret scanner."""
import ast,hashlib,json,re,subprocess,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
BINARY={'.pt','.pth','.ckpt','.onnx','.safetensors','.wav','.mp3','.flac','.silk','.db','.sqlite3','.exe','.dll','.node','.zip','.key','.pem'}
IGNORE={'.git','.local','.venv','__pycache__','.pytest_cache'}

def files():
    result=subprocess.run(['git','ls-files','-z'],cwd=REPO,capture_output=True)
    if result.returncode==0 and result.stdout:
        return [REPO/p for p in result.stdout.decode('utf-8').split('\0') if p]
    return [p for p in REPO.rglob('*') if p.is_file() and not any(part in IGNORE for part in p.relative_to(REPO).parts)]

def check():
    errors=[];count=0
    for p in files():
        rel=p.relative_to(REPO).as_posix();count+=1
        if p.is_symlink():errors.append(rel+': symlink is not an auditable source file');continue
        if p.suffix.lower() in BINARY or p.stat().st_size>2*1024**2:errors.append(rel+': binary/private/oversized file');continue
        if p.name.startswith('.env') and p.name!='.env.example':errors.append(rel+': local environment file');continue
        text=p.read_text(encoding='utf-8-sig')
        if re.search(r'(?i)(?:[A-Z]:[\\/](?:Users|QQBot|codex)[\\/])',text):errors.append(rel+': workstation-specific absolute path')
        if re.search(r'(?i)(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',text):errors.append(rel+': possible credential')
        if p.suffix=='.py':
            try:ast.parse(text,filename=rel)
            except SyntaxError as e:errors.append(rel+': '+str(e))
        if p.suffix=='.json':
            try:json.loads(text)
            except ValueError as e:errors.append(rel+': '+str(e))
    manifest=REPO/'source-manifest.json'
    if manifest.exists():
        for item in json.loads(manifest.read_text(encoding='utf-8'))['files']:
            p=REPO/item['path']
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['release_sha256']:errors.append(item['path']+': adapted source manifest mismatch')
    return {'passed':not errors,'files_checked':count,'errors':errors,'scope':'syntax/JSON/known-risk paths and patterns; not a proof of no secret or of runtime audio quality','network_calls':0}

if __name__=='__main__':
    result=check();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
