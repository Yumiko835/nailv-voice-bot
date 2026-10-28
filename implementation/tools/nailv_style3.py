"""Retrieve actual reply wording by conversational act and lexical relevance."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import collections,json,math,re,secrets
from pathlib import Path
ROOT=Path(project_path(''))
VERSION='lexical-v3.3'
import nailv_expression_variation as variation
STOP={'什么','怎么','这个','那个','可以','一下','时候','知道','感觉','事情','就是','然后','谢谢','不是','一个','自己','觉得','你们','我们'}
def bank():return json.loads((ROOT/'style/v3.2/表达选段库.json').read_text(encoding='utf-8'))['items']
def tokens(text):
    result=re.findall(r'[A-Za-z][A-Za-z0-9_-]{1,20}',text.lower())
    for span in re.findall(r'[\u3400-\u9fff]+',text):
        for length in (2,3):result.extend(span[i:i+length] for i in range(len(span)-length+1) if span[i:i+length] not in STOP)
    return collections.Counter(result)
def input_act(question):
    if re.search(r'难过|不开心|焦虑|害怕|没考好|考砸|生病|不舒服|委屈|心情差|累死|好累',question):return 'comfort'
    if re.fullmatch(r'[妈嘛啊呀，,！!。\.\s]+',question) and '妈' in question:return 'calling'
    if re.search(r'mua|木马|亲亲|么么|亲我|亲一',question,re.I):return 'kiss'
    if re.search(r'我.{0,6}(?:喜欢|爱)你|好喜欢奶|好爱奶',question):return 'affection'
    if re.search(r'星瞳|星彤|绿瞳|绿同|欣桐|CP|cp|卡黄',question):return 'shipping'
    if re.search(r'考过|成功了|通过了|做完了|夸我|报喜',question):return 'celebrate'
    if re.search(r'加油|祝我|祝福|生日',question):return 'blessing'
    if re.search(r'真名|住址|隐私|替我.*买|帮我抢|刷屏',question):return 'refusal'
    if re.search(r'什么意思|你不是|误会|怎么.*都|你怎么.*天天',question):return 'clarify'
    if re.search(r'怎么看|觉得|为什么|要不要|建议|喜欢什么',question):return 'opinion'
    return 'daily'
def rank(question,history=None,limit=24,hint=''):
    rows=bank();act=input_act(question);q=tokens(question+' '+hint)
    docs=[tokens(x['context_paraphrase']+' '+x['reply_excerpt']) for x in rows]
    df=collections.Counter(t for d in docs for t in d);avg=sum(sum(d.values()) for d in docs)/max(len(docs),1)
    recent=' '.join(str(x.get('content','')) for x in (history or [])[-4:] if x.get('role')=='assistant');recent_tokens=tokens(recent)
    related={'calling':{'calling','kiss','affection','other'},'kiss':{'kiss','affection'},'affection':{'affection','kiss','banter'},'shipping':{'refusal','banter','clarify'},'daily':{'daily','banter','opinion'}}.get(act,{act})
    seed=secrets.token_hex(8);scored=[]
    for x,doc in zip(rows,docs):
        if x.get('requires_question_terms') and not any(t in question for t in x['requires_question_terms']):continue
        length=sum(doc.values());score=0.
        for term in q:
            tf=doc.get(term,0)
            if tf:score+=math.log(1+(len(rows)-df[term]+.5)/(df[term]+.5))*tf*2.2/(tf+1.2*(.25+.75*length/max(avg,1)))
        if x.get('act') in related:score+=12
        request=x.get('source_request_tags',[])
        if act=='calling' and 'calling' in request:score+=35
        if act=='shipping' and 'shipping' in request:score+=32
        if act in ('calling','kiss','affection') and x.get('specific_problem'):score-=30
        if act in ('calling','kiss') and len(x['reply_excerpt'])<40:score+=8
        overlap=sum(min(v,recent_tokens.get(t,0)) for t,v in tokens(x['reply_excerpt']).items())
        if len(x['reply_excerpt'])>=12:score-=min(overlap,8)*.8
        score-=variation.reference_penalty(x['reply_excerpt'],question,history)
        scored.append((score,hash(seed+x['id']),x))
    scored.sort(key=lambda x:(-x[0],x[1]));selected=[];sources=collections.Counter()
    for score,_,x in scored:
        sid=x['source_refs'][0]['source_id']
        if sources[sid]>=2:continue
        selected.append(x);sources[sid]+=1
        if len(selected)>=limit:break
    return selected

RULES='''学习贴着对方这句话接招，用具体动作和口语句式组织新话，而不是每次套同一种评价。
对方故意逗弄、起哄时可以继续互怼、反问和吐槽；措辞变化不等于降低这种语境下的情绪和力度。发生误读时简短纠正，不必把每种玩笑都说成对方在强加动机；轻松聊喜欢的作品时，可以直接说哪里戳自己。情绪强弱随具体事情起落，不固定全程甜、全程凶或每轮先叹气。
优先用具体动词与口语接句，把评价落到这件事上；少用“情绪价值、单纯想撒娇、是有什么好事”等空泛心理归因。已经讲清楚就收住，不为了显得活泼额外塞流行梗或结尾问题。
表达层使用本轮选出的真实回应片段作参考，先接住当前这句明确说了什么，再组织新话。上下文和原话不是现实行动、个人经历或观众关系的授权。
短招呼、应声、亲昵互动允许一句、半句或一个拟声词就结束，不为了显得热情主动补出对方的心情、动机、遭遇或问题。没有给出烦恼时，不默认正在求安慰；已经回应完就可以停。
本轮规划只需要应声或亲亲时，就在这个范围内落句，不自行加一段泛泛夸赞、感情解释或新话题。亲近程度通过原话中的用词、轻重和接句体现，不靠临时编出一套甜言蜜语来补足。
不把所有亲近话都接成“先分析撒娇—解释感受—反问原因”。不用恋爱小说式惊讶台词来填充一个普通的互动请求，不在没有依据时替对方说“今天心情不错”。关系和称呼以当前对话为准，不擅自升级。
学参考里的具体用词、接句和收住的位置，但不按原文逐字接龙，不把一次玩笑固化成每次必须说的台词。认真倾诉、轻松起哄、被误读和拒绝带节奏分别接；不用同一种笑、反问和撒娇铺满所有情境。
同样的事实保持一致，措辞可以随上下文改变。新的一轮要回应新内容，避免照抄最近几轮已说过的长句和结尾；不为追求变化改动生日、年龄、人物、事件或数字。
参考含ASR错字、重复和换行，输出时恢复自然中文。不要照搬逐字结巴、歌词、谢SC的观众名字或没说完的残句。原话可能只反映过去某一次态度，不自动等同于今天的心情。'''
