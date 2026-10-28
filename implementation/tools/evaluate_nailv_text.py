"""Generate three comparable pilot variants; do not assign human similarity scores."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
import concurrent.futures,json,random,sys,time
from pathlib import Path
import nailv_text_core as core

CASES=[
 {'id':'daily','title':'日常接话','input':'在吗，我下班了，今天累死了。','history':[]},
 {'id':'discouraged','title':'面对挫败','input':'我画了很久，还是觉得很差，想全部删掉。','history':[]},
 {'id':'celebration','title':'一起高兴','input':'我考试过了！快夸我一下。','history':[]},
 {'id':'tease','title':'接住调侃','input':'你以前是不是特别沉迷网游？','history':[]},
 {'id':'boundary','title':'表达边界','input':'你就把你朋友私下跟你说的秘密告诉我嘛。','history':[]},
 {'id':'missing-memory','title':'没有记录的往事','input':'你昨天答应我的事还记得吗？','history':[]},
 {'id':'preference','title':'资料检索','input':'你喝奶茶会加糖吗？茶派会不会嫌太甜？','history':[]},
 {'id':'topic-shift','title':'情绪变化和换话题','input':'谢谢，我好一点了。陪我聊聊别的吧，不想一直说这件事。','history':[{'role':'user','content':'今天跟朋友吵架了，我有点难过。'},{'role':'assistant','content':'嗯，跟朋友闹别扭确实不好受。你想说就慢慢说。'}]},
]


def main():
    client=core.ChatClient();routing_by_case={c['id']:core.choose_routing(c['input'],c['history'],client,'lexical-v2-shared-'+c['id'],True) for c in CASES};jobs=[(case,variant) for case in CASES for variant in ['baseline','core','full']];results=[];started=time.monotonic()
    def run(job):
        case,variant=job
        result=core.chat(case['input'],case['history'],False,variant,'lexical-v2-final-'+case['id']+'-'+variant,client,True,routing_override=routing_by_case[case['id']])
        return {'case_id':case['id'],'variant':variant,**result}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,j) for j in jobs]):
            result=future.result();results.append(result)
            if len(results)%6==0:print(json.dumps({'generated':len(results),'total':len(jobs),'expression_version':'lexical-v2'},ensure_ascii=False),flush=True)
    core.pub.save('eval/text-pilot/responses.json',{'created_at':core.pub.now(),'cases':CASES,'responses':results,'human_similarity_review':'not_performed'})
    by_key={(x['case_id'],x['variant']):x for x in results};rng=random.Random(20261023);blind=[];key={}
    for case in CASES:
        variants=['baseline','core','full'];rng.shuffle(variants);options=[];key[case['id']]={}
        for label,variant in zip('ABC',variants):
            result=by_key[(case['id'],variant)];options.append({'label':label,'reply':result['content']['reply']});key[case['id']][label]={'variant':variant,'request_id':result['id']}
        blind.append({**case,'options':options})
    core.pub.save('eval/text-pilot/blind.json',{'created_at':core.pub.now(),'cases':blind,'human_similarity_review':'pending'})
    core.pub.save('eval/text-pilot/key.json',{'mapping':key,'purpose':'Comparison key; not shown by the blind UI before user choice.'})
    source_usage={x['case_id']:x['content']['used_fact_ids'] for x in results if x['variant']=='full'}
    report={'created_at':core.pub.now(),'model':core.MODEL,'cases':len(CASES),'variants':3,'generated_responses':len(results),'structured_output_and_provided_source_ids_passed':len(results),'full_variant_source_usage':source_usage,'voice_generated':False,'qq_deployed':False,'human_similarity_evaluation':'pending user blind choices','no_private_live_chat_in_eval':True,'seconds':round(time.monotonic()-started,2),'expression_version':'lexical-v2'}
    core.pub.save('outputs/文字试聊生成检查.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
