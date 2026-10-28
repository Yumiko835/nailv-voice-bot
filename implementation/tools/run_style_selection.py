
# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import concurrent.futures,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(project_path(''));sys.path.insert(0,str(ROOT/'tools'))
import publish_nailv_library as p
from nailv_study_client import StudyClient
pack=p.load('work/style-v3-20261024/approved-episode-candidates.json')['items']+p.load('work/style-v3-20261024/raw-calling-candidates.json')['items']
seen={x.get('episode_id',x['id']) for x in pack}
old=p.load('style/v2/表达选段库.json')['items'];wanted={x['episode_id'] for x in old if x.get('episode_id') and x['episode_id'] not in seen}
all_episodes=p.load('persona/behavior-episodes.json')['items']
extra=[]
for e in all_episodes:
    if e['id'] not in wanted:continue
    s=e['samples'][0]
    extra.append({'id':e['id']+'-general','episode_id':e['id'],'user_context':s['user'],'reply_lines':s['reply'].splitlines(),'source_refs':s.get('source_refs',e['source_refs']),'source_record_date':e['source_record_date'],'tags':['general'],'audio_verified':False})
extra=sorted(extra,key=lambda x:hashlib.sha256(x['id'].encode()).hexdigest())[:80];pack+=extra
p.save('work/style-v3-20261024/selection-input.json',{'items':pack,'extra_general':len(extra)})
prompt='''你是明前奶绿的中文直播语料编辑。仅从原文里选本人说给观众的、短而完整的回应，供学措辞与接话，不学直播喊感谢。输入context是上下文，不可用于输出行号；reply_lines是唯一允许选择的行数组。
非常重要：lo和hi只能是reply_lines的0基行号。如果reply_lines只有1行，唯一合法区间是0到0，绝不能填context的行号！选1到8连续行、总计不超过160字，不截断未完句。
原文可能读SC、接别的话题或夹歌词；归属不明、像歌词、句子不完整、仅“谢谢”或长串卡顿则take:false。不要将观众说的妈妈/爱你当本人回应。可以保留短促应声、mua和少量语气重复，不用把每段变成“安抚—解释—追问”。
只输出JSON：{"items":[{"id":"输入原ID","take":true,"lo":0,"hi":0,"act":"calling/kiss/affection/comfort/blessing/celebrate/banter/clarify/refusal/opinion/daily/other","reason":"最多30字的取舍依据","wording":"不超过40字的具体用词/语序/收句特点","avoid":"不超过40字的不适用语境"}]}。每个输入只输出一项；不要改写和补写原话，lo、hi不选时为null。'''
def payload(batch):return [{'id':x['id'],'user_context':x['user_context'],'context':x.get('context_lines',x['source_refs'][0]['quote'].splitlines()),'reply_lines':x['reply_lines'],'legal_line_numbers':list(range(len(x['reply_lines'])))} for x in batch]
def run(i,batch):
    messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'items':payload(batch)},ensure_ascii=False)}]
    result=StudyClient().call(messages,f'select-v3-{i:03d}',4096,.3)
    p.save(f'work/style-v3-20261024/selection-results/{i:03d}.json',result)
    return len(batch)
batches=[pack[i:i+10] for i in range(0,len(pack),10)];done=0
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(run,i,b) for i,b in enumerate(batches)]
    for future in concurrent.futures.as_completed(futures):
        done+=future.result()
        if done%50<10 or done==len(pack):print(json.dumps({'selected_inputs_done':done,'total':len(pack)}),flush=True)

# A clearer line-number specification is retested on exactly the same calling set.
task=p.load('work/style-v3-20261024/paired-analysis-tasks.json')['tasks'][0]
original=json.loads(task['messages'][1]['content'])['items']
messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'items':[{**x,'legal_line_numbers':list(range(len(x['reply_lines'])))} for x in original]},ensure_ascii=False)}]
p.save('work/style-v3-20261024/paired-analysis-retest-task.json',{'messages':messages,'same_inputs_for_both_models':True})
for model in [setting("chat_model","deepseek-flash"),'deepseek-v4-pro']:
    result=StudyClient(model).call(messages,'paired-calling-retest',4096,.3)
    p.save('work/style-v3-20261024/comparison/'+model+'-calling-retest.json',result)
    print(json.dumps({'retest_complete':model}),flush=True)
