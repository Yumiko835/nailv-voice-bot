"""Offline, source-grounded style observations. Does not rewrite accepted persona data."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import collections,hashlib,json,sys
from pathlib import Path

ROOT=Path(project_path(''))
sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as p


def main():
    episodes=p.load('persona/behavior-episodes.json')['items'];groups=p.load('persona/behaviors.json')['items']
    assert len(episodes)==1844 and all(x['review']=='approved' for x in episodes)
    phrases=[]
    for word in ['就是','不是','哈哈','对吧','我觉得','其实','好吧','确实','哎呀','反正','这不','怎么说','唉','呐']:
        hits=[x for x in episodes if word in x['samples'][0]['reply']]
        refs=[]
        for item in hits:
            if item['source_refs'][0]['source_id'] in {r['source_id'] for r in refs}:continue
            refs.append({'episode_id':item['id'],**item['source_refs'][0]})
            if len(refs)==3:break
        phrases.append({'phrase':word,'episodes_containing':len(hits),'distinct_records':len({x['source_refs'][0]['source_id'] for x in hits}),'fraction_in_selected_episodes':round(len(hits)/len(episodes),4),'examples':refs})
    # Verbatim contiguous excerpts. Contexts were accepted as paraphrases, not literal audience questions.
    wanted=[('behavior-group-002','肯定会的\n百分百会的\n你信我'),('behavior-group-005','这不很正常吗'),('behavior-group-009','真厉害OMG\n真厉害'),('behavior-group-010','不能\n我这个手速你指望我帮你抢到\n你想多了'),('behavior-group-011','什么叫我年轻的时候玩网游有多沉迷\n我现在就很年轻')]
    excerpts=[]
    for group_id,needle in wanted:
        group=next(x for x in groups if x['id']==group_id)
        sample=next(s for s in group['samples'] if needle in s['reply'])
        assert any(''.join(needle.split()) in ''.join(ref['quote'].split()) for ref in sample['source_refs'])
        excerpts.append({'id':'style-'+group_id,'behavior_id':group_id,'name':group['name'],'context_paraphrase':sample['user'],'reply_excerpt':needle,'excerpt_is_verbatim':True,'context_is_verbatim':False,'source_refs':sample['source_refs'],'source_review':'approved','new_style_interpretation_review':'draft'})
    analysis={'created_at':p.now(),'scope':'Counts in 1844 selected accepted interaction episodes, not random full-stream frequency or audio prosody. ASR errors and laughter transcription remain possible.','source_edition_acceptance_id':p.load('review/全量版用户认可.json')['id'],'selected_episode_count':1844,'unique_records':len({x['source_refs'][0]['source_id'] for x in episodes}),'phrase_observations':phrases,'excerpts':excerpts,'audio_prosody_inferred':False,'new_style_rules_review':'draft; for experimental text pilot only'}
    p.save('style/表达观察.json',analysis);p.save('style/示范选段.json',{'items':excerpts})
    instructions='''这是“明前奶绿风格AI”的实验性文字试聊。你不是主播本人；有人问身份时如实说明，不要每轮重复说明。
用人物骨架确定互动倾向，用相关原话感受句式和回应姿态。下面的细节建议仍需用户试聊确认，不能当作已证实的永久性格。
说话自然、口语化，普通聊天通常一至三句；需要解释时可以多说。直播字幕的逐行换行、卡顿和识别错字不应复制成聊天格式。
“就是、对吧、我觉得、其实”等在样本里常见，但也是普通口语；只在表达需要时自然出现，不规定配额，不一口气堆多个。“呐”证据少，不作为标志口癖。
对调侃或误解可以用有具体内容的反问、澄清、自嘲；对认真倾诉可温和、直接、给贴近处境的回应。不要把所有情境都演成嘴硬或撒娇，不强行先安慰再建议再祝福。
读前文，区分对方情绪和自己的回应姿态。对方已经缓过来并想换话题时，跟着转，不继续长篇劝慰。对关系亲近程度不确定时不擅自喊老婆、认领恋爱关系。
允许平常地回答，不必每条表演个性。不要每条哈哈哈、哎、唉或反问，不使用舞台动作括号冒充已经发出声音。
输出只有建议的表达计划，尚无任何语音合成。不得声称已经轻笑、叹气、发语音、登录QQ或替用户办事。
'''
    (ROOT/'style/试聊表达建议.txt').write_text(instructions,encoding='utf-8')
    lines=['# 新奶绿：文字表达观察（试验稿）','','这份观察用于下一步文字试聊，尚未获得风格相似度人评。人物资料的认可记录保持不变。','','## 观察范围','','统计来自已认可的1,844条互动片段，不能当作全部直播的随机频率；字幕中的哈哈也不能证明真实笑声的形态。','','|表达|含该表达的片段|涉及录播|','|---|---:|---:|']
    for row in phrases:lines.append(f'|{row["phrase"]}|{row["episodes_containing"]}|{row["distinct_records"]}|')
    lines.extend(['','## 用法','','高频词只提示自然语言习惯，不单独证明人物特征。重点比较具体场景里如何接话、澄清、调侃、安慰和划界。相同词语可有不同态度；没有听原声时，不据字幕猜音量、重音或轻笑的位置。','','## 有出处的选段'])
    for row in excerpts:lines.extend(['','### '+row['name'],'','情境概括：'+row['context_paraphrase'],'','> '+row['reply_excerpt'].replace('\n','\n> '),'','来源：'+', '.join(r['source_id']+' @ '+str(r['start_seconds'])+'秒' for r in row['source_refs'])])
    lines.extend(['','## 实验规则','',''+instructions])
    (ROOT/'style/表达风格观察.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'episodes':len(episodes),'phrases':len(phrases),'source_grounded_excerpts':len(excerpts),'style_status':'trial, awaiting user comparison','paid_model_calls':0},ensure_ascii=False))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
