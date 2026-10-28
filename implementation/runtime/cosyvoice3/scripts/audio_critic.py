"""CPU-only acoustic screening, not listening or a validated personality MOS.

All source WAVs are read-only. Different texts use distributional prosody stats;
DTW and a flat-pitch veto require explicitly identical spoken words.
"""

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
os.environ['CUDA_VISIBLE_DEVICES']='-1'  # This process never consumes training VRAM.
import argparse,re,math,contextlib,collections,csv,gc,unicodedata
import numpy as np,soundfile as sf,torch,torchaudio,onnxruntime,parselmouth
from scipy import signal,ndimage
from difflib import SequenceMatcher
torch.set_num_threads(2)
VERSION='acoustic-critic-v1-cpu'
ASSESSMENT_VERSION='local-boundary-review-v2'
EMOTIONS={'HAPPY','SAD','ANGRY','NEUTRAL','FEARFUL','DISGUSTED','SURPRISED','OTHER','EMO_UNKNOWN'}
def spoken(s):return ''.join(c for c in re.sub(r'<[^>]*>|\[[^\]]*\]','',s) if c.isalnum())
def load_audio(path,rate):
    y,sr=sf.read(path,dtype='float32',always_2d=True);y=y.mean(axis=1)
    assert np.isfinite(y).all() and len(y)>sr*.2
    if sr!=rate:y=signal.resample_poly(y,rate//math.gcd(rate,sr),sr//math.gcd(rate,sr)).astype(np.float32)
    return y
def summary(values):
    x=np.asarray(values);x=x[np.isfinite(x)]
    return {'median':float(np.median(x)),'p10':float(np.percentile(x,10)),'p90':float(np.percentile(x,90))} if len(x) else None
def dtw(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    if len(a)<3 or len(b)<3:return None
    # Bound CPU/memory for arbitrary caller input. Absolute pitch is retained.
    a=np.interp(np.linspace(0,len(a)-1,min(160,len(a))),np.arange(len(a)),a);b=np.interp(np.linspace(0,len(b)-1,min(160,len(b))),np.arange(len(b)),b)
    prev=np.full(len(b)+1,np.inf);prev[0]=0.
    for x in a:
        cur=np.full(len(b)+1,np.inf)
        for j,y in enumerate(b,1):cur[j]=abs(x-y)+min(prev[j],cur[j-1],prev[j-1])
        prev=cur
    return float(prev[-1]/(len(a)+len(b)))
def acoustic(y,sr=24000,text=''):
    assert sr==24000
    sound=parselmouth.Sound(y,sampling_frequency=sr)
    pitch=sound.to_pitch_ac(time_step=.01,pitch_floor=65.,pitch_ceiling=600.,voicing_threshold=.5)
    f0=pitch.selected_array['frequency'];times=pitch.xs();voiced=f0>0;st=12*np.log2(f0[voiced]/100.)
    harmonicity=sound.to_harmonicity_ac(time_step=.01,minimum_pitch=65.,silence_threshold=.1,periods_per_window=4.5)
    hv=harmonicity.values[0];ht=harmonicity.xs();valid=(hv>-100)&np.isfinite(hv)
    # HNR is meaningful for periodic voiced portions, not natural unvoiced breaths.
    hvoiced=np.interp(ht,times,voiced.astype(float),left=0,right=0)>.5
    hvsel=valid&hvoiced
    _,ts,z=signal.stft(y,fs=sr,nperseg=1024,noverlap=784,boundary=None,padded=False);power=np.abs(z)**2+1e-18;freq=np.fft.rfftfreq(1024,1/sr)
    rms=np.sqrt(np.sum(power,axis=0));db=20*np.log10(rms+1e-12);threshold=max(-65.,float(np.percentile(db,90))-27.)
    active=db>threshold;active_idx=np.flatnonzero(active)
    start=float(ts[active_idx[0]]) if len(active_idx) else 0.;end=float(ts[active_idx[-1]]) if len(active_idx) else len(y)/sr
    middle=(ts>=start)&(ts<=end);pause=float(np.mean(~active[middle])) if middle.any() else 1.
    low=(freq>=100)&(freq<6000);high=(freq>=6000)&(freq<=10000);total=(freq>=100)&(freq<=10000)
    hf_ratio=10*np.log10(np.sum(power[high],axis=0)/np.sum(power[total],axis=0)+1e-12)
    frame_voiced=np.interp(ts,times,voiced.astype(float),left=0,right=0)>.5
    # These include fricatives: never call them confirmed breaths or noise.
    weak=(db<float(np.percentile(db,75))-15)&(db>-85)&middle
    unvoiced=~frame_voiced&middle&(db>threshold-8)
    tail=(ts>=max(start,end-.15))&(ts<=end)
    scope=weak|unvoiced|tail
    logspec=10*np.log10(power[high]);spike=np.max(logspec-ndimage.median_filter(logspec,size=(9,1),mode='nearest'),axis=0)
    # Relative high-frequency level referenced to this utterance's active energy.
    hf_abs=10*np.log10(np.sum(power[high],axis=0)+1e-18)-float(np.percentile(db[active],75) if active.any() else -90)
    htail=hvsel&(ht>=max(start,end-.15))&(ht<=end)
    energy_values=db[active]
    f0_tail=f0[voiced&(times>=max(start,end-.25))]
    f0_head=f0[voiced&(times<=start+.25)]
    tail_delta=float(12*np.log2(np.median(f0_tail)/np.median(f0_head))) if len(f0_tail)>2 and len(f0_head)>2 else None
    return {'seconds':len(y)/sr,'active_span_seconds':max(.01,end-start),'peak':float(abs(y).max()),'clipping_fraction':float(np.mean(abs(y)>=.999)),
        'f0_median_hz':float(np.median(f0[voiced])) if voiced.any() else None,'f0_std_hz':float(np.std(f0[voiced])) if voiced.any() else None,
        'f0_range_p90_p10_hz':float(np.percentile(f0[voiced],90)-np.percentile(f0[voiced],10)) if voiced.any() else None,'pitch_std_semitones':float(np.std(st)) if len(st)>2 else None,
        'pitch_range_p90_p10_semitones':float(np.percentile(st,90)-np.percentile(st,10)) if len(st)>2 else None,
        'voiced_fraction':float(np.mean(voiced)),'voiced_frames':int(voiced.sum()),'pause_fraction':pause,
        'characters_per_active_second':len(spoken(text))/max(.01,end-start),
        'energy_iqr_db':float(np.percentile(energy_values,75)-np.percentile(energy_values,25)) if len(energy_values) else None,
        'tail_pitch_delta_semitones':tail_delta,'voiced_hnr_db':summary(hv[hvsel]),'tail_voiced_hnr_db':summary(hv[htail]),
        'weak_or_unvoiced_hf_ratio_db':summary(hf_ratio[scope]),'weak_or_unvoiced_hf_relative_level_db':summary(hf_abs[scope]),
        'hf_narrow_spike_excess_db':summary(spike[scope]),'weak_frames':int(weak.sum()),'unvoiced_candidate_frames':int(unvoiced.sum()),
        '_f0_st':st.tolist(),'_energy_normalized':(energy_values-float(np.median(energy_values))).tolist() if len(energy_values) else [],
        'analysis_limit':'Weak/unvoiced regions include normal consonants and breaths. HNR and HF peaks are proxies, not electrical-artifact diagnosis.'}
class Critic:
    def __init__(self):
        options=onnxruntime.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.camp=onnxruntime.InferenceSession(str(BASE/'campplus.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.camp_sha=sha(BASE/'campplus.onnx');self.sense=None
        self.cache=T/'critic-cache';self.cache.mkdir(exist_ok=True)
    def embedding(self,path):
        y=load_audio(path,16000);feat=torchaudio.compliance.kaldi.fbank(torch.from_numpy(y)[None,:],num_mel_bins=80,dither=0,sample_frequency=16000);feat-=feat.mean(dim=0,keepdim=True)
        e=self.camp.run(None,{self.camp.get_inputs()[0].name:feat[None,:].numpy()})[0].flatten().astype(np.float64);return e/np.linalg.norm(e)
    def rich(self,path):
        if self.sense is None:
            sys.path.insert(0,str(ROOT/'runtime/sensevoice-curation/packages'))
            import sentencepiece
            for name in ['LoadFromFile','load_from_file','Load','load']:setattr(sentencepiece.SentencePieceProcessor,name,lambda self,path:self.LoadFromSerializedProto(Path(path).read_bytes()))
            from funasr import AutoModel
            with (T/'critic-sensevoice.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):self.sense=AutoModel(model=str(ROOT/'runtime/models/sensevoice-small'),device='cpu',ncpu=2,disable_update=True,disable_pbar=True,trust_remote_code=False,fp16=False)
            model=sentencepiece.SentencePieceProcessor();model.LoadFromSerializedProto((ROOT/'runtime/models/sensevoice-small/chn_jpn_yue_eng_ko_spectok.bpe.model').read_bytes())
            self.supported={model.id_to_piece(i) for i in range(model.get_piece_size())}
        with (T/'critic-sensevoice.log').open('a',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),torch.inference_mode():raw=self.sense.generate(input=load_audio(path,16000),cache={},language='zh',use_itn=False,batch_size_s=20,disable_pbar=True)[0]['text']
        tags=re.findall(r'<\|([^|]+)\|>',raw);events=[t for t in tags if t in {'Laughter','Breath','Cry','Cough','Sneeze','BGM','Sing','Speech_Noise'}]
        return {'raw':raw,'text':re.sub(r'<\|.*?\|>','',raw),'emotions':[t for t in tags if t in EMOTIONS],'events':events,
                'supports_laughter':'<|Laughter|>' in self.supported,'supports_breath':'<|Breath|>' in self.supported,
                'taunting_or_personal_style_class_supported':False,'naturalness_of_breath_or_laughter_verified':False}
    def file(self,path,text):
        digest=sha(path);key=hashlib.sha256((VERSION+digest+text+self.camp_sha).encode()).hexdigest();dest=self.cache/(key+'.json')
        if dest.exists():
            cached=read(dest)
            if 'f0_std_hz' not in cached['acoustic']:
                hz=100*2**(np.asarray(cached['acoustic']['_f0_st'])/12)
                cached['acoustic']['f0_std_hz']=float(np.std(hz)) if len(hz) else None
                cached['acoustic']['f0_range_p90_p10_hz']=float(np.percentile(hz,90)-np.percentile(hz,10)) if len(hz) else None
                write(dest,cached)
            return cached
        result={'path':str(path),'sha256':digest,'embedding':self.embedding(path).tolist(),'acoustic':acoustic(load_audio(path,24000),text=text),'rich':self.rich(path)}
        write(dest,result);return result
def prosody_score(g,r,same_text=False):
    terms=[];warnings=[]
    for key,weight,scale in [('pitch_std_semitones',1.,1.),('pitch_range_p90_p10_semitones',.5,1.),('energy_iqr_db',.4,1.),('characters_per_active_second',.6,1.)]:
        a,b=g.get(key),r.get(key)
        if a is not None and b is not None and a>0 and b>0:terms.append(weight*abs(math.log(a/b)))
    if g['f0_median_hz'] and r['f0_median_hz']:terms.append(abs(12*math.log2(g['f0_median_hz']/r['f0_median_hz']))/6)
    terms.append(abs(g['pause_fraction']-r['pause_fraction'])*2)
    ratio=(g['pitch_std_semitones'] or 0)/max(r['pitch_std_semitones'] or 0,.01)
    flat=bool(same_text and g['voiced_frames']>=40 and r['voiced_frames']>=40 and (r['pitch_std_semitones'] or 0)>1.5 and ratio<.5)
    if ratio<.5:warnings.append('音高变化偏小；不同台词只能提示，不能据此判定念稿或淘汰。')
    f0dist=dtw(g['_f0_st'],r['_f0_st']) if same_text else None;edist=dtw(g['_energy_normalized'],r['_energy_normalized']) if same_text else None
    if f0dist is not None:terms.append(f0dist/4)
    return 100*math.exp(-.3*sum(terms)),{'pitch_std_ratio':ratio,'same_spoken_text':same_text,'f0_dtw_semitones':f0dist,'energy_dtw_db':edist,'same_text_flat_pitch_veto':flat,'warnings':warnings}
def noise_score(g,r):
    penalty=0.;evidence={}
    for key,scale,tolerance in [('weak_or_unvoiced_hf_relative_level_db',2.,3.),('hf_narrow_spike_excess_db',1.5,4.)]:
        if g[key] and r[key]:
            excess=max(0.,g[key]['p90']-r[key]['p90']-tolerance);penalty+=min(30.,excess*scale);evidence[key+'_excess_db']=excess
    for key in ['voiced_hnr_db','tail_voiced_hnr_db']:
        if g[key] and r[key]:
            drop=max(0.,r[key]['median']-g[key]['median']-5.);penalty+=min(15.,drop);evidence[key+'_drop_db']=drop
    penalty+=min(50.,g['clipping_fraction']*20000)
    return max(0.,100-penalty),evidence
def emotion_score(g,r,target):
    match=bool(set(g['emotions'])&set(r['emotions'])-{'EMO_UNKNOWN','OTHER'});score=85. if match else 55.
    expected=[]
    if '[laughter]' in target or '<laughter>' in target:expected.append('Laughter')
    if '[breath]' in target:expected.append('Breath')
    missing=[e for e in expected if e not in g['events']]
    if expected:score+=15*(len(expected)-len(missing))/len(expected);score-=10*len(missing)
    else:score+=5
    return max(0,min(100,score)),{'reference_emotions':r['emotions'],'generated_emotions':g['emotions'],'expected_events':expected,'generated_events':g['events'],'missing_events':missing,'scope':'Coarse tag/event consistency only, not emotional authenticity; absence is not proof of no breath.'}
def text_error(expected,actual):
    from pypinyin import lazy_pinyin,Style
    a=spoken(expected);b=spoken(actual);pa=lazy_pinyin(a,style=Style.NORMAL);pb=lazy_pinyin(b,style=Style.NORMAL)
    return {'character_sequence_error_proxy':1-SequenceMatcher(None,a,b,autojunk=False).ratio(),'phonetic_sequence_error_proxy':1-SequenceMatcher(None,pa,pb,autojunk=False).ratio(),'recognized':actual,'repeated_words_collapsed':False}
def assess(critic,row,reference,anchors,anchor_limit):
    path=Path(row.get('raw') or row['playback']);g=critic.file(path,row['text']);r=critic.file(reference['path'],reference['text'])
    e=np.asarray(g['embedding']);centroid=np.mean(anchors,axis=0);centroid/=np.linalg.norm(centroid);cos=float(e@centroid);pair=float(e@np.asarray(r['embedding']))
    score1=100*(.7*cos+.3*pair)
    same=spoken(row['text'])==spoken(reference['text']);score2,pros=prosody_score(g['acoustic'],r['acoustic'],same)
    score3,emotion=emotion_score(g['rich'],r['rich'],row.get('tts_text',row['text']));score4,noise=noise_score(g['acoustic'],r['acoustic'])
    content=text_error(row['text'],g['rich']['text']);fail=[]
    if cos<anchor_limit:fail.append('声纹低于本原声池保守阈值；需要人工复核')
    if pros['same_text_flat_pitch_veto']:fail.append('同文条件下音高变化显著不足')
    if content['phonetic_sequence_error_proxy']>.25:fail.append('自动内容核对差异较大')
    if g['acoustic']['clipping_fraction']>.002:fail.append('削波比例过高')
    if g['acoustic']['voiced_frames']<15:fail.append('有效浊音太少，声学统计不可靠')
    expected=spoken(row['text']);recognized=spoken(g['rich']['text']);local=[]
    if expected.startswith('行行'):
        exact=recognized.startswith('行行');local.append({'target':'句首行行','asr_exact_match':exact,'recognized':recognized[:5],'perceptual_pronunciation_verified':False})
        if not exact:fail.append('句首“行行”局部转写不一致，需复核；整句分数不能覆盖。')
    if expected.endswith('嗯'):
        exact=recognized.endswith('嗯');local.append({'target':'句末嗯','asr_exact_match':exact,'recognized':recognized[-5:],'audibility_verified':False})
        if not exact:fail.append('句末“嗯”未被局部转写保留，需复核。')
    total=.4*score1+.3*score2+.15*score3+.15*score4
    return {'id':row['id'],'group':row.get('group',row['id']),'text':row['text'],'style':row['style'],'path':str(path),'playback':row['playback'],
        'scores':{'speaker':score1,'prosody':score2,'emotion_events':score3,'artifact_proxy':score4,'total':total},
        'speaker':{'cosine_centroid':cos,'cosine_same_emotion_reference':pair,'conservative_threshold':anchor_limit},'prosody':pros,'emotion':emotion,'artifact':noise,'content':content,
        'technical_gate_passed':not fail,'review_flags':fail,'local_boundary_checks':local,'assessment_version':ASSESSMENT_VERSION,'acoustic':g['acoustic'],'rich_transcription':g['rich'],'human_likeness_verified':False}
def rank_results(results):
    ranking=[];rng=np.random.default_rng(1986)
    for key,rows in results.items():
        vals=np.array([r['scores']['total'] for r in rows]);boot=np.median(rng.choice(vals,(1000,len(vals)),replace=True),axis=1)
        ranking.append({'variant':key,'cases':len(rows),'technical_failures':sum(not r['technical_gate_passed'] for r in rows),
            **{k:float(np.median([r['scores'][k] for r in rows])) for k in ['speaker','prosody','emotion_events','artifact_proxy','total']},
            'total_bootstrap_interval':[float(np.percentile(boot,5)),float(np.percentile(boot,95))]})
    ranking.sort(key=lambda r:(r['technical_failures']>0,-r['total']));return ranking
def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--references-only',action='store_true');p.add_argument('--manifest',type=Path);p.add_argument('--historical',action='store_true');p.add_argument('--out',type=Path,default=O/'critic');args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    bank=read(O/'prompts/manifest.json')['prompts'];critic=Critic()
    if args.self_test:
        y=load_audio(bank['daily']['path'],24000);a=critic.embedding(bank['daily']['path']);assert float(a@a)>0.99999
        original=acoustic(y,text=bank['daily']['text']);t=np.arange(24000*3)/24000;flat=.15*np.sin(2*np.pi*200*t);curve=.15*np.sin(2*np.pi*(200*t+25/(2*np.pi*2)*np.sin(2*np.pi*2*t)))
        fs=acoustic(flat,text='啊');cs=acoustic(curve,text='啊');assert fs['pitch_std_semitones']<cs['pitch_std_semitones']
        assert dtw([1,2,3,4],[1,2,3,4])==0 and dtw([1,2,3,4],[3,4,5,6])>0
        dirty=y.copy();tone=.012*np.sin(2*np.pi*7800*np.arange(len(y))/24000);dirty+=tone
        bad=acoustic(dirty,text=bank['daily']['text']);clean_score,_=noise_score(original,original);bad_score,_=noise_score(bad,original);assert bad_score<clean_score,(bad_score,clean_score)
        write(args.out/'self-test.json',{'passed':True,'identity_embedding_cosine':float(a@a),'constant_pitch_std_st':fs['pitch_std_semitones'],'modulated_pitch_std_st':cs['pitch_std_semitones'],'clean_self_artifact_score':clean_score,'added_7800Hz_tone_score':bad_score,'dtw_identity':True,'torch_cuda_context_initialized':torch.cuda.is_initialized(),'torch_cuda_allocated_bytes':torch.cuda.memory_allocated(),'original_audio_modified':False});print('Critic synthetic sanity checks passed.',flush=True);return
    anchors=[np.asarray(critic.file(r['path'],r['text'])['embedding']) for r in bank.values()]
    within=[]
    for i,a in enumerate(anchors):c=np.mean([v for j,v in enumerate(anchors) if j!=i],axis=0);c/=np.linalg.norm(c);within.append(float(a@c))
    threshold=max(-1.,float(np.percentile(within,5))-.12);write(args.out/'calibration.json',{'within_person_reference_loo_cosines':within,'conservative_threshold':threshold,'references':list(bank),'not_a_validated_personality_threshold':True})
    if args.references_only:print('Reference-pool CPU calibration cached.',flush=True);return
    if args.historical:
        prior=read(ROOT/'voice/comparison/cosyvoice2-20261026/finetune-20261026/generated/manifest.json')['samples'];history={}
        for key in ['lora-e1','lora-e2']:
            history[key]=[assess(critic,r,bank[r['style']],anchors,threshold) for r in prior if r['model_variant']==key]
        write(args.out/'historical-e1-e2.json',{'ranking':rank_results(history),'details':history,'human_preference':'original E1 preferred over E2','causal_explanation_proven':False,'scope':'Same three old test sentences; cannot compare their aggregate rank with the new six-case CV3 suite.'});return
    results={}
    manifests=[args.manifest] if args.manifest else [folder/'manifest.json' for folder in sorted((O/'generated').iterdir()) if (folder/'manifest.json').exists()]
    for manifest in manifests:
        folder=manifest.parent;rows=read(manifest)['samples']
        if not args.manifest and len(rows)!=6:continue
        results[folder.name]=[]
        for row in rows:
            assessment=assess(critic,row,bank[row['style']],anchors,threshold);results[folder.name].append(assessment)
            print(json.dumps({'critic':folder.name,'case':row['id'],'total':round(assessment['scores']['total'],2),'gate':assessment['technical_gate_passed']}),flush=True)
        write(args.out/'details.json',results)
    assert args.manifest or len(results)>=4,'Need base and all requested candidate generations.'
    ranking=rank_results(results);valid=[r for r in ranking if r['technical_failures']==0];recommended=valid[0]['variant'] if valid else None
    receipt={'version':VERSION,'assessment_version':ASSESSMENT_VERSION,'device':'CPU only','score_weights':{'speaker':.4,'prosody':.3,'emotion_events':.15,'artifact_proxy':.15},
        'ranking':ranking,'technical_recommendation':recommended,'automatic_default_changed':False,'human_likeness_verified':False,
        'limitations':['Heuristic unvalidated scores, not listening or MOS.','Different texts: no framewise F0-DTW or hard flat-pitch veto.','Natural breath and fricatives have low HNR; no unvoiced-HNR penalty.','SenseVoice coarse emotion and event tags do not measure taunting or authentic breathing.','HF and HNR cannot uniquely identify vocoder phase distortion.','Bootstrap interval describes these few test sentences, not general population confidence.']}
    receipt['waveform_sha256_by_variant']={key:[sha(r['path']) for r in rows] for key,rows in results.items()}
    receipt['identical_waveform_pairs']=[{'a':a,'b':b} for a in results for b in results if a<b and receipt['waveform_sha256_by_variant'][a]==receipt['waveform_sha256_by_variant'][b]]
    receipt['ranking_is_close_or_uncertain']=len(ranking)>1 and (ranking[0]['total']-ranking[1]['total']<2 or ranking[0]['total_bootstrap_interval'][0]<=ranking[1]['total_bootstrap_interval'][1])
    receipt['torch_cuda_context_initialized']=torch.cuda.is_initialized();receipt['torch_cuda_allocated_bytes']=torch.cuda.memory_allocated()
    write(args.out/'ranking.json',receipt)
    lines=['# CV3 四维自动筛查（不是听感验收）','','|候选|声纹|韵律统计|情绪/事件|伪影风险指标|综合|技术复核项|','|---|---:|---:|---:|---:|---:|---:|']
    for r in ranking:lines.append('|'+r['variant']+'|'+ '|'.join(f'{r[k]:.2f}' for k in ['speaker','prosody','emotion_events','artifact_proxy','total'])+'|'+str(r['technical_failures'])+'|')
    lines+=['','自动推荐候选：'+str(recommended),'分数仅用于本批技术排序，不能证明最像本人，也不能解释某一轮主观变差的因果。','不同台词不做音高轨迹逐帧对齐；HNR只用于有基音区，保留真实气口。']
    (args.out/'ranking.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps({'ranking':ranking,'technical_recommendation':recommended,'ranking_is_close_or_uncertain':receipt['ranking_is_close_or_uncertain'],'cuda_allocated_bytes':receipt['torch_cuda_allocated_bytes']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
