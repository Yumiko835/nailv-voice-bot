
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
import collections,hashlib,json,math,re,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'));import publish_nailv_library as p
def canon(text):
    text=re.sub(r'^在\d{4}-\d\d-\d\d对应的录播中[，,]?','',text)
    text=re.sub('明前奶绿|在直播中|在本次直播中|自述|表示|提到|自己|这个|那个|觉得','',text)
    return re.sub(r'[^a-z0-9\u3400-\u9fff]','',text.lower())
def terms(text):
    text=canon(text);return {text[i:i+n] for n in [2,3] for i in range(len(text)-n+1)}
def main():
    pending=p.load('review/self-supplement-20261024/subtitle-pending.json')['items']
    old=p.load('persona/facts.json')['items']+p.load('persona/corpus.json')['items']+p.load('data/self-supplement/items.json')['items']
    posting=collections.defaultdict(list);sets=[]
    for i,x in enumerate(old):
        ts=terms(x['text']);sets.append(ts)
        for t in ts:posting[t].append(i)
    idf={t:math.log(1+len(old)/len(ids)) for t,ids in posting.items()}
    pairs=[];flags=[]
    regs={
      'identity':r'生日|年龄|出生|\d+岁|十九岁|十八岁|二十岁|身高|体重|国籍|真名',
      'pet_timeline':r'(?:坚果|店长).{0,35}(?:去世|死亡|摔死|死了|失踪|喵星|不在|离开|还活)',
      'exclusive_claim':r'从来没|从未|第一次|唯一|只有|从来不|没有谈过|没有去过|没养过',
      'attribution':r'论文致谢|毕业论文.{0,15}花店|观众.{0,15}(?:自己|自述|投稿)|投稿.{0,15}(?:自己|自述)',
      'realm':r'LLL.{0,20}(?:解散|决裂)|同公司|亲姐妹|亲生|已婚|结婚|离婚|精神分裂|双重人格|偷星|偷心九月|莉莉丝.{0,15}漫画',
      'private_detail':r'住址|小区|几楼|楼层|学校名|身份证|电话号|私人联系',
    }
    for x in pending:
        ts=terms(x['text']);scores=collections.defaultdict(float)
        for t in ts:
            if t not in posting or len(posting[t])>len(old)*.08:continue
            for i in posting[t]:scores[i]+=idf[t]
        nearest=[]
        for i,_ in sorted(scores.items(),key=lambda z:-z[1])[:12]:
            overlap=ts&sets[i];den=sum(idf.get(t,1) for t in ts|sets[i]);sim=sum(idf.get(t,1) for t in overlap)/den if den else 0
            nearest.append({'id':old[i]['id'],'text':old[i]['text'],'date':old[i].get('source_record_date'),'similarity':round(sim,4),'same_source':bool({r['source_id'] for r in x['source_refs']}&{r['source_id'] for r in old[i]['source_refs']})})
        nearest=sorted(nearest,key=lambda z:-z['similarity'])[:4]
        cats=[k for k,v in regs.items() if re.search(v,x['text'])]
        obj={'id':x['id'],'text':x['text'],'kind':x['kind'],'date':x['source_record_date'],'scope':x['time_scope'],'entities':x.get('entities',[]),'flags':cats,'quote':x['source_refs'][0]['quote'],'nearest':nearest}
        pairs.append(obj)
        if cats:flags.append(obj)
    p.save('work/conditional-acceptance-20261024/census.json',{'candidate_count':len(pending),'baseline_count':len(old),'flag_counts':dict(collections.Counter(c for x in flags for c in x['flags'])),'pairs':pairs})
    p.save('work/conditional-acceptance-20261024/flagged.json',{'items':flags})
    print(json.dumps({'candidates':len(pending),'baseline':len(old),'flags':dict(collections.Counter(c for x in flags for c in x['flags'])),'flagged_items':len(flags)},ensure_ascii=False))
    for x in flags:
        if any(k in x['flags'] for k in ['identity','pet_timeline','realm','attribution','private_detail']):print(json.dumps({'id':x['id'],'text':x['text'],'flags':x['flags'],'nearest':x['nearest'][:1]},ensure_ascii=False))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
