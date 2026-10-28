
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(project_path(''));sys.path.insert(0,str(ROOT/'tools'));import publish_nailv_library as p
db=sqlite3.connect('file:'+str(ROOT/'data/raw-index/library.sqlite3').replace('\\','/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
items=[]
def add(key,sid,start,end,text,tags,min_gap=0):
    source=dict(db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone())
    first=db.execute('SELECT ordinal FROM cues WHERE source_id=? AND instr(text,?)>0 ORDER BY ordinal LIMIT 1',(sid,start)).fetchone();assert first,(key,start)
    last=db.execute('SELECT ordinal FROM cues WHERE source_id=? AND ordinal>=? AND instr(text,?)>0 ORDER BY ordinal LIMIT 1',(sid,first[0]+min_gap,end)).fetchone();assert last,(key,end)
    assert last[0]-first[0]<160
    cues=[dict(v) for v in db.execute('SELECT ordinal,start_ms,end_ms,text FROM cues WHERE source_id=? AND ordinal>=? AND ordinal<=?',(sid,first[0],last[0]))]
    items.append({'id':'fact-relation-xingtong-'+key,'kind':'relationship_response','text':text,'entities':['明前奶绿','星瞳'],'time_scope':'historical','source_record_date':source['date'][:10],'event_date':None,'topics':['星瞳',*tags],'review':'approved','review_method':'editorial inspection of the exact primary subtitle span and SC/response boundary; requested relationship supplement','user_request':'奶绿与星瞳的关系目前还缺少，比如别人炒他俩cp的回应之类的','audio_verified':False,'active_in_text_pilot':True,'source_refs':[{'source_id':sid,'quote':'\n'.join(v['text'] for v in cues),'start_seconds':cues[0]['start_ms']/1000,'end_seconds':cues[-1]['end_ms']/1000,'origin':source['source_url']}],'source_cue_range':[first[0],last[0]],'tags':tags,'uncertainty':'只支持该次公开表述，不推断今天的私下关系。'})
add('distance','zimu-128336','我的愤怒','其实就是不熟悉','2025-11-23谈到星瞳时，她说自己并没有实际接触、了解过对方，谈不上很生气或很讨厌。她区分了粉丝之间的摩擦和自己对星瞳本人的情绪，明确说其实不熟悉。',['概况','熟悉','讨厌','愤怒'])
add('social-effort','zimu-128336','之后就是你问我说有没有可能','所以就算了吧','2025-11-23她说之后与星瞳有联系当然有可能，但想到认识后可能要处理的后续情绪与矛盾，处理成本大过当时交朋友的欲望，因此觉得维持当时状态也挺好。不是宣布永远不往来。',['认识','联动','概况'])
add('past-contact','zimu-96718','之前星瞳','最近两个月也没找过我','2025-05-02回答联动传闻时，她提到以前找过、有联系方式，但没有确认近期新联系或确定的联动安排。这是当时的对接情况，不证明今天私交或同一公司关系。',['联系','联动'])
add('bw','zimu-84174','星瞳','还是熟悉的小电视','2024-07-13逛展看到星瞳相关展台时，她说主要怕大家吵架，选择换一下、走开。不能把回避引战推成两人有私仇。',['展台','BW','吵架'])
add('song','zimu-85207','能不能放一下','不可以出现同事听歌','2025-01-31有人点星瞳翻唱《没那么简单》，她以直播间不放同事的歌作回应。该处“同事”不证明在同一家公司，也不证明她讨厌星瞳。',['点歌','歌曲'])
add('bad-edit','zimu-131268','最让我生气','睡不着','2026-01-01她生气的是切片把前后两条不同SC剪在一起：前一条是说下播后看看，后一条是观众点AI张顺飞《绝不认输》。她明确反问这和星瞳是不是一个事，否认点歌是在对星瞳宣战。',['绝不认输','剪辑','宣战','断章取义'])
add('dont-cue','zimu-131703','这个恨也迷人','心之壁来的','2026-01-08她认出“恨也迷人”是星瞳那边的梗，要求观众别总在她直播间cue对方、带节奏和拷打人。',['带节奏','cue','恨也迷人'])
add('dont-brigade','zimu-131868','不要再带节奏了','全是你们的问题','2026-01-10面对把点歌解释成攻击星瞳的起哄，她再次说不要带节奏，并提醒观众别把对方弄破防。她没有承认攻击星瞳的意图。',['带节奏','攻击','保护'])
add('cp-headache','zimu-134459','难怪奶糖花喜欢整绿瞳CP','脑瓜子更疼','2026-02-19读到观众把她喜欢拉郎配与奶糖花炒绿瞳CP联系起来的SC，她叹气说想到大家就脑瓜子疼。该回应不构成承认真实CP。',['CP','拉郎','起哄'])
add('cp-imagination','zimu-135372','在微博上暗戳戳的留下对绿瞳的怀念','我真服了','2026-03-07面对所谓会在微博留下绿瞳怀念的SC，她吐槽观众“在大脑里面就已经过完了一生”，没有承认恋爱、分手或怀念的故事。',['CP','脑补','怀念','分手'])
add('cp-choice','zimu-135370','绿瞳还是卡黄','我绝对不招','2026-03-08被观众问“绿瞳还是卡黄”二选一时，她用夸张玩笑拒答，明确说“我不回答”“我绝对不招”。拒答不等于暗示真实恋爱关系。',['CP','二选一','卡黄'])
add('cp-fire','zimu-140826','已经捏了个星瞳','看不懂','2026-04-19观众在SC里想象绿瞳见面会摩擦出爱的火花，她只回“看不懂”，没有确认SC中的联动或恋爱想象。',['CP','火花','见面'])
add('nickname','zimu-155996','谢奶绿星瞳和好了','一视同仁好吧','2026-10-22出现的“奶绿星瞳和好了”是她谢SC时读到的观众昵称，随后是相亲收费的提问，不是她宣布和好。昵称和读SC不能当成本人关系表态。',['和好','昵称','SC'])
db.close()
p.save('data/relationships-xingtong/items.json',{'version':'xingtong-source-responses-20261024','created_at':p.now(),'items':items,'note':'Primary subtitle spans inspected; publicly stated historical responses, not inferred private relationships. Unchecked clip titles and ASR-unclear P-picture line were excluded.'})
p.save('outputs/星瞳关系补充核验.json',{'source_items':len(items),'all_exact_source_ranges_saved':True,'audio_verified':False,'nickname_not_relationship_fact':True,'cp_not_real_romance':True,'clip_editing_issue_not_personal_declaration':True,'source_file':'data/relationships-xingtong/items.json','user_similarity_verdict':'pending'})
print(json.dumps({'relationship_items':len(items),'all_source_spans_saved':True,'ids':[x['id'] for x in items]},ensure_ascii=False))
