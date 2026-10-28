"""Create an isolated local workspace and stage adapted code; no network or models."""
import argparse,json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_config import REPO,ROOT,project_path,configure_cli

def bootstrap(target: Path) -> None:
    target=target.resolve()
    if target==REPO or not target.is_relative_to((REPO/'.local').resolve()):
        raise ValueError('Bootstrap only writes below this checkout .local/; use manual staging for another drive')
    marker=target/'public-workspace.json'
    if target.exists() and any(target.iterdir()) and not marker.exists():
        raise FileExistsError('Refusing to overlay an existing non-public project')
    target.mkdir(parents=True,exist_ok=True)
    for source in (REPO/'implementation').rglob('*'):
        if source.is_file():
            dest=target/source.relative_to(REPO/'implementation');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    os.environ['NAILV_SOURCE_ROOT']=str(REPO)
    style=target/'style/v3.2/表达选段库.json';style.parent.mkdir(parents=True,exist_ok=True)
    if not style.exists():shutil.copy2(REPO/'examples/fictional-style-bank.json',style)
    marker.write_text(json.dumps({'kind':'public_source_workspace','fictional_demo_only':True,'source_root':str(REPO)},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    configure_cli()
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT);args=parser.parse_args()
    bootstrap(args.out)
    print(json.dumps({'created':str(args.out.resolve()),'models_downloaded':0,'cloud_calls':0},ensure_ascii=False))
