"""Re-scan every raw cue for self lore, biographical events and public peer relationships."""

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
import collections,hashlib,json,re,sqlite3,sys
R=Path(project_path(''))
OUT=R/'work/self-audit-20261024'
PATTERNS={
 'core_setting':r'永远.{0,8}(?:19|十九)|(?:我|主播).{0,6}(?:19岁|十九岁)|(?:我|主播).{0,8}生日|拉普拉斯|[Ll]aplace|侧写|共感|花店.{0,8}(?:店员|店长|名字)|奶糖花.{0,8}(?:名字|称呼|粉丝)',
 'jianguo':r'坚果|堅果|建国|建果|(?:店长|猫猫|猫咪).{0,12}(?:去世|走了|失踪|走丢|不在|找到|没了|过世|火化)',
 'peers_lll':r'莉莉丝|莉莉斯|莉莉思|莉莉絲|雫露露|雫るる|露露|露璐|[lL][uU][lL][uU]|[lLＬｌ]\s*[lLＬｌ]\s*[lLＬｌ]|三人组|三人組|露莉绿|发卡|李艺彤',
 'own_life_event':r'(?:我|主播).{0,15}(?:辞职|离职|入职|毕业|留学|转行|搬家|停播|复播|出道|首播|初配信|退圈|住院|手术|签约|解约|创立|成立)|(?:我小时候|我初中|我高中|我大学|我以前|我之前).{0,20}(?:读|学|做过|从事|打工|考上|毕业|搬|养)',
}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect('file:'+str(R/'data/raw-index/library.sqlite3').replace('\\','/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    sources={s['id']:dict(s) for s in db.execute('SELECT * FROM sources')}
    hits=collections.defaultdict(list);counts=collections.Counter();rows=0
    regs={k:re.compile(p) for k,p in PATTERNS.items()}
    for row in db.execute('SELECT source_id,ordinal,text FROM cues ORDER BY source_id,ordinal'):
        rows+=1;txt=row['text']
        for topic,reg in regs.items():
            if reg.search(txt):hits[row['source_id']].append((row['ordinal'],topic));counts[topic]+=1
    windows=[];skipped=[]
    for sid,found in hits.items():
        source=sources[sid];source_cues=[dict(x) for x in db.execute('SELECT ordinal,start_ms,end_ms,text FROM cues WHERE source_id=? ORDER BY ordinal',(sid,))]
        by_ord={x['ordinal']:i for i,x in enumerate(source_cues)};ranges=[]
        for ordinal,topic in found:
            i=by_ord[ordinal];lo=max(0,i-7);hi=min(len(source_cues),i+25)
            if ranges and lo<=ranges[-1]['hi'] and hi-ranges[-1]['lo']<=100:
                ranges[-1]['hi']=hi;ranges[-1]['topics'].add(topic)
            else:ranges.append({'lo':lo,'hi':hi,'topics':{topic}})
        for span in ranges:
            selected=source_cues[span['lo']:span['hi']];text='\n'.join(x['text'] for x in selected)
            topics=sorted(span['topics']);has_target=any(t in topics for t in ['core_setting','jianguo','peers_lll'])
            # Thank-you lists and nut/game names remain available in raw research, but not every occurrence warrants extraction.
            only_names=all(re.search(r'谢谢|感謝|感谢|的(?:SC|sc|舰长|店长|点赞|投喂)',source_cues[by_ord[o]]['text']) for o,tp in found if tp in topics and span['lo']<=by_ord[o]<span['hi'])
            if only_names:skipped.append({'source_id':sid,'lo':selected[0]['ordinal'],'reason':'only matching gift/name mentions'});continue
            item={'id':'self-'+sid+'-'+str(selected[0]['ordinal']),'source_id':sid,'record_date':source['date'][:10],'title':source['title'],
                'source_url':source['source_url'],'genre_hint':source['genre'],'topics':topics,
                'lo_ordinal':selected[0]['ordinal'],'hi_ordinal':selected[-1]['ordinal'],
                'cues':selected,'sha256':sha(text)}
            windows.append(item)
    db.close()
    windows.sort(key=lambda x:(0 if 'core_setting' in x['topics'] else 1 if 'jianguo' in x['topics'] else 2 if 'peers_lll' in x['topics'] else 3,x['record_date'],x['source_id'],x['lo_ordinal']))
    (OUT/'windows.json').write_text(json.dumps({'items':windows},ensure_ascii=False),encoding='utf-8')
    report={'raw_cues_scanned':rows,'source_records':len(sources),'nonempty_records':sum(s['status']=='ok' for s in sources.values()),'cue_hits_by_topic':dict(counts),
        'context_windows':len(windows),'window_topics':dict(collections.Counter(t for x in windows for t in x['topics'])),'skipped_name_only_windows':len(skipped),
        'coverage_note':'Every raw cue searched with listed patterns; only matching contextual spans sent for focused extraction. Not an assertion that all biographical statements have been found.',
        'patterns':PATTERNS}
    (OUT/'scan-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    # Readable targeted chronological evidence for the two concrete omissions.
    targeted=[x for x in windows if 'core_setting' in x['topics'] or ('jianguo' in x['topics'] and '2025'<=x['record_date']<'2026')]
    (OUT/'core-and-jianguo-evidence.txt').write_text('\n\n'.join(x['id']+' '+x['record_date']+' '+x['title']+'\n'+'\n'.join(f"[{i}] {c['text']}" for i,c in enumerate(x['cues'])) for x in targeted),encoding='utf-8')
if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
