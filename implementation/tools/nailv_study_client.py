"""Bounded offline study calls; only approved public-source tasks and synthetic cases."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import hashlib,json,os,re,urllib.error,urllib.request
from pathlib import Path
import nailv_call_limits as limits

class StudyClient:
    def __init__(self,model=setting("chat_model","deepseek-flash")):
        if model not in limits.RATES:raise ValueError('Unpriced model')
        self.model=model;self.budget=limits.StudyBudget()
        self.key=(os.environ.get('CHAT_API_KEY') or Path(secret_path("CHAT_API_KEY_FILE")).read_text(encoding='utf-8-sig')).strip()
    def call(self,messages,job,max_tokens=4096,temperature=.3):
        import publish_nailv_library as pub
        fp=hashlib.sha256(json.dumps([self.model,messages,max_tokens,temperature,'nonthinking-json-v1'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        path=pub.ROOT/'cache/style-study'/f'{job}-{fp[:16]}.json'
        if path.exists():return json.loads(path.read_text(encoding='utf-8'))
        row=self.budget.reserve(self.model,messages,max_tokens,job)
        body={'model':self.model,'messages':messages,'temperature':temperature,'max_tokens':max_tokens,'thinking':{'type':'disabled'},'response_format':{'type':'json_object'}}
        req=urllib.request.Request(setting("chat_endpoint","https://api.deepseek.com/v1/chat/completions"),data=json.dumps(body,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:data=json.load(response)
            self.budget.settle(row,data.get('usage',{}),data.get('model',''))
            choice=data['choices'][0]
            if choice.get('finish_reason')!='stop':raise RuntimeError('模型输出未完整结束。')
            text=choice['message']['content'].strip()
            if text.startswith('```'):text=re.sub(r'^```(?:json)?\s*','',text).removesuffix('```').strip()
            result={'job':job,'model':self.model,'returned_model':data.get('model'),'created_at':pub.now(),'content':json.loads(text),'usage':data.get('usage',{}),'fingerprint':fp}
            pub.save(str(path.relative_to(pub.ROOT)),result);return result
        except urllib.error.HTTPError as exc:raise RuntimeError('研究调用未完成：HTTP '+str(exc.code)) from None
