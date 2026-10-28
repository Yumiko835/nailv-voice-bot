
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
import bisect,collections,importlib.util,json,re,sqlite3,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'))
import publish_nailv_library as p
OUT=R/'work/self-audit-extra-20261024'
PATTERNS={
 'other_public_peers':r'我(?:和|跟|认识|见过|约了|联系).{0,18}|七海|阿梓|米拉|灰泽满|林忆宁|梨安|安珂',
 'other_self_history':r'我(?:以前|之前|小时候|从小|曾经|后来|当时|那时候|那个时候|家里|去过|养过|毕业|大学|高中)|(?:以前|当时|那时候|小时候|后来|去年|前年)我',
 'career_milestone':r'首播|初配信|出道|休播|复播|开播纪念|周年|第一次直播|第一天直播|(?:我|主播).{0,8}播了.{0,6}年',
 'pet_loss_context':r'猫.{0,12}(?:死|走了|离开|不在|摔|坠|丢|窗|找|尸)|(?:店长|猫).{0,8}喵星',
}
def scan():
    OUT.mkdir(parents=True,exist_ok=True)
    old=p.load('work/self-audit-20261024/windows.json')['items'];covered=collections.defaultdict(list)
    for w in old:covered[w['source_id']].append((w['lo_ordinal'],w['hi_ordinal']))
    regs={k:re.compile(v) for k,v in PATTERNS.items()};hits=collections.defaultdict(list);count=collections.Counter();total=skipped=0
    db=sqlite3.connect('file:'+str(R/'data/raw-index/library.sqlite3').replace('\\','/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    sources={x['id']:dict(x) for x in db.execute('SELECT * FROM sources')}
    for row in db.execute('SELECT source_id,ordinal,text FROM cues ORDER BY source_id,ordinal'):
        total+=1;topics=[k for k,reg in regs.items() if reg.search(row['text'])]
        if not topics:continue
        if any(lo<=row['ordinal']<=hi for lo,hi in covered[row['source_id']]):skipped+=1;continue
        for t in topics:count[t]+=1;hits[row['source_id']].append((row['ordinal'],t))
    windows=[]
    for sid,found in hits.items():
        s=sources[sid];cues=[dict(x) for x in db.execute('SELECT ordinal,start_ms,end_ms,text FROM cues WHERE source_id=? ORDER BY ordinal',(sid,))];pos={x['ordinal']:i for i,x in enumerate(cues)};ranges=[]
        for ordinal,topic in found:
            i=pos[ordinal];lo=max(0,i-9);hi=min(len(cues),i+32)
            if ranges and lo<=ranges[-1]['hi'] and hi-ranges[-1]['lo']<=100:ranges[-1]['hi']=hi;ranges[-1]['topics'].add(topic)
            else:ranges.append({'lo':lo,'hi':hi,'topics':{topic}})
        for span in ranges:
            selected=cues[span['lo']:span['hi']]
            windows.append({'id':'extra-'+sid+'-'+str(selected[0]['ordinal']),'source_id':sid,'record_date':s['date'][:10],'title':s['title'],'source_url':s['source_url'],
                'genre_hint':s['genre'],'topics':sorted(span['topics']),'lo_ordinal':selected[0]['ordinal'],'hi_ordinal':selected[-1]['ordinal'],'cues':selected})
    db.close();p.save('work/self-audit-extra-20261024/windows.json',{'items':windows})
    report={'raw_cues_rescanned':total,'previously_covered_matching_cues_skipped':skipped,'new_windows':len(windows),'new_window_topics':dict(count),'patterns':PATTERNS,
        'scope':'Broader self history and all public peers, not limited to named examples. Matching spans only, not a claim all statements were semantically exhausted.'}
    p.save('work/self-audit-extra-20261024/scan-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
def run_module(name,file):
    spec=importlib.util.spec_from_file_location(name,str(R/'tools'/file));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    scan()
    module=run_module('self_more_extract','extract_nailv_self.py');module.OUT=OUT
    # Save functions use fixed relative destinations in the base script; rewrite only this isolated module's save wrapper.
    original_save=module.p.save
    def redirected_save(path,data):return original_save(path.replace('work/self-audit-20261024/','work/self-audit-extra-20261024/'),data)
    module.p.save=redirected_save
    module.PROMPT=module.PROMPT.replace('重点：','重点（不限于用户举例）：') if '重点：' in module.PROMPT else module.PROMPT
    module.PROMPT+='\n本批已扩展到其他人物与经历。所有明确出现的公开主播同行、朋友和合作对象都可记，不只收莉莉丝、露露或LLL。童年、求学、工作、旅行、生活习惯、角色形象、直播发展等具体自述均可；前述排除归属错误和私密信息的规则保持。不要根据日V玩笑推断真实国籍，不根据角色年龄推算真人身份。'
    module.main()
