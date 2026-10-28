"""Source-backed supplemental retrieval, separate from the accepted vector edition."""

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
import json,re,sqlite3
ROOT=Path(project_path(''))
ALIASES={
 '星瞳':['星瞳','星彤','欣桐','绿瞳','绿同','瞳姐'],
 '坚果':['坚果','店长','果仁'],
 'LLL':['lll','露莉绿','三人组','你们三个','你们仨'],
 '莉莉丝':['莉莉丝','夜王莉莉丝','发卡','正直少年李发卡'],
 '露露':['露露','雫露露','雫るる','lulu'],
 '年龄':['几岁','多大','年龄','19岁','十九岁','永远19'],
 '生日':['生日','几月几号','3月4','三月四'],
 '花店':['花店','laplace','拉普拉斯','侧写','共感'],
 '奶黑':['奶黑','新衣','新形象','皮套','角色形象'],
 '直播经历':['首播','出道','初配信','周年','休播','复播'],
 '梨安':['梨安','梨安不迷路','梨宝'],
 '恬豆':['恬豆','甜豆','恬豆发芽了'],
 '白小蛮':['白小蛮','白小蛮不讲理'],
 '栞栞':['栞栞','shiori'],
 '勾檀':['勾檀','mayumi'],
 '申䒕雅':['申䒕雅','小雅','申放送'],
 '小希':['小希','小希小桃channel'],
}
STOP={'什么','怎么','时候','最近','一下','你好','觉得','今天','昨天','可以','这个','那个','喜欢','知道','是不是','关系','感情','事情','感觉','问题','一起','记得'}
def items():
    file=ROOT/'data/self-supplement/items.json'
    return json.loads(file.read_text(encoding='utf-8'))['items'] if file.exists() else []
def core_facts():return [x for x in items() if x.get('core')]
def groups(question):
    q=question.lower();return [k for k,v in ALIASES.items() if any(a.lower() in q for a in v)]
def expand(question,history=None):
    topics=groups(question);extra=''
    # Carry entities only for a dependent follow-up, not an unrelated new topic.
    follow=bool(re.search(r'她们|你们|她呢|她还|他呢|那次|那时候|那个时候|后来呢|之后呢|还有呢|还有什么|一起.*(?:玩|做|干)|还有.*回忆',question))
    if follow and not topics:
        for turn in reversed((history or [])[-4:]):
            if turn.get('role') not in ['user','assistant']:continue
            previous=groups(str(turn.get('content','')))
            if previous:topics=previous;extra=' '+str(turn.get('content',''))[:300];break
    if 'LLL' in topics:
        topics=list(dict.fromkeys(topics+['莉莉丝','露露']))
    aliases=[a for k in topics for a in ALIASES[k]]
    return question+' '+extra+' '+' '.join(aliases),topics
def retrieve(question,history=None,limit=6):
    rows=items()
    if not rows:return [],question
    expanded,topics=expand(question,history);q=question.lower()
    if '坚果' in topics and re.search(r'现在|还在|还好|活着|怎么样|去世|死|出事',question) and not re.search(r'以前|那次|当时|往事|怎么找',question):
        return [],expanded  # The curated loss timeline is always in core, old pet routines stay out here.
    terms=set(re.findall(r'[a-z][a-z0-9_-]{1,24}',expanded.lower()))
    for span in re.findall(r'[\u3400-\u9fff]+',question):
        for n in [2,3,4]:
            for i in range(len(span)-n+1):
                t=span[i:i+n]
                if t not in STOP and not any(c in '你我她他是了的呢吗啊呀吧哦么这那就不很在有想要能会个一对' for c in t):terms.add(t)
    def score(x):
        if x.get('entity_disambiguation') and not re.search(r'漫画|偷[星心]|十月|四月',question):return 0
        text=x['text'].lower();entities=' '.join(x.get('entities',[])).lower();xt=x.get('topics',[])
        hit=sum(t.lower() in text for t in terms)
        entity_hit=sum(1 for k in topics if k in xt or any(a.lower() in entities or a.lower() in text for a in ALIASES[k]))
        direct_entity=any(len(v)>=2 and v.lower() in q for v in x.get('entities',[]) if v not in ['明前奶绿','奶绿','主播','店员','自己','花店'])
        entity_hit+=int(direct_entity)
        focused=bool(topics)
        if focused and not entity_hit:return 0
        rank=entity_hit*25+hit*3
        if x.get('editorial_checked'):rank+=8
        if x.get('human_review'):rank+=2
        if x.get('core'):rank+=5
        if 'LLL' in topics and x.get('kind')=='lll_event':rank+=30
        if '坚果' in topics and x.get('core') and '失' in x['text']:rank+=35
        if re.search(r'怎么认识|认识.*时候',q) and not re.search(r'认识|初次|第一次',text):rank-=15
        return rank if focused or direct_entity or hit>=2 else 0
    ranked=sorted(((score(x),x) for x in rows if not x.get('core')),key=lambda z:(-z[0],z[1]['id']))
    selected=[];source_counts={};event_counts={}
    for rank,x in ranked:
        if rank<=0:continue
        sid=x['source_refs'][0]['source_id']
        if source_counts.get(sid,0)>=2:continue
        event=next((v for v in ['双影奇境','双人成行','鬼灭之刃','BW','逛街','骰子','菜王杯'] if v in x['text']),None)
        if event and event_counts.get(event,0)>=1:continue
        selected.append(x);source_counts[sid]=source_counts.get(sid,0)+1
        if event:event_counts[event]=event_counts.get(event,0)+1
        if len(selected)>=limit:break
    return selected,expanded
