
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
import torch,onnxruntime,whisper,torchaudio,numpy as np,soundfile as sf,re,collections
from cosyvoice.tokenizer.tokenizer import CosyVoice3Tokenizer
plan=read(T/'dataset-plan.json');records=read(T/'continuous-audio.json');checks=read(T/'continuous-content-check.json')
U=ROOT/'voice/training/cosyvoice2-curated-v2-20261026';parents={r['id']:r for r in read(U/'curated-dataset.json')['train']}
train=plan['train'].copy();accepted=[];rejected=[]
for row in plan['continuity_candidates']:
    if checks[row['id']]['automatic_content_candidate']:
        train.append(records[row['id']]);accepted.append(row['id'])
    else:
        train.extend(parents[key] for key in row['constituents']);rejected.append(row['id'])
def act(row):
    text=row['text']
    if re.search(r'你[们]?|大家|是不是|知道吗|对吧',text) and re.search(r'[？?]|吗|怎么|什么',text):return '反问与向粉丝确认'
    if re.search(r'不是|没有|哪有|怎么可能|我错',text):return '否认或自我纠正'
    if re.search(r'意思|因为|所以|就是说|其实|比如',text):return '解释与转折'
    if re.search(r'哈哈|好笑|笑死|搞笑|什么鬼',text):return '接梗或调侃'
    return {'reply':'随口接话','explain':'解释叙述','story':'讲述经历'}.get(row.get('speech_act'),'自然口语')
for r in train:r['speech_action']=act(r)
assert len({r['id'] for r in train})==len(train)
split={'train':train,'validation':plan['validation'],'holdout':plan['holdout']}
tokenizer=CosyVoice3Tokenizer(str(BASE/'CosyVoice-BlankEN'));instruction=torch.tensor(tokenizer.encode('You are a helpful assistant.<|endofprompt|>'),dtype=torch.long)
options=onnxruntime.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
session=onnxruntime.InferenceSession(str(BASE/'speech_tokenizer_v3.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
tokenizer_sha=sha(BASE/'speech_tokenizer_v3.onnx')
# CPU feature frontend is sequential and bounded; the speech LM training and
# synthesis networks use CUDA. This avoids loading ONNX and train graphs together.
torch.set_num_threads(2);manifest={'train':[],'validation':[],'holdout':[],'train_minutes':sum(r['seconds'] for r in train)/60,
    'continuous_accepted':accepted,'continuous_content_rejected':rejected,'speech_action_counts':dict(collections.Counter(r['speech_action'] for r in train)),
    'speech_tokens':'fresh official v3 tokenizer, never reused v2 tokens','original_text_and_fillers_preserved':True,'human_likeness_verified':False}
for name,rows in split.items():
    for i,row in enumerate(rows,1):
        feature=T/'features'/(row['id']+'.pt');feature.parent.mkdir(parents=True,exist_ok=True);assert sha(row['path'])==row['sha256']
        if feature.exists():
            f=torch.load(feature,map_location='cpu',weights_only=True);assert f['source_sha256']==row['sha256'] and f['text']==row['text'] and f['tokenizer_sha256']==tokenizer_sha
        else:
            y,sr=sf.read(row['path'],dtype='float32',always_2d=True);wav=torch.from_numpy(y.mean(axis=1))[None,:]
            if sr!=16000:wav=torchaudio.functional.resample(wav,sr,16000)
            mel=whisper.log_mel_spectrogram(wav,n_mels=128)
            code=session.run(None,{session.get_inputs()[0].name:mel.numpy(),session.get_inputs()[1].name:np.array([mel.shape[2]],dtype=np.int32)})[0].flatten().astype(np.int64)
            assert len(code)>40 and code.min()>=0 and code.max()<6561
            torch.save({'id':row['id'],'text':row['text'],'text_token':torch.tensor(tokenizer.encode(row['text']),dtype=torch.long),'instruct_token':instruction,
                'speech_token':torch.from_numpy(code.copy()),'source_sha256':row['sha256'],'tokenizer_sha256':tokenizer_sha,'seconds':row['seconds']},feature)
        manifest[name].append(row|{'feature':str(feature)})
        if i%20==0 or i==len(rows):print(json.dumps({'features':name,'completed':i,'total':len(rows)}),flush=True)
assert not ({x['id'] for x in train}&{x['id'] for x in plan['validation']+plan['holdout']})
write(T/'dataset.json',manifest);print(json.dumps({'features_complete':True,'train':len(train),'minutes':manifest['train_minutes'],'continuous_accepted':len(accepted)}),flush=True)
