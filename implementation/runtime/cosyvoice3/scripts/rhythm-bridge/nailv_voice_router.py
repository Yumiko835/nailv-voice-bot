"""Local reference selection by reply speech act, not emotion tags in chat text."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import re, math
from nailv_live_emotions import LABELS as LIVE_LABELS,normalize
VERSION='background-delivery-router-v4'
# Match the character's RESPONSE, not a topic such as 星瞳/CP or user emotion alone.
RULES={
 'explaining':[
  (4.0,r'(?:没|没有)(?:实际)?(?:接触|见过|交集)|谈不上(?:熟|认识)','说明实际接触与熟悉程度'),
  (3.4,r'粉丝(?:之间|那边|的事)|别把.{0,10}关系.{0,10}(?:复杂|想)|关系.{0,8}(?:没那么|不是)','澄清关系与粉丝话题'),
  (3.2,r'我的意思|我是说|我说的是|不是.{0,7}(?:这个|那个)意思|也就是说|你理解|就是这个意思','解释或纠正理解'),
  (2.8,r'不是说.{0,12}我是说|先看看.{0,12}别回头|因为.{0,20}所以','解释原因与做法')],
 'tsundere':[
  (4.1,r'(?:别|不要)(?:老|再|一直|连着)(?:.{0,5})(?:叫|喊|催|说)|(?:叫|喊|说)一声就够','轻微制止反复称呼或催促'),
  (4.0,r'硬(?:塞|凑|扯).{0,12}(?:干嘛|做什么)','抱怨被强行牵扯'),
  (4.0,r'别.{0,8}(?:推|扯|赖|扣).{0,6}(?:我|头上)','制止把事情推到自己身上'),
  (3.4,r'没生气|才没有|少来|不许|别闹|真是服了|你还来','嗔怪或否认生气'),
  (2.4,r'你又不听|让你听话|我都说了|还要我说几遍','轻微抱怨与提醒')],
 'teasing':[
  (5.4,r'木马|么么|啵(?:啵)?|亲(?:你|我|一口|一下)','亲昵玩笑'),
  (3.5,r'逗你|你又懂了|我就当你懂|瞧把你|瞧你|还挺会|就你会|学会了是吧|你倒是|又开始了','顺着对方接梗'),
  (3.0,r'这么喜欢叫|可真行|想得美|给自己加戏|被你(?:发现|逮|看穿)|差辈了','调侃称呼或顺势打趣')],
 'surprised':[
  (5.0,r'(?:^|[。！？])\s*(?:啊|诶|欸)[？?]|真的假的|怎么会|怎么突然|什么情况|不会吧','明显惊讶或疑惑'),
  (3.1,r'我还以为.{0,20}(?:你说|在说)|居然.{0,12}[？?！!]','发现理解与预期不同')],
 'excited':[
  (4.5,r'恭喜|太好了|好耶|太厉害|成功啦|太棒了|终于(?:过了|成了|赢了)|这回真.{0,5}(?:弄成|成功)','庆祝或兴奋肯定'),
  (3.4,r'可以啊你|真给你.{0,4}(?:弄成|做成)|你是真顶住了','带兴奋的肯定')],
 'sigh':[
  (4.0,r'(?:^|[。！？])\s*(?:唉|哎呀)|没办法|我能怎么办|说了半天|怎么又|我也没招','无奈或叹息'),
  (3.4,r'折腾.{0,8}(?:半天|这么久)|折腾半天|算了吧|先放一放.{0,12}(?:明天|累)','疲惫与暂时放下')],
 'serious':[
  (5.2,r'认真说|原则|界限|造谣|不要传播|这件事.{0,5}很重要|不能这么做','认真说明原则或界限')],
 'lazy':[
  (3.3,r'困了|好困|懒得|躺着|刚睡醒|发会呆|歇一会|歇会|随便聊|不着急','松弛、疲惫或随意聊天')],
}
# General speech-act patterns recovered from missed real chat replies.
RULES['teasing'] += [(3.8,r'我急什么|看你还能.{0,5}(?:编|装)|你还真敢|装什么|你就装','反话接招或打趣')]
RULES['tsundere'] += [(3.8,r'我就不|硬扣帽子|别乱认|称呼.{0,8}(?:不敢接|算了)|妈妈.{0,8}算了','嗔怪、装不接招或抱怨')]
RULES['explaining'] += [(3.2,r'再(?:次)?声明|再说一遍|我说清楚','明确重申或澄清')]
RULES['explaining'] += [(3.6,r'我(?:不太|没)明白|你说的是|你的意思是|是这个(?:意思)?吗|我确认一下|所以你是想','求证对方的意思')]

def route(text,question='',history=None,manual=None,allowed=None,delivery=None):
    allowed=set(allowed or LIVE_LABELS);scores={'daily':.8,**{k:0. for k in RULES}}
    evidence={k:[] for k in scores}
    if manual:
        manual=normalize(manual,text)
        if manual not in allowed:raise ValueError('参考语气不可用。')
        return {'style':manual,'source':'manual','note':'按你手动选择的参考语气','version':VERSION,'scores':None}
    from nailv_affect_context import routing_profile
    profile=routing_profile(text,question,history)
    if profile and 'serious' in allowed:
        return {'style':'serious','reference_profile':profile,'affect':'低落惦念',
                'source':'character_pet_context','note':'提起坚果的克制低落；暂用已确认的沉稳条，不用质问式叹气条。',
                'reference_limit':'尚无人工确认的纯净悲伤条；沉稳参考不能保证生成悲伤听感。',
                'version':VERSION,'scores':None,'human_affect_correction':True}
    for style,rules in RULES.items():
        for weight,pattern,note in rules:
            match=re.search(pattern,text)
            if match:
                # Negative emotion words are not positive excitement cues.
                if style=='excited' and re.search(r'不开心|不是.{0,4}(?:好事|开心)|别高兴',text):continue
                scores[style]+=weight;evidence[style].append({'note':note,'matched':match.group()})
    for retired in ('lazy','sigh','surprised'):
        target=normalize(retired,text)
        if scores[retired] and target in allowed:
            scores[target]+=scores[retired];evidence[target].extend(evidence[retired])
    # Pure reassurance is not a reprimand merely because it starts with 别.
    if re.search(r'别着急|别担心|不用急|没关系',text) and not evidence['tsundere']:
        scores['daily']+=1.
    best=max((k for k in scores if k in allowed),key=scores.get)
    if scores[best]<2.:best='daily'
    source='reply_act_rules';note='；'.join(x['note'] for x in evidence[best]) or '没有明显表演语气，保持自然闲聊'
    delivery=delivery if isinstance(delivery,dict) else {}
    labels={'日常闲聊':'daily','开心兴奋':'excited','调侃戏谑':'teasing','慵懒随性':'lazy','傲娇抱怨':'tsundere','惊讶疑惑':'surprised','认真严肃':'serious','无奈叹气':'sigh','解释确认':'explaining'}
    explicit=normalize(delivery.get('emotion'),text)
    coarse={'playful':'teasing','firm':'tsundere','serious':'serious'}.get(delivery.get('tone'))
    if not coarse and delivery.get('nonverbal')=='sigh_candidate':coarse=normalize('sigh',text)
    if explicit in allowed and explicit!='daily':
        best=explicit;source='llm_background_emotion';note='按聊天模型结合上下文给出的后台语气分类'
    elif best!='daily':
        if explicit=='daily':source='reply_act_corrected_daily';note+='；具体表达优先于笼统的闲聊分类'
    elif coarse in allowed:
        best=coarse;source='llm_delivery_tone';note='按聊天模型已有的后台表达姿态匹配参考'
    elif explicit=='daily':source='llm_background_emotion';note='聊天模型判断为自然日常接话'
    return {'style':best,'source':source,'version':VERSION,'note':note,
            'scores':scores,'evidence':evidence[best],
            'llm_delivery':{k:delivery[k] for k in ['emotion','tone','pace','intensity','nonverbal'] if isinstance(delivery.get(k),str) and len(delivery[k])<=40},
            'reply_act_drives_voice_not_user_topic':True,'not_a_calibrated_emotion_probability':True}
