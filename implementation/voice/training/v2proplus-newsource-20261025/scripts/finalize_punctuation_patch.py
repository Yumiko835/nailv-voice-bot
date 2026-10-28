
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
import shutil,copy
import numpy as np,soundfile as sf
from punctuation_audio_patch import cut_punc,tail_token_plan

D=Path(__file__).parent;O=T/'punctuation-tail-patch-20261025'
models=read(T/'selected-models.json');assert models==read(O/'selected-models-before.json')
for key in ['gpt','sovits']:assert sha(models[key]['path'])==models[key]['sha256']
original=read(O/'generated/manifest.json')['samples']
retry=read(O/'retry-generated/manifest.json')['samples']
checks=read(O/'verification/content-check.json')
retry_checks=read(O/'retry-verification/content-check.json')
scores={r['id']:r for r in checks+retry_checks}
choices=[];selected=[];rows=[];metrics=[]
for base in original:
    case=base['id'];candidates=[base]+[r for r in retry if r['case_id']==case]
    def score(r):return max(scores[r['id']+'-split']['error'],scores[r['id']+'-full']['error'])
    winner=min(candidates,key=score);selected.append(winner)
    choices.append({'case':case,'selected_source_id':winner['id'],'selected_max_ASR_error':score(winner),
        'candidates':[{'id':r['id'],'max_ASR_error':score(r)} for r in candidates],
        'ASR_is_content_screen_not_human_sound_approval':True})
    for suffix,label,effects in [('split','A · 仅分句与末尾Token处理',False),('full','B · 三道补丁（尾音收束＋气音柔化）',True)]:
        r=copy.deepcopy(winner)
        if not effects:r.update(winner['control'])
        r.update(id=case+'-'+suffix,case=case,case_title=base['audition_label'],label=label,acoustic_effects_applied=effects)
        check=scores[winner['id']+'-'+suffix]
        if check['error']>0:r['content_note']='自动转写对极短片段有差异，请重点试听是否读清；未按识别分数判断音质。'
        rows.append(r)
    assert len(winner['segments'])==len(cut_punc(winner['text']))
    assert winner['settings']['top_k']==15 and winner['settings']['temperature']==.8
    assert winner['settings']['repetition_penalty']==1.35 and winner['settings']['fragment_interval']==.25
    assert winner['settings']['text_split_method']=='cut_punc'
    raw,sr=sf.read(winner['control']['native_float'],dtype='float32');full,_=sf.read(winner['native_float'],dtype='float32')
    assert sr==32000 and len(raw)==len(full)
    for left,right in winner['inserted_silence_regions_samples']:
        assert right-left==8000 and np.all(raw[left:right]==0) and np.all(full[left:right]==0)
    for s in winner['segments']:
        assert s['postprocessing']['tail']['fade_ms']==100
        assert s['postprocessing']['tail']['lowpass_cutoff_hz']==5000
        assert s['postprocessing']['deesser']['maximum_band_reduction_db']==5
        assert not any(ch in s['spoken'] for ch in '，、。！？；：')
        for e in s['attempts'][-1]['decode_events']:
            plan=tail_token_plan(e['semantic_ids_before']);assert plan==e['token_tail_cap']
            assert e['semantic_ids_before'][:plan['retained_tokens']]==e['semantic_ids_after']
            assert e['noise_scale']==.5 and e['acoustic_model_dtype']=='torch.float32'
    metrics.append({'case':case,'clauses':len(winner['segments']),'seconds':winner['seconds'],
        'exact_inserted_gaps_samples':8000,'raw_vs_processed_rms_difference_db':float(10*np.log10(max(np.mean((full-raw)**2),1e-18)/max(np.mean(raw**2),1e-18))),
        'ASR_error_A':scores[winner['id']+'-split']['error'],'ASR_error_B':scores[winner['id']+'-full']['error'],
        'suffix_tokens_removed':sum(e['token_tail_cap']['removed_tokens'] for s in winner['segments'] for e in s['attempts'][-1]['decode_events'])})
assert len(rows)==18
for r in rows:
    for kind in ['raw','playback']:
        assert sha(r[kind])==r[kind+'_sha256']
        info=sf.info(r[kind]);y,sr=sf.read(r[kind],dtype='float32')
        assert sr==32000 and info.subtype=='PCM_24' and info.channels==1
        assert len(y) and np.isfinite(y).all() and np.abs(y).max()<1
for i in range(0,len(rows),2):assert rows[i]['playback_gain_db']==rows[i+1]['playback_gain_db']
verify_protected()
write(O/'listening-initial.json',read(O/'listening.json'))
write(O/'listening.json',{'samples':rows,'models':models,'human_quality_verified':False,
    'comparison':'Same independently generated segments and playback gain; B adds tail fade/dynamic lowpass and de-essing.',
    'selection_is_content_screening_not_sound_acceptance':True})
write(O/'selected-content-candidates.json',choices)
write(O/'technical-verification.json',{'fixed_models':models,'protected_hashes_unchanged':True,
    'cases':9,'clauses':sum(m['clauses'] for m in metrics),'comparison_files':18,'metrics':metrics,
    'human_quality_verified':False,'no_retraining':True,'not_a_proof_punctuation_is_the_only_cause':True})
backup=O/'deployment-backup';backup.mkdir(exist_ok=True)
for name in ['nailv_proplus_voice.py','voice-proplus.html']:
    destination=ROOT/('tools/'+name if name.endswith('.py') else 'outputs/奶绿V2ProPlus双阶段语音.html')
    assert not (backup/name).exists()
    shutil.copy2(destination,backup/name)
    shutil.copy2(D/name,destination)
for name in ['synthesize_punctuation.py','punctuation_audio_patch.py','prepare_punctuation_trials.py','prepare_punctuation_page.py','finalize_punctuation_patch.py','nailv_proplus_voice.py','voice-proplus.html']:
    source=D/name
    if source.suffix=='.py':compile(source.read_text(encoding='utf-8-sig'),str(source),'exec')
    shutil.copy2(source,T/'scripts'/name)
deployment=read(T/'deployment.json');write(backup/'deployment.json',deployment)
deployment['inference_worker']=str(T/'scripts/synthesize_punctuation.py')
deployment['inference_patches']={'version':'punctuation-tail-v1','user_requested':True,'strict_outer_punctuation_calls':True,
    'short_clauses_not_merged':True,'inserted_gap_seconds':.25,'top_k':15,'default_temperature':.8,'repetition_penalty':1.35,
    'tail_identical_ID_trim_trigger':12,'tail_identical_ID_keep':8,'internal_loop_retry_trigger':16,
    'cosine_tail_fade_ms':100,'dynamic_tail_lowpass_hz':5000,'deesser_band_hz':[4500,9000],'deesser_max_db':5,
    'human_quality_verified':False,'listening_manifest':str(O/'listening.json')}
deployment['tail_treatment']={'default':True,'pipeline':'punctuation-tail-v1','previous_gentle_treatment_not_adopted':True,'human_quality_verified':False}
deployment['known_quality_issue']='New requested inference patches deployed for audition. Forced short clauses can alter prosody; some very short segments have ASR disagreement. No claim of eliminated artifacts.'
write(T/'deployment.json',deployment)
notes='''# 标点、尾音、气音三道推理补丁

固定原SoVITS第14轮与本次ProPlus GPT第6轮，权重、训练集和参考原件均未改动，不重训。

1. 项目外层按逗号、顿号、句号、问号、叹号、分号、冒号切分，每个短句独立调用GPT，避免原前端把短片段重新合并。每段结尾使用句末标记，两个短句之间插入8000个零样本（32kHz下0.25秒），不在“妈妈妈妈”内部加空隙。top_k15、温度0.8、重复惩罚1.35。
2. 送入SoVITS前检查目标Token的末尾，连续相同ID达12帧时保留8帧，截断多余尾部。保留正常交替/叠词编码；内部异常循环仍会换种子重试。不能保证只凭同码重复就完全识别字音，极短句须实际试听。
3. 先用高过零率、较低80-800Hz能量、较高4.5-9kHz能量检测气音/齿音候选，在该频段动态衰减最多5dB，8ms启动、50ms释放。随后对估计发音结束点施加100ms余弦淡出，并在同一区域渐变混入5kHz零相位低通结果。能量检测有40ms保护余量，不裁掉波形样本；两种处理均可能影响很轻的尾字或清辅音，自动检测不是字级对齐。

## 试听

9句、18个同文对照。A为分句和Token处理；B在同份合成上添加上述声学收尾。播放增益逐对一致，原生32kHz PCM24，未重采样、移调或加速。初版和换种子候选全部保留。辅助转写只用于筛查内容，不用于证明电流消失或自然度通过；有差异的条目已在页面标注。

官方代码里的按标点方法名为cut5，且TextPreprocessor会合并短片段，所以本项目在外层强制独立调用，同时仅在进程内注册cut_punc，不修改共享GPT-SoVITS源码。

代码参考：https://github.com/RVC-Boss/GPT-SoVITS/blob/main/GPT_SoVITS/TTS_infer_pack/text_segmentation_method.py
API参数参考：https://github.com/RVC-Boss/GPT-SoVITS/blob/main/api_v2.py

## 回退

deployment-backup保存此前后台和页面，原synthesize.py保留不动。把后台worker切回synthesize.py即可恢复上一推理方式。本轮不接入QQ、不调用云端音频服务。
'''
(O/'三道补丁说明.md').write_text(notes,encoding='utf-8')
status('proplus-ready',gpt_epoch=6,default_acoustic_epoch=14,completed_acoustic_epoch=20,
    inference_patch='punctuation-tail-v1',punctuation_patch_cases=9,human_electrical_noise_resolved=False)
print(json.dumps({'published_pairs':9,'clauses':sum(m['clauses'] for m in metrics),'choices':choices,'model_hashes_unchanged':True},ensure_ascii=False))
