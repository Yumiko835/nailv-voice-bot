"""Explicit user ceiling and a separate model-aware ledger for the new style study."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import json,threading,uuid
from pathlib import Path
ROOT=Path(project_path(''))
RATES={setting("chat_model","deepseek-flash"):(2.,8.),'deepseek-v4-pro':(9.,27.)}
PRICING='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
LOCK=threading.Lock()

def authorized_total():
    path=ROOT/'review/调用预算调整-20261024.json'
    if path.exists():
        record=json.loads(path.read_text(encoding='utf-8'))
        if record.get('status')=='explicitly_authorized_by_user' and record.get('authorized_total_cny')==100:return 100.
    return 50.

def events(path):
    result={}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line);result[row['request_id']]=row
    return result

def analysis_spent():return sum(x.get('cost_cny',x['reserved_cny']) for x in events(ROOT/'work/style-study-usage.jsonl').values())

def embedding_spent():return sum(x.get('cost_cny',x['reserved_cny']) for x in events(ROOT/'work/embedding-usage.jsonl').values())

class StudyBudget:
    def __init__(self,stage_cap=5.):self.stage_cap=stage_cap;self.path=ROOT/'work/style-study-usage.jsonl'
    def append(self,row):
        import os
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
    def reserve(self,model,messages,max_tokens,job):
        import extract_nailv_library as engine
        import publish_nailv_library as pub
        rate_in,rate_out=RATES[model]
        bound=len(json.dumps(messages,ensure_ascii=False).encode('utf-8'))+2048
        reserved=(bound*rate_in+max_tokens*rate_out)/1e6
        with LOCK:
            spent=analysis_spent();total=engine.Budget().report()['conservative_upper_cny']+embedding_spent()+spent
            if total+reserved>authorized_total()-.01 or spent+reserved>self.stage_cap:raise RuntimeError('本轮分析或累计调用额度已到上限。')
            row={'request_id':uuid.uuid4().hex,'created_at':pub.now(),'model':model,'job':job,'state':'reserved','reserved_cny':reserved,'input_bound':bound,'max_output_tokens':max_tokens,'rates_peak_cny_per_million':[rate_in,rate_out],'pricing_url':PRICING,'pricing_checked_date':'2026-10-24'}
            self.append(row);return row
    def settle(self,row,usage,returned_model):
        import publish_nailv_library as pub
        p,c=usage.get('prompt_tokens'),usage.get('completion_tokens')
        if not isinstance(p,int) or not isinstance(c,int) or min(p,c)<0:raise RuntimeError('模型未返回可核验用量。')
        rate_in,rate_out=RATES[row['model']];cost=(p*rate_in+c*rate_out)/1e6
        if cost>row['reserved_cny']+.001:raise RuntimeError('模型用量超过调用前预留。')
        with LOCK:self.append({**row,'state':'completed','settled_at':pub.now(),'cost_cny':cost,'usage':usage,'returned_model':returned_model})
