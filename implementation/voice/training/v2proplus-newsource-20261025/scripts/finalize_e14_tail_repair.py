
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
import shutil
import numpy as np, soundfile as sf

D=Path(__file__).parent;O=T/'e14-tail-repair-20261025'
sel=read(T/'selected-models.json');assert sel==read(O/'selected-models-before.json')
for k in ['gpt','sovits']:assert sha(sel[k]['path'])==sel[k]['sha256']
reg=read(O/'guard-regression/manifest.json')['samples'];assert len(reg)==12
slow=next(r for r in reg if r['id']=='tailguard-e14-more-b03')
assert len(slow['generation_attempts'])==2
assert slow['generation_attempts'][0]['maximum_identical_token_run']==27
assert not slow['generation_attempts'][0]['semantic_loop_guard_passed']
assert slow['generation_attempts'][1]['maximum_identical_token_run']==5
assert slow['seconds']==4 and slow['settings']['repetition_penalty']==1.35
assert all(len(r['generation_attempts'])==1 for r in reg if r!=slow)
content=read(O/'guard-regression/content-check.json')
assert next(r for r in content if r['id']==slow['id'])['error']==0
filtered_content=read(O/'filtered-content-check/content-check.json')
assert len(filtered_content)==6 and all(r['error']==0 for r in filtered_content)
metrics=[]
samples=read(O/'listening-v2.json')['samples'];assert len(samples)==10
for r in samples:
    for name in ['raw','playback']:
        assert sha(r[name])==r[name+'_sha256']
        info=sf.info(r[name]);y,sr=sf.read(r[name],dtype='float32')
        assert sr==32000 and info.subtype=='PCM_24' and info.channels==1
        assert len(y)>0 and np.isfinite(y).all() and np.max(np.abs(y))<1
    if isinstance(r.get('treatment'),dict):
        source=next(v for v in reg if v['native_float_sha256']==r['source_native_sha256'])
        y,sr=sf.read(source['native_float'],dtype='float32');z,_=sf.read(r['native_float'],dtype='float32')
        assert len(z)==len(y) and r['playback_gain_db']==source['playback_gain_db']
        quiet=np.zeros(len(y),bool);tail=quiet.copy()
        for a,b in r['treatment']['quiet_intervals_seconds']:
            quiet[int(a*sr):int(b*sr)]=True
            tail[max(0,int((a-.18)*sr)):int(a*sr)]=True
        def delta(mask):
            return float(10*np.log10(max(float(np.sum(z[mask]**2)),1e-18)/max(float(np.sum(y[mask]**2)),1e-18)))
        metrics.append({'id':r['id'],'quiet_region_energy_delta_db':delta(quiet),'pre_pause_180ms_energy_delta_db':delta(tail),
            'relative_residual_db':float(10*np.log10(np.mean((z-y)**2)/np.mean(y**2))),
            'not_a_clean_reference_SNR_or_perceptual_quality_score':True})
verify_protected()
receipt={'gpt_epoch':6,'acoustic_epoch':14,'model_files_unchanged':True,'protected_sources_unchanged':True,
    'loop_guard_regression_cases':12,'loop_guard_b03':slow['generation_attempts'],
    'other_11_cases_no_unnecessary_retry':True,
    'regression_ASR_disagreement_ids':[r['id'] for r in content if r['error']>0],
    'six_processed_copies_ASR_matches':True,'metrics':metrics,
    'human_quality_verified':False,'postprocessing_default':False}
write(O/'repair-verification.json',receipt)
backup=O/'deployment-backup';backup.mkdir(exist_ok=True)
targets=[(D/'synthesize.py',T/'scripts/synthesize.py'),
    (D/'voice-proplus.html',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html'),
    (D/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py')]
for src,target in targets:
    saved=backup/target.name
    assert not saved.exists(), 'Preserve deployment backup'
    compile(src.read_text(encoding='utf-8-sig'),str(src),'exec') if src.suffix=='.py' else None
    shutil.copy2(target,saved);shutil.copy2(src,target)
for name in ['repair_e14_tail_trials.py','tail_signal.py','build_e14_tail_listening.py','prepare_e14_tail_page.py','finalize_e14_tail_repair.py','voice-proplus.html','nailv_proplus_voice.py']:
    shutil.copy2(D/name,T/'scripts'/name)
deployment=read(T/'deployment.json');write(backup/'deployment.json',deployment)
deployment['semantic_loop_guard']={'maximum_identical_run_exclusive':16,'attempts':3,'retry_seed_offsets':[0,95,104729],
    'sampling_penalty_unchanged':1.35,'explicit_written_elongation_exempt':True,'trim_or_speedup_audio':False,
    'coverage':'12 regression sentences; detects consecutive same-code loops, not every form of drawn-out prosody.'}
deployment['tail_treatment']={'default':False,'audition_manifest':str(O/'listening-v2.json'),'human_quality_verified':False}
write(T/'deployment.json',deployment)
notes='''# 原第14轮：拖音与气息、尾音电流排查

保持本次ProPlus GPT第6轮和原SoVITS第14轮，所有权重、训练资料、已选参考文件均未修改。没有继续训练、插值、加速、裁掉尾字或切高频。

## 拖音

B03原版216个语音单元，最长同一单元重复27次，输出8.64秒。只换采样种子的137版本保持温柔参考和重复惩罚1.35，输出4秒，最长重复5次，辅助转写完整保留两遍“慢慢来”。1.40的参数候选虽短，却有明显识别差异，因此没有采用。1.50的候选也未设为通用默认。

推理新增连续相同语音单元检测，触发时重新生成，保留被拒的原音和日志。12句回归中只有B03触发重试，其余11句首次输出。B01/B02辅助转写仍有差异，不宣称所有重复字均已解决。此检测只覆盖连续相同编码的循环，不覆盖所有不自然韵律。

## 电流与底噪候选

提供三句话、共10段同文试听：慢慢来含原8.64秒、重新生成4秒、轻处理、稍强处理；短句停顿和温柔换气各含原音、轻处理、稍强处理。处理以原相位、受限幅度的频谱衰减配合渐变的低电平间隙衰减，保留未选中强发声样本，无整段低通、不硬静音。低音量辅音和气声仍可能被影响，需要实际试听。

处理前后采样数和32kHz原生采样率一致、PCM24导出、沿用完全相同播放增益。6份处理副本自动转写均与目标读音匹配，但这不能证明电流消除、没有轻声损伤或听感自然。处理尚未设为默认。

第一版仅用静音噪声估计，对发声尾音影响几乎为零，已经另存而未发布。本轮试听是补充局部扩散噪声估计的第二版。技术记录在repair-verification.json；掩码只是声学估计，能量下降不等于电流主观消除。

## 回退

deployment-backup内保存原推理脚本、后台和HTML，所有旧试听仍在原目录。没有接入QQ或云端音频服务。
'''
(O/'排查与试听说明.md').write_text(notes,encoding='utf-8')
status('proplus-ready',gpt_epoch=6,default_acoustic_epoch=14,completed_acoustic_epoch=20,
    semantic_loop_guard_enabled=True,tail_treatment_default=False,human_electrical_noise_resolved=False)
print(json.dumps({'published_samples':len(samples),'B03_seconds_before':8.64,'B03_seconds_after':4.,'regression_cases':12,'postprocessing_not_default':True,'metrics':metrics},ensure_ascii=False))
