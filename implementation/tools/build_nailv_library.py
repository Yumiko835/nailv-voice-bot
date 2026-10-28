"""Build a provenance-preserving local subtitle research database; no network calls."""
from __future__ import annotations

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import collections,hashlib,json,re,sqlite3,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path

PROJECT=Path(project_path(''))
MATERIALS=PROJECT.parent/'素材/mingqian-nailv-zimu-20261023'
SKILL=Path(dependency_path("optional_source",'character-bot-builder'))

def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.part');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def genre(title):
    if re.search(r'一起看|看片|看番|看电影|解说|鉴赏|黑袍|jojo|JOJO|炎拳|海猫',title):return 'watchalong',-30
    if re.search(r'歌回|歌会|唱歌|演唱|点歌|歌曲|粉丝歌',title):return 'music',-15
    if re.search(r'杂谈|电台|聊天|闲聊|生日|周年|千舰|新衣|新装|百日|见面|故事',title):return 'talk',30
    if re.search(r'游戏|玩|推理|恐怖|鬼武者|怪猎|黑神话|之王|三国|迷宫',title):return 'game',0
    return 'unspecified',10
def windows(cues,max_chars=15000,max_cues=1500,overlap=35):
    lo=0;order=0
    while lo<len(cues):
        hi=lo;size=0
        while hi<len(cues) and hi-lo<max_cues:
            extra=len(cues[hi]['text'])
            if hi>lo and size+extra>max_chars:break
            size+=extra;hi+=1
        text='\n'.join(x['text'] for x in cues[lo:hi])
        signals=sum(text.count(x) for x in ['我喜欢','我不喜欢','我小时候','我以前','我记得','我觉得','你们说','你说','问我','为什么','什么意思','你们不要','我真的'])
        yield lo,hi,size,order,signals
        if hi>=len(cues):break
        lo=max(lo+1,hi-min(overlap,max(0,(hi-lo)//4)));order+=1

def build():
    started=time.monotonic()
    if PROJECT.exists():raise FileExistsError('Project already exists; build is not an overwrite operation')
    sys.path.insert(0,str(SKILL/'scripts'))
    from init_project import create_project
    create_project(PROJECT,'new-milkgreen','明前奶绿（新项目）')
    config=json.loads((PROJECT/'project.json').read_text(encoding='utf-8'))
    config['phase']='raw-index-and-candidate-review'
    config['features'].update(text=False,retrieval=False,voice=False)
    config['models']['chat'].update(provider='DeepSeek',model=setting("chat_model","deepseek-flash"),base_url='https://api.deepseek.com/v1')
    config['budget']={'authorized_cny':50,'pricing_source':'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/','pricing_checked_date':'2026-10-23','model':setting("chat_model","deepseek-flash"),'off_peak_cny_per_million':{'cache_hit':.02,'cache_miss':1.,'output':4.},'peak_cny_per_million':{'cache_hit':.04,'cache_miss':2.,'output':8.},'reserve_safety_cny':1.,'note':'Paid extraction separate from local raw index; no automatic bot deployment.'}
    config['raw_search']={'backend':'sqlite-fts5-trigram','path':'data/raw-index/library.sqlite3','scope':'research-only, unreviewed ASR, not production character memory'}
    save(PROJECT/'project.json',config)
    dbpath=PROJECT/'data/raw-index/library.sqlite3';dbpath.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(dbpath)
    db.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA temp_store=MEMORY;
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE sources(id TEXT PRIMARY KEY,clip_id INTEGER UNIQUE,title TEXT,date TEXT,source_url TEXT,srt_url TEXT,status TEXT,genre TEXT,priority INTEGER,cue_count INTEGER,character_count INTEGER,transcript_path TEXT);
    CREATE TABLE cues(source_id TEXT NOT NULL,ordinal INTEGER NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,text TEXT NOT NULL,PRIMARY KEY(source_id,ordinal)) WITHOUT ROWID;
    CREATE TABLE chunks(id INTEGER PRIMARY KEY,source_id TEXT NOT NULL,lo INTEGER,hi INTEGER,start_ms INTEGER,end_ms INTEGER,text TEXT NOT NULL,sha256 TEXT NOT NULL,flags TEXT NOT NULL);
    CREATE INDEX chunks_source ON chunks(source_id,lo);
    CREATE VIRTUAL TABLE chunks_fts USING fts5(text,content='chunks',content_rowid='id',tokenize='trigram');
    CREATE TABLE windows(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,lo INTEGER,hi INTEGER,characters INTEGER,window_order INTEGER,signals INTEGER,genre TEXT,priority INTEGER);
    CREATE INDEX windows_priority ON windows(genre,window_order,signals);
    ''')
    all_sources=[];source_counts=collections.Counter();cue_count=chunk_count=window_count=character_count=0
    catalog=json.loads((MATERIALS/'catalog.json').read_text(encoding='utf-8'))
    manifest={r['clip_id']:r for r in json.loads((MATERIALS/'manifest.json').read_text(encoding='utf-8'))}
    for raw in catalog['items']:
        row=manifest[raw['id']];sid=f"zimu-{raw['id']}";kind,priority=genre(raw['title'])
        rel=f'sources/transcripts/{sid}.txt'
        db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(sid,raw['id'],raw['title'],raw['datetime'],row['source_url'],row['srt_url'],row['status'],kind,priority,row.get('cue_count',0),row.get('character_count',0),rel))
        all_sources.append({'id':sid,'kind':'livestream_asr','title':raw['title'],'origin':row['source_url'],'srt_url':row['srt_url'],'record_date':raw['datetime'],'transcript_path':rel,'raw_srt_path':str(MATERIALS/row['srt_path']),'speaker_separated':False,'source_genre_hint':kind,'review':'draft','status':row['status'],'notes':'机器转写；未核对说话人。日期为来源网站记录日期，00:00:00不是已核实的开播时刻。片名分类只是筛选线索。'})
        if row['status']=='empty':(PROJECT/rel).write_text('',encoding='utf-8')
    db.commit();source_lookup={x['id']:x for x in all_sources}
    with (MATERIALS/'明前奶绿_带来源字幕.jsonl').open(encoding='utf-8') as file:
        for n,line in enumerate(file,1):
            record=json.loads(line);sid=record['source_id'];cues=record['segments'];src=source_lookup[sid];kind,priority=genre(record['title'])
            plain='\n'.join(x['text'] for x in cues)
            (PROJECT/src['transcript_path']).write_text(plain+'\n',encoding='utf-8')
            source_counts[kind]+=1;cue_count+=len(cues);character_count+=len(plain)
            db.executemany('INSERT INTO cues VALUES (?,?,?,?,?)',((sid,i,x['start_ms'],x['end_ms'],x['text']) for i,x in enumerate(cues)))
            lo=0;size=0
            def add_chunk(a,b):
                nonlocal chunk_count
                text='\n'.join(x['text'] for x in cues[a:b])
                flags=['unreviewed_asr','speaker_not_separated']
                if kind in ('watchalong','music','game'):flags.append('source_'+kind)
                if len(re.sub(r'\s+','',text))<30:flags.append('low_information')
                cur=db.execute('INSERT INTO chunks(source_id,lo,hi,start_ms,end_ms,text,sha256,flags) VALUES (?,?,?,?,?,?,?,?)',(sid,a,b,cues[a]['start_ms'],cues[b-1]['end_ms'],text,hashlib.sha256(text.encode()).hexdigest(),json.dumps(flags)))
                db.execute('INSERT INTO chunks_fts(rowid,text) VALUES (?,?)',(cur.lastrowid,text));chunk_count+=1
            for i,cue in enumerate(cues):
                gap=cue['start_ms']-cues[i-1]['end_ms'] if i else 0
                if i>lo and (size+len(cue['text'])>1800 or cue['end_ms']-cues[lo]['start_ms']>180000 or gap>15000):add_chunk(lo,i);lo=i;size=0
                size+=len(cue['text'])+1
            if cues:add_chunk(lo,len(cues))
            for a,b,size,order,signals in windows(cues):
                wid=f'{sid}-w{order:03d}'
                db.execute('INSERT INTO windows VALUES (?,?,?,?,?,?,?,?,?)',(wid,sid,a,b,size,order,signals,kind,priority));window_count+=1
            if n%50==0:
                db.commit();print(json.dumps({'stage':'local_index','records':n,'total':1631,'cues':cue_count,'chunks':chunk_count},ensure_ascii=False),flush=True)
    db.execute("INSERT INTO metadata VALUES ('scope',?)",('unreviewed source research database; not approved persona facts',))
    db.execute("INSERT INTO metadata VALUES ('schema_version','1')")
    db.execute("INSERT INTO metadata VALUES ('created_at',?)",(now(),))
    db.commit();db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')");db.commit()
    assert db.execute('SELECT count(*) FROM sources').fetchone()[0]==1635
    assert db.execute('SELECT count(*) FROM cues').fetchone()[0]==2757563
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    example=db.execute('SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?',('"我喜欢"',)).fetchone()[0]
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('PRAGMA journal_mode=DELETE');db.close()
    save(PROJECT/'sources/manifest.json',{'schema_version':1,'sources':all_sources})
    stats={'created_at':now(),'source_records':len(all_sources),'records_with_text':sum(source_counts.values()),'empty_records':4,'cue_count':cue_count,'text_characters':character_count,'chunk_count':chunk_count,'extraction_windows':window_count,'genre_hints':dict(source_counts),'search_smoke_test_matches':example,'build_seconds':round(time.monotonic()-started,2),'database_bytes':dbpath.stat().st_size,'scope':'all source text searchable; no source is automatically approved as the streamer speaking'}
    save(PROJECT/'outputs/全文底库报告.json',stats)
    print(json.dumps({'stage':'local_index_complete','report':stats,'project':str(PROJECT)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    build()
