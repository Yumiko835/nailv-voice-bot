"""Source-grounded lexical analysis; experimental layer never rewrites accepted facts."""

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
import collections, concurrent.futures, hashlib, json, os, re, shutil, sys, time

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as p
import extract_nailv_library as engine
OUT=ROOT/'style/v2'
PROBES='就是|不是|然后|其实|反正|所以|但是|不过|主要是|问题是|怎么说|怎么说呢|我觉得|我感觉|我寻思|我以为|我跟你说|你知道吗|你想想|你看|就是说|也就是说|说实话|讲道理|确实|确实是|还挺|蛮|有点|有一点|不至于|倒不至于|倒也|也不是|也不是说|那倒是|那不就|这不就|这不|这有什么|那有什么|有什么好|不然呢|什么叫|怎么就|怎么会|为什么要|凭什么|哪有|对吧|是吧|是不是|对啊|对的|好吧|行吧|算了|算了吧|得了|就好了|就行了|就完了|你要是|如果说|但凡|只要|那肯定|肯定会|本来就|不就是|不一定|不太|也没|也就|我真的|真的很|真厉害|恭喜|夸夸你|你信我|抱抱|mua|哎呀|哎哟|啊这|哈|哈哈|哈哈哈|唉|哦|呀|呐|好家伙|怎么个事|家人们|宝宝|老婆|首先|其次|总之|理解你的|你的感受'.split('|')
FORMS={
 '纠正前提':r'不是|不对|什么叫|怎么就|我寻思|我以为',
 '顺势反问':r'那不就|这不|有什么|不然呢|怎么会|凭什么|是不是',
 '主观限定':r'我觉得|我感觉|我寻思|其实|主要是|也不是|不至于|倒也|不一定',
 '条件接结果':r'你要是|如果|只要|那就|就好了|就行了|算了',
 '拉对方进话题':r'对吧|是吧|你看|你想|我跟你说|你知道吗',
 '短句加重':r'(真厉害|恭喜|好起来|肯定会|不至于|没有|算了|夸夸你|抱抱)',
 '口语转折':r'但是|不过|然后|反正|后来|结果|当时',
}
SCENES={
 'comfort':r'安慰|难过|焦虑|失落|内耗|低落|自卑|烦恼|困境|压力',
 'celebrate':r'成功|恭喜|考试.*通过|考过|夸赞|夸奖|报喜|进展',
 'blessing':r'生日|祝福|鼓励|面试|加油|手术',
 'tease':r'调侃|玩笑|逗|沉迷|年轻|嘲讽',
 'clarify':r'质疑|误解|澄清|指责|贴标签|闹不愉快|背刺',
 'relationship':r'恋爱|感情|表白|告白|分手|暧昧|交往',
 'boundary':r'拒绝|隐私|秘密|真名|越界|底线|骚扰|抢票',
 'opinion':r'评价|观点|喜好|喜欢|角色|看法|建议|选择',
}

def save(name,obj):p.save('style/v2/'+name,obj)
def compact(s):return re.sub(r'\s+','',s)

def scan():
    import jieba_fast
    OUT.mkdir(parents=True,exist_ok=True)
    tokenizer=jieba_fast.Tokenizer();tokenizer.tmp_dir=str(ROOT/'cache/style-v2/tokenizer')
    Path(tokenizer.tmp_dir).mkdir(parents=True,exist_ok=True)
    episodes=p.load('persona/behavior-episodes.json')['items']
    unigram=collections.Counter();collocations=collections.Counter();colloc_sources=collections.defaultdict(set)
    for e in episodes:
        text=compact(e['samples'][0]['reply']);tokens=list(tokenizer.cut(text,HMM=False))
        for n in (2,3,4):
            for i in range(len(tokens)-n+1):
                phrase=''.join(tokens[i:i+n])
                if 3<=len(phrase)<=12 and re.fullmatch(r'[\u3400-\u9fff]+',phrase):
                    collocations[phrase]+=1;colloc_sources[phrase].add(e['source_refs'][0]['source_id'])
    candidates=[x for x,c in collocations.most_common() if c>=8 and len(colloc_sources[x])>=6 and re.search(r'我|你|那|这|就|吧|啊|是|有|会|觉得|其实|然后|不',x)][:220]
    phrases=list(dict.fromkeys(PROBES+candidates))
    counts=collections.Counter();df=collections.Counter();by_genre=collections.defaultdict(collections.Counter)
    all_sources=p.load('sources/manifest.json')['sources'];done=chars=lines=0
    for source in all_sources:
        path=ROOT/source['transcript_path']
        if not path.exists():continue
        text=path.read_text(encoding='utf-8-sig');flat=compact(text)
        if not flat:continue
        done+=1;chars+=len(flat);lines+=len(text.splitlines())
        unigram.update(x for x in tokenizer.cut(flat,HMM=False) if re.fullmatch(r'[\u3400-\u9fff]{2,8}',x))
        genre=source.get('source_genre_hint','unspecified')
        for phrase in phrases:
            count=flat.count(phrase)
            if count:counts[phrase]+=count;df[phrase]+=1;by_genre[genre][phrase]+=count
        if done%200==0:print(json.dumps({'scan_records':done,'of_nonempty':1631}),flush=True)
    observations=[]
    for phrase in phrases:
        hits=[e for e in episodes if phrase in compact(e['samples'][0]['reply'])]
        observations.append({'phrase':phrase,'full_archive_occurrences':counts[phrase],'full_archive_records':df[phrase],
            'by_title_genre':{g:c[phrase] for g,c in by_genre.items()},'accepted_response_episodes':len(hits),
            'accepted_response_records':len({e['source_refs'][0]['source_id'] for e in hits}),
            'evidence_episode_ids':[e['id'] for e in hits[:5]]})
    save('词语与搭配统计.json',{'created_at':p.now(),'nonempty_records_scanned':done,'non_whitespace_characters':chars,'transcript_lines':lines,
        'counting':'Whitespace removed; str.count non-overlapping substring occurrences. Tokens jieba_fast HMM=False. No attribution from raw frequency alone.',
        'raw_attribution_warning':'Whole archive includes read chat, songs, videos, games and other speakers; genre is title hint only.',
        'approved_episode_count':len(episodes),'lexical_observations':observations,
        'top_segmented_words':[{'word':w,'count':c} for w,c in unigram.most_common(250)],
        'response_collocations':[{'phrase':w,'occurrences':collocations[w],'records':len(colloc_sources[w])} for w in candidates],
        'audio_prosody_inferred':False})
    # Diverse candidates for model-assisted selection of readable, contiguous original passages.
    candidates=[]
    for e in episodes:
        sample=e['samples'][0];text=sample['reply'];tags=[k for k,r in FORMS.items() if re.search(r,text)]
        if not tags or not 12<=len(text)<=400 or len(re.findall(r'[A-Za-z]',text))>30:continue
        scenes=[k for k,r in SCENES.items() if re.search(r,e['name']+' '+e['trigger'])] or ['daily']
        candidates.append({'episode_id':e['id'],'scene_context':sample['user'],'scene_tags':scenes,'form_tags':tags,
            'lines':text.splitlines(),'source_id':e['source_refs'][0]['source_id'],'form_score':len(tags),
            'source_refs':e['source_refs'],'source_date':e['source_record_date']})
    candidates.sort(key=lambda x:(-x['form_score'],hashlib.sha256(x['episode_id'].encode()).hexdigest()))
    selected=[];record_counts=collections.Counter();scene_counts=collections.Counter()
    for row in candidates:
        scene=row['scene_tags'][0]
        if record_counts[row['source_id']]>=2 or scene_counts[scene]>=90:continue
        selected.append(row);record_counts[row['source_id']]+=1;scene_counts[scene]+=1
        if len(selected)==600:break
    save('待整理原话.json',{'items':selected,'status':'experimental; source replies accepted, excerpt selection pending'})
    print(json.dumps({'scan_complete':done,'phrases':len(phrases),'curation_candidates':len(selected),'candidate_records':len(record_counts)}),flush=True)

CURATION='''你只做字幕表达选段，不生成新台词。输入是已获用户整版认可的明前奶绿互动原文，但仍可能有ASR错字。每条给编号行。
选择其中可独立理解、措辞有价值、自然口语的连续回应，排除明显错字乱码、读礼物/弹幕名单、歌曲、播放的视频、第三方私事、脱离上下文的辱骂和无法分清说话人的内容。不为凑数保留。
每项只输出一个连续区间，lo/hi从0起且含尾；通常2-8行，最多200字。不要改错字，不要拼接，不要编证据。情境只是概括，不是逐字问题。
tags仅从：纠正前提、顺势反问、主观限定、条件接结果、拉对方进话题、短句加重、口语转折 中选。只标真实出现的，不猜声音。
只输出JSON：{"items":[{"episode_id":"输入的ID","lo":0,"hi":3,"tags":["纠正前提"],"wording_note":"20字内说明如何用词接句，而非性格评价"}]}。不合适的条目完全省略。'''

def curate():
    candidates=p.load('style/v2/待整理原话.json')['items'];lookup={x['episode_id']:x for x in candidates}
    client=engine.APIClient(engine.Budget(cap=49-__import__('nailv_text_core').embed_spent()))
    batches=[candidates[i:i+40] for i in range(0,len(candidates),40)];results=[]
    def call(pair):
        idx,batch=pair
        data=[{'episode_id':x['episode_id'],'context':x['scene_context'],'lines':dict(enumerate(x['lines']))} for x in batch]
        result=client.call('lexical-v2-curate-'+str(idx),'style-lexical-v2',[{'role':'system','content':CURATION},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],4096,2.)
        if result['status']!='ok':
            # Truncated JSON is not accepted; split only failed public batches once.
            rows=[]
            for half in range(2):
                sub=data[half*20:(half+1)*20]
                part=client.call('lexical-v2-curate-'+str(idx)+'-half'+str(half),'style-lexical-v2',[{'role':'system','content':CURATION},{'role':'user','content':json.dumps(sub,ensure_ascii=False)}],4096,2.)
                if part['status']!='ok':raise RuntimeError('Split curation incomplete: '+str(idx))
                rows.extend(part['response'].get('items',[]))
            result={'status':'ok','response':{'items':rows}}
        return idx,result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in concurrent.futures.as_completed([pool.submit(call,x) for x in enumerate(batches)]):
            idx,res=future.result();results.append((idx,res));print(json.dumps({'curated_batches':len(results),'total':len(batches)}),flush=True)
    bank=[];errors=[]
    for idx,res in sorted(results):
        batch_ids={x['episode_id'] for x in batches[idx]};seen=set()
        for obj in res['response'].get('items',[]):
            eid=obj.get('episode_id');lo=obj.get('lo');hi=obj.get('hi')
            if eid not in batch_ids or eid in seen or type(lo)!=int or type(hi)!=int:errors.append({'batch':idx,'reason':'invalid or duplicate id/indices'});continue
            row=lookup[eid];seen.add(eid)
            if not 0<=lo<=hi<len(row['lines']):errors.append({'id':eid,'reason':'invalid interval'});continue
            excerpt='\n'.join(row['lines'][lo:hi+1])
            if not 8<=len(excerpt)<=260 or not any(compact(excerpt) in compact(r['quote']) for r in row['source_refs']):errors.append({'id':eid,'reason':'length or provenance'});continue
            tags=[t for t in obj.get('tags',[]) if t in FORMS and re.search(FORMS[t],excerpt)]
            if not tags:continue
            bank.append({'id':'lexical-'+eid,'episode_id':eid,'context_paraphrase':row['scene_context'],'reply_excerpt':excerpt,
                'scene_tags':row['scene_tags'],'form_tags':tags,'wording_note':str(obj.get('wording_note',''))[:100],
                'source_refs':row['source_refs'],'source_date':row['source_date'],'reply_lines_in_accepted_sample':[lo,hi],
                'excerpt_is_verbatim':True,'context_is_verbatim':False,'source_review':'approved',
                'style_selection_review':'experimental model-assisted; awaiting user style judgment','audio_verified':False})
    save('表达选段库.json',{'items':bank,'validation_errors':errors,'created_at':p.now(),'source_records':len({x['source_refs'][0]['source_id'] for x in bank})})
    print(json.dumps({'style_bank_items':len(bank),'provenance_errors':len(errors)}),flush=True)

def report():
    stats=p.load('style/v2/词语与搭配统计.json');bank=p.load('style/v2/表达选段库.json')['items'];rows={x['phrase']:x for x in stats['lexical_observations']}
    md=['# 奶绿的措辞与接句：第二版试验记录','','这次检查的是具体用词、搭配和句子组织。风格判断仍以你的试聊感受为准。',
        '',f"全文扫描：{stats['nonempty_records_scanned']:,}份非空字幕；另从1,844条已认可互动中整理了{len(bank)}段可追溯原话。全文词频含视频、弹幕和其他人，不能直接视为本人词频。",'',
        '|词语或搭配|全文出现次数|已认可回应中涉及录播数|','|---|---:|---:|']
    for phrase in ['我觉得','我感觉','我寻思','我以为','不是','什么叫','那不就','这有什么','不至于','你要是','就好了','算了','对吧','其实','反正','真厉害','夸夸你','呐','好家伙']:
        x=rows[phrase];md.append(f"|{phrase}|{x['full_archive_occurrences']:,}|{x['accepted_response_records']}|")
    explanations={
      '纠正前提':'常能看到她抓住对方用的一个词，接“不是／什么叫……”再改写前提。重点是接住具体措辞，不是泛泛地“我理解你的感受”。',
      '顺势反问':'“那不就……吗／这有什么……”把判断压进短反问。只在推论或熟悉的玩笑里用，难过时不自动反问。',
      '主观限定':'“我觉得／我寻思／也不是／不至于”给观点留范围。不是每次把自己的判断写成对方应当接受的结论。',
      '条件接结果':'“你要是……那就……／……就好了”把建议落在具体条件上；不用动辄整理成三点计划。',
      '拉对方进话题':'“对吧／你看／你想”通常接在一段理由后面确认，不是随机撒在每句话末尾。',
      '短句加重':'肯定、否定或祝福有时用短句再重复核心词。保留这种着力方式，去掉ASR逐字卡顿。',
      '口语转折':'“就是／然后／反正／结果”承担解释、转折、收束，句子可以边说边补一个限定，但不抄录音的全部停顿。',
    }
    for tag,explanation in explanations.items():
        md.extend(['','## '+tag,'',explanation])
        chosen=[];records=set()
        for x in bank:
            sid=x['source_refs'][0]['source_id']
            if tag in x['form_tags'] and sid not in records:
                chosen.append(x);records.add(sid)
            if len(chosen)==2:break
        for x in chosen:
            ref=x['source_refs'][0];md.extend(['','情境：'+x['context_paraphrase'],'','> '+x['reply_excerpt'].replace('\n','\n> '),'',f"出处：{x['episode_id']}，{ref['start_seconds']}—{ref['end_seconds']}秒（原证据区间）；选段行号见JSON。"])
    md.extend(['','## 放进聊天时怎么用','','每轮根据对方的具体话和前文，从同类处境取少量选段看措辞，再组织新回答；不复读经历、不固定添加口癖、不把温柔和反问做成统一模板。',
        '不知道对方提到哪件往事时，自然追问是哪件事、让对方提醒，不编造共同记忆。系统说明留在界面，不塞进角色台词。',
        '新风格层与已认可事实、人物经历、语义索引分开保存。字幕没有可靠的真实重音、轻笑和叹气信息，本次没有据此训练或宣称改好了音色。'])
    (OUT/'奶绿的措辞与接句.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    action=sys.argv[1]
    if action=='scan':scan()
    elif action=='curate':curate();report()
