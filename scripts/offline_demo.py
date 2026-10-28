"""Exercise the actual act-aware style retriever with fictional, non-audio examples."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_config import REPO
sys.path.insert(0,str(REPO/'implementation/tools'))
import nailv_style3 as style

def run():
    with tempfile.TemporaryDirectory(prefix='nailv-offline-') as folder:
        target=Path(folder)/'style/v3.2/表达选段库.json';target.parent.mkdir(parents=True)
        target.write_bytes((REPO/'examples/fictional-style-bank.json').read_bytes())
        original=style.ROOT
        try:
            style.ROOT=Path(folder)
            output=[]
            for question in ['妈妈妈妈','妈妈，我今天没考好。','考试通过了，快夸我。']:
                cards=style.rank(question,[],24)
                output.append({'question':question,'heuristic_act':style.input_act(question),'candidate_ids':[x['id'] for x in cards],'LLM_called':False,'voice_generated':False})
            return output
        finally:style.ROOT=original

if __name__=='__main__':print(json.dumps({'demo':'fictional examples, actual retriever','results':run(),'cloud_calls':0},ensure_ascii=False,indent=2))
