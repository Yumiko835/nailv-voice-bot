"""Conservative continuity plan: real adjacent source intervals, never concatenate clips."""

# Public-release configuration shim. Production files are not modified.
import sys as _public_sys
from pathlib import Path as _PublicPath
_public_repo = next((p for p in _PublicPath(__file__).resolve().parents if (p/'release_config.py').is_file()), None)
if _public_repo is None:
    import os as _public_os
    _public_repo = _PublicPath(_public_os.environ['NAILV_SOURCE_ROOT']).resolve()
_public_sys.path.insert(0, str(_public_repo))
from release_config import project_path, dependency_path, secret_path, setting
from common import *
setup()
import copy,re,unicodedata
U=ROOT/'voice/training/cosyvoice2-curated-v2-20261026'
S=ROOT/'voice/training/v5dev-newsource-20261025'
data=read(U/'curated-dataset.json');screen=read(S/'analysis/screen.json')
def chars(s):return ''.join(c for c in s if not c.isspace() and not unicodedata.category(c).startswith('P'))
def overlap(a,b):return a['source_id']==b.get('source_id') and min(a['end'],b.get('end',-1))>max(a['start'],b.get('start',1e10))-.25
refs=read(ROOT/'voice/comparison/cosyvoice2-20261026/prompts/manifest.json')['prompts']
protected=data['validation']+data['holdout']
original_refs=read(ROOT/'voice/training/v2proplus-newsource-20261025/prompts/manifest.json')
protected+=list(original_refs['prompts'].values())+list(original_refs.get('alternates',{}).values())
rows=sorted(data['train'],key=lambda x:(x['source_id'],x['start']))
used=set();pairs=[]
for a,b in zip(rows,rows[1:]):
    gap=b['start']-a['end'];duration=b['end']-a['start']
    if a['id'] in used or b['id'] in used or a['source_id']!=b['source_id'] or not (-.05<=gap<=.65 and 6<=duration<=15):continue
    if not (a.get('speech_act') in {'reply','explain','story'} and b.get('speech_act') in {'reply','explain','story'}):continue
    # A protected interval or any third detected utterance in the true gap disqualifies the union.
    union=a|{'end':b['end']}
    if any(overlap(union,p) for p in protected):continue
    others=[x for x in screen.values() if x['id'] not in {a['id'],b['id']} and x['source_id']==a['source_id'] and min(x['end'],b['start'])>max(x['start'],a['end'])+.05]
    if others:continue
    tail=len(chars(a['text']));head=chars(b['text']);base=chars(a['text'])
    if not base or not head:continue
    # Keep existing spoken words. Only distinguish actual pause punctuation.
    text=a['text'].rstrip('，。！？；：、…')+('，' if gap<.25 else '。')+b['text']
    assert chars(text)==chars(a['text'])+chars(b['text'])
    rid='CV3C'+hashlib.sha256((a['id']+'|'+b['id']).encode()).hexdigest()[:12]
    pairs.append({'id':rid,'source_id':a['source_id'],'source_path':a['source_path'],'source_sha256':a['source_sha256'],
        'start':a['start'],'end':b['end'],'seconds':duration,'text':text,'speech_act':a['speech_act'],
        'constituents':[a['id'],b['id']],'actual_gap_seconds':gap,'continuous_original_source':True,
        'synthetic_silence_or_concatenation':False,'text_human_verified':False})
    used.update([a['id'],b['id']])
manifest={'train':[copy.deepcopy(x) for x in rows if x['id'] not in used], 'continuity_candidates':pairs,
          'validation':copy.deepcopy(data['validation']),'holdout':copy.deepcopy(data['holdout']),
          'parent_dataset_sha256':sha(U/'curated-dataset.json'),'parent_selected_minutes':data['train_minutes'],
          'original_audio_modified':False,'protected_intervals_enforced':True,'unrelated_clip_stitching':False,
          'purpose':'Preserve oral characters and real clause-to-clause transitions, retain calm/reply/story variety; acoustic/speech-act labels remain automatic.'}
write(T/'dataset-plan.json',manifest)
print(json.dumps({'retained_short_clips':len(manifest['train']),'real_continuous_candidates':len(pairs),'continuous_minutes':sum(x['seconds'] for x in pairs)/60},ensure_ascii=False),flush=True)
