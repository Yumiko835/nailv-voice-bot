"""Publish a separate, reversible experimental supplement with provenance."""

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
import collections,datetime,hashlib,html,json,re,shutil,sqlite3,sys
R=Path(project_path(''));sys.path.insert(0,str(R/'tools'))
import publish_nailv_library as p
def load(rel):return json.loads((R/rel).read_text(encoding='utf-8'))
def save(rel,data):p.save(rel,data)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def source_day(value):
    if value.endswith('Z'):return datetime.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
    return value
CORE=[];EDITORIAL=[]
def main():
    if (R/'review/conditional-acceptance-20261024/decision.json').exists():
        from publish_conditional_acceptance import main as apply_accepted
        apply_accepted();return
    out=R/'data/self-supplement';out.mkdir(parents=True,exist_ok=True)
    posts={x['id']:x for x in load('work/social-supplement-20261024/posts.json')['items']}
    subs={x['id']:x for x in load('work/self-audit-20261024/keep.json')['items']}
    def add(name,text,topics,entities,source_ids,core=False,kind='fact',scope='historical',realm='public_life'):
        refs=[];dates=[]
        for sid in source_ids:
            if sid in posts:
                x=posts[sid];refs.append({'source_id':sid,'quote':x['own_text'],'origin':x['origin']});dates.append(source_day(x['record_date']))
            elif sid in subs:
                x=subs[sid];refs+=x['source_refs'];dates.append(x['source_record_date'])
            else:raise ValueError('Missing source: '+sid)
        obj={'id':'fact-self-'+name,'kind':kind,'text':text,'topics':topics,'entities':entities,'core':core,'time_scope':scope,'realm':realm,'source_record_date':max(dates),'event_date':None,'source_refs':refs,'review':'editorial_source_checked','editorial_checked':True,'human_review':False,'active_in_text_pilot':True,'audio_verified':False,'review_note':'Source text and attribution checked during this update; not user approval and not original-audio verification.'}
        (CORE if core else EDITORIAL).append(obj)
    add('age19','角色自称永远19岁。回答年龄保持19，不按年份或周年增加岁数，也不由此推测真实出生年。',['年龄'],['明前奶绿'],['supp-d1749801f22045539158'],True,scope='stable',realm='lore')
    add('birthday','生日是3月4日，不是3月14日；某年庆生直播延后不代表生日改了。',['生日'],['明前奶绿'],['supp-8cd2d68730e1beb2e4e9'],True,scope='stable')
    intro='bili-709069976572526628'
    add('flower-shop','公开角色设定：在名为LAPLACE（拉普拉斯）的花店打工，是花店店员；喜欢百合，习惯躺藤椅晒太阳打盹，有侧写与共感的能力。能力是角色设定。',['花店'],['明前奶绿','LAPLACE'],[intro],True,scope='stable',realm='lore')
    add('manager','坚果是一只布偶猫，在花店的公开设定里称为店长。过去会拿他懒、贪吃、翻垃圾桶开玩笑；这些是往事，不等于他现在仍在身边。',['坚果','花店'],['明前奶绿','坚果'],[intro],True,scope='stable',realm='lore')
    add('lll-members','LLL是明前奶绿、夜王莉莉丝和雫るる（露露）三人的公开联动组合。她们有共同活动和亲近玩笑；不能据此认定真实恋爱或同公司雇佣关系。',['LLL','莉莉丝','露露'],['明前奶绿','莉莉丝','露露','LLL'],['bili-995243814836764681','supp-6e655fd5bd1c62ed99c6'],True,scope='stable')
    add('lulu-friend','雫るる的常见叫法是露露、lulu。2026年2月的本人动态公开称她为“我的超级大亲友”，曾一起联动游戏、唱歌和活动。亲昵称呼“老婆”保留朋友玩笑语境。',['露露'],['明前奶绿','露露'],['bili-1165869890450489361','bili-1044972376437030912'],True,scope='stable')
    add('lilith-context','莉莉丝与正直少年李发卡这个公开账号的活动有关；奶绿也会用“发卡是发卡，莉莉丝是莉莉丝”区分角色称呼。用这些叫法可联系公开往事，不挖掘或扩展真实身份。',['莉莉丝','LLL'],['明前奶绿','莉莉丝','发卡'],['bili-827915797427912708','supp-1b32c2964e389c674838'],True,scope='stable')
    add('fans','粉丝会被称为奶糖花；花店、店员、店长是她经常使用的公开称呼体系。',['花店'],['明前奶绿','奶糖花'],['bili-1094822824922578948'],True,scope='stable')
    clip=load('sources/social-20261024/jianguo-clip/transcription.json')
    spans=[x for x in clip['segments'] if 33<=x['start']<=44.7]
    CORE.append({'id':'fact-self-manager-loss','kind':'pet_event','core':True,'text':'2025年11月公开片段里谈到寻找坚果没有找到，并保留“可能还活着”的说法。这是一段失去店长陪伴的往事，不能编成他现在还在身边，也不能断言已确认死亡、具体死因或事故日期。','entities':['明前奶绿','坚果'],'topics':['坚果'],'time_scope':'historical','realm':'public_life','source_record_date':'2025-11-15','event_date':None,'uncertainty':'片段上传日不是事故日；现有原话仍有不确定性。自动转写未逐句听校。','source_refs':[{'source_id':'clip-BV1fACSB1ERV','origin':clip['origin'],'quote':'\n'.join(x['text'] for x in spans),'start_seconds':spans[0]['start'],'end_seconds':spans[-1]['end']}],'review':'editorial_source_checked','editorial_checked':True,'human_review':False,'active_in_text_pilot':True,'audio_verified':False})
    add('manager-nickname','2024年5月的一则动态里，奶绿说“坚果叫果仁这个提议很不错！采纳了！”“果仁”可作为这段玩笑里的店长昵称。',['坚果'],['坚果','果仁'],['bili-928088307502415877'],kind='pet_event',realm='joke')
    add('lll-demon-slayer','2024年6月，奶绿、莉莉丝、露露约好三人一起看《鬼灭之刃 无限列车篇》。后来聊过：奶绿先和露露约时间，再邀请莉莉丝，最后定在17号一起看。',['LLL','莉莉丝','露露'],['明前奶绿','莉莉丝','露露','LLL'],['bili-942855843919953937','supp-2ca35149d6ae7a6002e1'],kind='lll_event')
    add('lll-equipment','三人联动时有过提前很久调设备仍遇到麦克风、软件故障的插曲。相关调侃是当时的联动趣事，不能据此断言谁一直笨或关系不好。',['LLL','莉莉丝','露露'],['明前奶绿','莉莉丝','露露','LLL'],['supp-b95f948380edf4ce141d'],kind='lll_event')
    add('lll-bw2024','2024年7月BW现场，明前奶绿、雫露露与夜王莉莉丝以LLL组合参加过答题小剧场；本人7月12日动态也@了她们和申䒕雅，并说“我们是天才”。',['LLL','莉莉丝','露露'],['明前奶绿','莉莉丝','露露','LLL','申䒕雅'],['supp-6e655fd5bd1c62ed99c6','bili-953176027772747800'],kind='lll_event')
    add('lll-schedule','奶绿说过，三个人的活动消息会有时间差和信息差，所以后来会发到三人群里互相确认；有人时间对不上，只去两个人是正常情况，不等于组合解散。',['LLL','莉莉丝','露露'],['明前奶绿','莉莉丝','露露','LLL'],['supp-9c217879c5925e2991af','supp-e9e3d7449e37fd5a0ea9'],kind='lll_event')
    add('lll-dice','一次为选歌排顺序，奶绿和发卡、露露掷骰子：她和发卡先都掷出六，重来后发卡二、奶绿一。她把这当作好笑的准备插曲。',['LLL','莉莉丝','露露'],['明前奶绿','发卡','露露','LLL'],['supp-e5b0616203d4529057b1'],kind='lll_event')
    EDITORIAL[-1]['event_details']={'purpose':'选歌顺序','first_round':{'奶绿':6,'发卡':6,'result':'平手'},'second_round':{'奶绿':1,'发卡':2},'boundary':'两轮点数不能混成同一轮。'}
    add('lulu-split-fiction','2025年3月27日，奶绿预告晚上和露露玩《双影奇境》；4月1日另一次联动因身体不适延期，4月3日凌晨的动态说完结并谢谢大家收看。预告与完结分别保留日期，不合并成同一天。',['露露'],['明前奶绿','露露'],['bili-1048979056940285977','bili-1050824204945981447','bili-1051305834000154625'],kind='peer_relation')
    add('family-leave2025','2025年7月29日，奶绿公告因家中亲人遭遇变故需要照料，一个月无法正常直播，期间可能在动态或微博冒泡、偶尔电台。公告没有说亲人身份、诊断或去世，不能补写。',['直播经历'],['明前奶绿'],['bili-1094822824922578948'],kind='streaming_milestone')
    add('birthday-delayed2025','2025年的庆生直播安排在3月8日，属于直播安排；生日仍是3月4日。',['生日','直播经历'],['明前奶绿'],['bili-1041546319695446071','supp-8cd2d68730e1beb2e4e9'],kind='streaming_milestone')
    add('character-storm','2023年12月11日的亚空间风暴、少女被卷入、征集全新形象，是花店栏目和角色剧情，不能当作本人现实失踪事件。',['奶黑','花店'],['明前奶绿'],['bili-873842204849733683'],realm='lore',kind='character_setting')
    add('nigreen-world','奶黑、奶白是花店世界观相关的角色称呼。2025年6月谈到她们时，奶绿把大家的凝视让角色“活过来”比作薛定谔的观测，认为很浪漫；这是对角色的叙述，不能据此杜撰现实中的医学人格诊断。',['奶黑','花店'],['明前奶绿','奶黑','奶白'],['supp-3d5700d7a305ea1dbe9b'],realm='lore',kind='character_setting')
    add('shop-bankrupt-joke','2023年“花店倒闭，坚果带着研究机器跑路”的文字是征集粉丝投稿的栏目文案，不能当作现实花店倒闭或2025年宠物事故。',['坚果','花店'],['明前奶绿','坚果'],['bili-798504467212271625'],realm='joke',kind='character_setting')
    # Machine-checked candidates are a separate experimental layer, never re-labelled as user-approved.
    machine=list(subs.values())+load('work/social-supplement-20261024/keep.json')['items']
    extra=R/'work/self-audit-extra-20261024/keep.json'
    if extra.exists():machine+=load(str(extra.relative_to(R)))['items']
    held=[];active=[];seen=set()
    for raw in machine:
        x=dict(raw);text=x['text'];kind=x['kind'];reason=None
        if re.search(r'生日|岁|年龄|出生|属相|星座|身高|体重',text):reason='Identity-related claim needs individual editorial reconciliation; consolidated core has priority.'
        if re.search(r'住址|小区|几楼|楼层|学校名|真名|身份证|电话号|私人联系|诊断|精神分裂|双重人格',text):reason='Private detail or medical/persona ambiguity excluded.'
        if re.search(r'坚果|店长',text) and re.search(r'死亡|去世|摔死|坠|死了|喵星',text):reason='Pet loss uncertainty requires curated timeline.'
        if re.search(r'坚果',text) and re.search(r'核桃|碧根果|炒货|果仁糖|坚果类',text):reason='Common noun nuts is not the pet.'
        if '莉莉丝' in text and re.search(r'偷心|偷星|漫画|四月|游戏角色|动漫角色',text):reason='Fictional character with the same name is not the peer.'
        if '发卡' in text and re.search(r'头饰|头上|饰品|买.{0,3}发卡',text):reason='Physical hair clip is not a person.'
        if any(r['source_id']=='bili-1051305834000154625' for r in x['source_refs']) and '梦女文学' in text:reason='Opportunity/wish wording does not establish a completed shared activity.'
        if re.search(r'第[一二三四五六七八九十\d]+题|答题',text) and kind=='character_setting':reason='Stage content is not a character identity setting.'
        if reason:x['editorial_hold_reason']=reason;held.append(x);continue
        key=re.sub(r'[\W_]+','',re.sub(r'明前奶绿|在直播中|在本次直播中|自述|提到|说过','',text))
        if key in seen:continue
        seen.add(key)
        original_id=x['id'];x['id']='fact-self-'+original_id.removeprefix('supp-')
        x.update({'candidate_id':original_id,'review':'machine_source_checked','human_review':False,'editorial_checked':False,'active_in_text_pilot':True,'core':False,'time_scope':'historical' if x.get('time_scope')=='stable' else x.get('time_scope','historical'),'topics':[],'review_note':'Two model passes with exact-source spans; experimental, not user-approved or original-audio verified.'})
        if x.get('event_date'):
            try:
                yr,mo,dy=map(int,x['event_date'].split('-'))
                supported=any(re.search(str(yr)+r'\D{0,3}'+str(mo)+r'\D{1,3}'+str(dy)+r'(?:日|号|\D|$)',r['quote']) for r in x['source_refs'])
            except (TypeError,ValueError):supported=False
            if not supported:x['event_date']=None;x['inferred_event_date_removed']=True
        if x['source_refs'][0]['source_id'] in posts:
            stamp=posts[x['source_refs'][0]['source_id']]['record_date']
            if stamp.endswith('Z'):
                x['source_published_at_utc']=stamp
                x['source_record_date']=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        source=' '.join(x.get('entities',[]))+' '+text
        for topic,pattern in {'坚果':r'坚果|店长|果仁','LLL':r'LLL|lll|三人组','莉莉丝':r'莉莉丝|发卡','露露':r'露露|lulu|Lulu|るる','花店':r'花店|拉普拉斯|LAPLACE','奶黑':r'奶黑|新衣|形象','直播经历':r'出道|周年|休播|复播|首播'}.items():
            if re.search(pattern,source):x['topics'].append(topic)
        if re.search(r'打算|计划|预告|准备|明年|下周|明天|到时候',text) and not re.search(r'已经|曾经|后来',text):x['time_scope']='planned'
        if re.search(r'玩笑|调侃|开玩笑|称呼|妈妈|老婆|老公|解散|倒闭|跑路',text):x['realm']='joke'
        if kind=='character_setting' and re.search(r'魔法|共感|侧写|花店',text):x['realm']='lore'
        active.append(x)
    subtitle_pending=[x for x in active if not x.get('source_text_direct')]
    active=[x for x in active if x.get('source_text_direct')]
    for x in subtitle_pending:
        x['active_in_text_pilot']=False;x['review']='pending_speaker_attribution'
        x['review_note']='Machine checks are insufficient to establish who speaks first-person; held out of pilot pending attribution review.'
    extras=load('work/self-audit-extra-20261024/candidates.json')['items']
    extra_pending=[]
    for raw in extras:
        x=dict(raw);x['id']='pending-extra-'+x['id'].removeprefix('supp-')
        x.update({'review':'draft_first_model_pass','active_in_text_pilot':False,'editorial_checked':False,'human_review':False,'topics':[]})
        extra_pending.append(x)
    save('review/self-supplement-20261024/subtitle-pending.json',{'items':subtitle_pending+extra_pending,'note':'Not active character memories. Speaker attribution needs review; no automatic human approval.'})
    items=CORE+EDITORIAL+active
    save('data/self-supplement/items.json',{'version':'self-supplement-20261024','items':items,'human_review':False,'note':'Experimental supplement; original accepted data and vectors are unchanged.'})
    save('review/self-supplement-20261024/held.json',{'items':held})
    dbpath=out/'library.sqlite3'
    if dbpath.exists():dbpath.unlink()
    db=sqlite3.connect(dbpath);db.execute('CREATE TABLE items(id TEXT PRIMARY KEY,kind TEXT,text TEXT,entities TEXT,topics TEXT,source_date TEXT,time_scope TEXT,source_refs TEXT,review TEXT)')
    db.execute("CREATE VIRTUAL TABLE item_fts USING fts5(id UNINDEXED,text,tokenize='trigram')")
    for x in items:
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?)',(x['id'],x['kind'],x['text'],json.dumps(x['entities'],ensure_ascii=False),json.dumps(x.get('topics',[]),ensure_ascii=False),x['source_record_date'],x['time_scope'],json.dumps(x['source_refs'],ensure_ascii=False),x['review']))
        db.execute('INSERT INTO item_fts VALUES(?,?)',(x['id'],x['text']))
    db.execute('CREATE TABLE public_sources(id TEXT PRIMARY KEY,platform TEXT,text TEXT,source_date TEXT,origin TEXT)')
    db.execute("CREATE VIRTUAL TABLE source_fts USING fts5(id UNINDEXED,text,tokenize='trigram')")
    for sid,x in posts.items():
        db.execute('INSERT INTO public_sources VALUES(?,?,?,?,?)',(sid,x['platform'],x['own_text'],x['record_date'],x['origin']));db.execute('INSERT INTO source_fts VALUES(?,?)',(sid,x['own_text']))
    db.commit();db.close()
    reference_hashes=load('review/versions/before-lexical-v2/untouched-data-hashes.json')
    unchanged={rel:sha(R/rel)==digest for rel,digest in reference_hashes.items()};assert all(unchanged.values()),unchanged
    report={'version':'self-supplement-20261024','created_at':now(),'collection':load('work/social-supplement-20261024/collection-report.json'),'always_present_core':len(CORE),'editorial_memory_capsules':len(EDITORIAL),'machine_checked_additions':len(active),'active_supplement_items':len(items),'subtitle_candidates_pending_attribution':len(subtitle_pending),'additional_subtitle_drafts':len(extra_pending),'editorial_holds':len(held),'kinds':dict(collections.Counter(x['kind'] for x in items)),'unique_entities':len({t for x in items for t in x.get('entities',[]) if t!='明前奶绿'}),'original_data_unchanged':unchanged,'original_vector_count':7621,'new_vectors_generated':0,'new_human_review':False,'target':'Independent text pilot only; other QQ bots are not modified.','subtitle_scan':load('work/self-audit-20261024/scan-report.json'),'extra_scan':load('work/self-audit-extra-20261024/scan-report.json'),'extra_extraction':load('work/self-audit-extra-20261024/extraction-report.json'),'social_extraction':load('work/social-supplement-20261024/extraction-report.json'),'social_review':load('work/social-supplement-20261024/review-report.json')}
    save('outputs/人物资料补充报告.json',report)
    md=f'''# 人物资料补充 · 2026-10-24

本轮已收集 B站 {report['collection']['bilibili_public_posts']} 条公开动态、微博 {report['collection']['weibo_public_posts']} 条公开动态，微博35页及10篇长文已处理，B站九段历史均翻至各自边界。仅覆盖当前账号可见的公开文字；图片链接保留但未全部OCR，删除、付费或私密内容不在此范围。

原字幕全库2,757,563条重新扫描了自身设定、经历、同行和宠物线索。本轮试聊补充包含{len(CORE)}条常驻背景、{len(EDITORIAL)}段编辑核对往事、{len(active)}条本人动态的模型检查资料。另有{len(subtitle_pending)}条字幕候选需要核对说话人、{len(extra_pending)}条更宽泛的字幕初稿，均未加入试聊；机器容易把念观众留言误当本人经历。模型检查不等于你已逐条认可，也不等于原声听校。更宽泛的字幕候选尚未全部逐窗提炼；原字幕可全文检索，不能说所有直播的每件事都已识别。

固定19岁、3月4日生日、花店店员与店长、LLL成员已单独整理。莉莉丝、发卡、露露、雫るる、lulu、店长、坚果、果仁等叫法会关联检索；“你们三个”“那次”可承接近期话题。其他同行和公开活动也在补充里，不局限于用户列举的几项。

坚果：2025年11月公开片段有“没有找到”“可能还活着”的说法，现有证据不能确定死亡、死因和事故日；保留失去店长陪伴的往事，不编成他现在还在身边。片段为本地自动转写，未逐句听校。

原来你认可的7,621条事实/经历及语义向量没有改写。这轮新增内容用单独的本地索引和来源文件接入文字试聊，没有重新发送整批数据到智谱。待核对与冲突条目独立留存，未放进本轮试聊。

文字试聊：http://127.0.0.1:49850/\n资料核对页：http://127.0.0.1:49850/knowledge

文件：data/self-supplement/items.json，data/self-supplement/library.sqlite3，review/self-supplement-20261024/held.json，sources/social-20261024/。这里的新资料尚未接入其他旧QQ机器人。恢复时用 review/versions/before-self-supplement/ 中的服务器与聊天模块。
'''
    (R/'outputs/人物资料补充说明.md').write_text(md,encoding='utf-8')
    payload=json.dumps({'items':items+subtitle_pending+extra_pending,'report':{k:report[k] for k in ['always_present_core','editorial_memory_capsules','machine_checked_additions','active_supplement_items','subtitle_candidates_pending_attribution','additional_subtitle_drafts','editorial_holds','new_human_review']},'coverage':report['collection']},ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>奶绿 · 人物资料补充</title><style>body{font:16px/1.75 'Microsoft YaHei',sans-serif;color:#243d34;background:#f4f7f5;max-width:1050px;margin:30px auto;padding:0 20px}input,select,button{font:inherit;padding:9px;margin:6px;border:1px solid #afc8ba;border-radius:6px}article{background:white;padding:20px;border:1px solid #d4e1d9;border-radius:10px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 inherit;background:#f3f6f4;padding:14px}.muted{color:#61766c;font-size:14px}a{color:#24694c}</style><h1>奶绿 · 人物资料补充</h1><p><a href="/">返回文字试聊</a></p><p id="coverage"></p><p>这轮新资料包含编辑核对的固定背景与往事，以及经模型检查的试用资料。模型检查不等于你已逐条认可，字幕与片段也不等于原声听校。原7,621条已认可事实/经历及向量保留。字幕候选中可能混入念观众留言，先不作为她本人的经历。</p><p class="muted">图片尚未全部识字；原字幕虽然全文可检索，更宽泛的自身经历候选还未逐窗提炼完。坚果片段保留“没有找到、可能还活着”的不确定性。旧直播偏好不会直接视为现状。</p><input id="q" placeholder="找人物、经历或关键词" aria-label="搜索人物资料"><select id="filter"><option value="all">全部</option><option value="editorial">编辑核对</option><option value="machine">本人动态，模型检查</option><option value="pending">字幕候选，未接入试聊</option></select><span id="count"></span><div id="list"></div><button id="more">再看50条</button><script>const data=PAYLOAD;let shown=50;const $=x=>document.getElementById(x);$('coverage').textContent=`本次公开文字：B站 ${data.coverage.bilibili_public_posts} 条、微博 ${data.coverage.weibo_public_posts} 条。已接入试聊 ${data.report.active_supplement_items} 条；另有 ${data.report.subtitle_candidates_pending_attribution+data.report.additional_subtitle_drafts} 条字幕候选待核对。`;function draw(){let q=$('q').value.trim().toLowerCase(),f=$('filter').value;const xs=data.items.filter(x=>(f==='all'||(f==='editorial'&&x.editorial_checked)||(f==='machine'&&x.active_in_text_pilot&&!x.editorial_checked)||(f==='pending'&&!x.active_in_text_pilot))&&JSON.stringify([x.text,x.entities,x.topics]).toLowerCase().includes(q));$('count').textContent=` ${xs.length} 条`;$('list').replaceChildren();for(const x of xs.slice(0,shown)){const card=document.createElement('article'),p=document.createElement('p'),meta=document.createElement('div');p.textContent=x.text;meta.className='muted';meta.textContent=(x.core?'常驻背景 · ':'')+(x.editorial_checked?'编辑核对原文':x.active_in_text_pilot?'本人动态 · 模型检查，待你确认':'字幕候选 · 未接入试聊')+' · 来源时间：'+x.source_record_date+' · '+({stable:'固定背景',historical:'过去的记录',planned:'当时的计划',uncertain:'尚不确定'}[x.time_scope]||'待核对')+' · '+({lore:'花店世界观',joke:'玩笑语境',public_life:'公开生活与活动'}[x.realm]||'公开记录');card.append(p,meta);if(x.uncertainty){const u=document.createElement('p');u.textContent=x.uncertainty;card.append(u)}const d=document.createElement('details'),s=document.createElement('summary');s.textContent='查看原文和出处';d.append(s);for(const r of x.source_refs){const a=document.createElement('a');a.href=r.origin||'#';a.target='_blank';a.rel='noopener noreferrer';a.textContent=r.source_id+(r.start_seconds!==undefined?' · '+r.start_seconds+' 秒':'');const pre=document.createElement('pre');pre.textContent=r.quote;d.append(a,pre)}card.append(d);$('list').append(card)}$('more').hidden=shown>=xs.length}$('q').oninput=$('filter').onchange=()=>{shown=50;draw()};$('more').onclick=()=>{shown+=50;draw()};draw();</script></html>'''.replace('PAYLOAD',payload)
    (R/'outputs/人物资料补充核对.html').write_text(page,encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['always_present_core','editorial_memory_capsules','machine_checked_additions','active_supplement_items','editorial_holds','unique_entities']},ensure_ascii=False))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
