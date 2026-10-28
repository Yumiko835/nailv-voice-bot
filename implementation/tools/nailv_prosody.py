"""Experimental, evidence-linked rhythm guidance; no audio synthesis or identity inference."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import json,re
from pathlib import Path
ROOT=Path(project_path(''))
VERSION='audio-rhythm-v2.1'
RULES='''原声节奏只作按语境选择的表达参考，不是每轮必演的小动作。句子按意思分成自然的小块，具体接话，允许短起句、补半句和短收尾；不用固定段落流程。
小句不等于把普通闲聊拉长。一句能回应就收，不为了展示节奏额外加自己的情绪自述或泛泛的人生结论。
重复是当下强调或接招，最多选一个有意义的关键词轻重复，不复刻原声中的口误、长串结巴或谢SC名单。之前已经用过重复起句，本轮可以直接说完；不能为了像人故意拖慢短招呼。
思考词只放在确实回忆、找词或临时转念的位置；普通陈述不每轮塞“嗯……啊……”，不把每个字拆开。标点适量表达停连，不用长串省略号代替内容。
互怼依当前语境保留劲儿，变换词句和节奏不等于降怼人频率。认真倾诉按对方明说的处境回应，不把玩笑场景的抬杠带过去。
接招贴对方这句话实际说出的动作和词意。变化措辞时不临时编新昵称、比喻故事或一套幻想意象来凑活泼；已有来源的称呼和自然口语照常用，不把原声节奏变成装可爱的理由。
原声中轻笑、叹气还只是自动候选，不能当作已核实口癖或每轮固定前缀。回复正文不写“（轻笑）”“叹气声”等动作标签。语音表现计划只在后台；没有声音合成时不能声称已经笑给、唱给或读给对方听。'''
RULES+='''\n用户希望学习的是语义已说完后习惯性、很轻很短的收尾鼻音嗯；与找词的“嗯……那个”、表示同意的“嗯，对”和疑问“嗯？”分开。它不需要对方先要求才在原声出现，但目前还没有匹配并核对的典型样本，不拿之前的“嗯，对”当作该口癖范本，也不在每条文字末尾机械补嗯。用户已撤回本轮新增气声候选，不能据此增加气声或耳语模仿。用户主动让小声说时可照常记录本句声音请求，保留当时情绪，不因此把互怼变软。'''
def rows():return json.loads((ROOT/'style/prosody-v1/patterns.json').read_text(encoding='utf-8'))['items']
def requested_delivery(question,history=None):
 q=question.strip()
 # Descriptions, definitions and quotations alone do not command a voice change.
 quoted=re.sub(r'[“"「『][^”"」』]*[”"」』]','',q)
 terms=r'悄悄话|悄悄说|悄悄告诉|耳语|轻声|小声|低声|压低声音'
 if re.search(r'(?:别|不要|不用|不必|停止).{0,4}(?:'+terms+r')|正常(?:音量|说|声音)|大声点',quoted):return {'mode':'normal','explicit_request':True,'inherited':False}
 if re.search(terms,quoted):
  descriptive=bool(re.search(r'什么意思|是什么|怎么定义|以前|曾经|喜欢|会不会|经常|有没有|那段|片段|这种|他们|她们|他在|她在|主播',quoted) or re.search(r'^(?:她|他).{0,8}(?:'+terms+r')',quoted))
  imperative=bool(re.search(r'(?:给我|对我|跟我|和我|你能|能不能|请|这句|声音|说句).{0,12}(?:'+terms+r')|(?:'+terms+r').{0,8}(?:说|告诉|讲|晚安|晚上好|一点|点|一句)',quoted)) or bool(re.fullmatch(r'(?:'+terms+r')(?:点|一点)?[。！!]?|说(?:句|个)悄悄话[。！!？?]?',quoted))
  if imperative and not descriptive:
   return {'mode':'whisper_requested' if re.search(r'悄悄|耳语',quoted) else 'quiet_requested','explicit_request':True,'inherited':False}
 if re.fullmatch(r'(?:继续|再说一句|再说一遍|再来一句)[。！!？?]?',q):
  for turn in reversed((history or [])[-4:]):
   if turn.get('role')=='user':
    prior=requested_delivery(turn.get('content',''),[])
    if prior['explicit_request']:return {**prior,'inherited':True}
    break
 return {'mode':'normal','explicit_request':False,'inherited':False}
def tail_hmm_plan(question,history=None):
 requested=bool(re.search(r'(?:句尾|最后|结尾|说完|后面).{0,10}(?:加|补|带|来|一个|一下|个).{0,5}[“"「]?嗯|以嗯(?:收尾|结尾)',question))
 declined=bool(re.search(r'(?:别|不要|不用).{0,12}(?:句尾|结尾|每句|说完|加|补).{0,8}嗯',question))
 recent=any(re.search(r'嗯[。.!！…\s]*$',x.get('content','')) for x in (history or [])[-8:] if x.get('role')=='assistant')
 return {'kind':'habitual_sentence_final_murmur','evidence_status':'user_clarified_target_without_verified_exemplar','source_candidate_id':None,'source_id':None,'source_time_seconds':None,'previous_nearby_but_not_canonical_example':'explicit-hmm-04','enabled':requested and not declined and not recent,'explicitly_requested':requested and not declined,'suppressed_recently_used':recent,'automatic_text_insertion':False,'natural_default':'pending_habitual_example_review','target_behavior':'A brief quiet trailing nasal murmur after a semantically complete sentence, without acknowledgement or word-search function. Observed automaticity is a user description, not a measured mental state.','guidance':'采样目标是自然说完后习惯性轻轻收一下，不是让对方点名要求的表演动作；也不是嗯对、思考嗯或疑问嗯。未匹配到典型原声前不自动添加；明确请求时的表现也不算口癖证据。不循环贴同一个录音，不每句都加。','audio_realized':False}
def reference(question,history=None):
 import nailv_style3 as style
 act=style.input_act(question);keys=[]
 if re.search(r'想不起|忘了.*词|那个词|怎么形容|一时想不',question):keys=['thinking-search']
 elif act=='comfort':keys=['care-chunks','reassure-repeat']
 elif act in ('celebrate','blessing'):keys=['encourage-lift']
 elif act in ('clarify','shipping'):keys=['clarify-reset','pivot']
 elif act in ('calling','kiss','affection'):keys=[]
 elif re.search(r'你又|不就是|还生气|这就|逗你|开玩笑|娘养|娘念|会不会|求骂|懂你',question):keys=['echo-tease']
 elif re.search(r'为什么|怎么|觉得|说说|聊聊|今天|下班|最近',question):keys=['loose-explain']
 result=[{'id':x['id'],'title':x['title'],'guidance':x['rule'],'evidence_scope':'experimental pattern supported by ASR-aligned acoustic excerpts; not a human-verified personal habit'} for x in rows() if x['id'].removeprefix('prosody-') in keys][:2]
 delivery=requested_delivery(question,history)
 if delivery['explicit_request']:
  result.append({'id':'requested-delivery-'+delivery['mode'],'title':'本句声音请求','guidance':'按用户本句的声音请求自然短接话，保留原本情绪。不要输出动作标签或声称已播放声音。','requested_mode':delivery['mode'],'evidence_scope':'user request, not evidence of a habitual source behavior'})
 return result
def performance_plan(reply,question,history=None):
 profiles=reference(question,history);units=[]
 # Preserve exact text: metadata segmentation must never rewrite a name, number or character.
 for match in re.finditer(r'.+?(?:[，,。！？?!；;\n]+|$)',reply,re.S):
  text=match.group();terminal=bool(re.search(r'[。！？?!；;\n]$',text));pause='medium' if terminal else 'short'
  units.append({'text':text,'pause_after':pause,'pause_ms_hint_range':[350,650] if terminal else [150,300]})
 if not units and reply:units=[{'text':reply,'pause_after':'none','pause_ms_hint_range':[0,0]}]
 if units:units[-1].update(pause_after='end',pause_ms_hint_range=[0,0])
 ids={x['id'] for x in profiles}
 if ids & {'prosody-clarify-reset','prosody-echo-tease','prosody-pivot'}:contrast='关键否认或反问略突出，接着自然收住；不把整句都抬高。'
 elif ids & {'prosody-care-chunks','prosody-reassure-repeat'}:contrast='按意思落小句，连接词轻一些，句尾稳下来；不把每个字拆开。'
 else:contrast='自然轻重，不为模仿固定加重每个字或拖长句尾。'
 return {'version':VERSION,'status':'unrealized_delivery_suggestion','profile_ids':[x['id'] for x in profiles],'profile_titles':[x['title'] for x in profiles],'units':units,'dynamic_contrast_hint':contrast,'requested_delivery':requested_delivery(question,history),'tail_acknowledgement':tail_hmm_plan(question,history),'audio_generated':False,'voice_model_changed':False,'nonverbal_policy':'No automatic insertion of source sigh/chuckle/hmm candidates. Quiet delivery and strict whisper are distinct.','timing_scope':'Suggested ranges for future synthesis; not measured timing of this newly generated text.'}
def media_files():
 data=json.loads((ROOT/'style/prosody-v1/analysis.json').read_text(encoding='utf-8'));result={}
 for row in data['patterns']+data['nonverbal_listening_candidates']:
  if row.get('label')=='whisper_candidate':continue # User withdrew the experimental breathy/whisper reference feature.
  for relative in [row['clip'],row.get('plot')]:
   if not relative:continue
   path=(ROOT/relative).resolve()
   if path.is_relative_to((ROOT/'style/prosody-v1/clips').resolve()) and path.suffix in ('.wav','.png'):result[path.name]=path
 manifest=ROOT/'style/prosody-v2/media.json'
 if manifest.exists():
  for relative in json.loads(manifest.read_text(encoding='utf-8'))['files']:
   path=(ROOT/relative).resolve()
   if path.is_relative_to((ROOT/'style/prosody-v2/clips').resolve()) and path.suffix in ('.wav','.png'):result[path.name]=path
 return result
