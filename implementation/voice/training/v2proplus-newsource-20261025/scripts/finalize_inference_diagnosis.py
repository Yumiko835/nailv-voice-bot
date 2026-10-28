
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
import shutil,ast
import numpy as np,soundfile as sf
O=T/'inference-diagnosis-20261025';here=Path(__file__).parent
checks=read(O/'content-check.json');repairchecks=read(O/'content-check.json')
# The checker writes alongside its input manifest; the second run intentionally
# contains the18 latest cases. The initial10-case receipt was already preserved
# by its input file and raw sample hashes; do not invent listening approval.
assert len(checks)==18
old=read(O/'before/listening.json');new=read(O/'repaired-emotions/manifest.json');byid={r['id']:r for r in new['samples']};assert len(byid)==8
listing=old.copy();listing.update(version='proplus-listening-v3-rp135-diagnosed',human_quality_verified=False,human_feedback='Strong electronic sound/slow drawn-out repeats reported on v2. RP-specific repair is not an approval of remaining timbre quality.',repair='All11 published tests now use repetition_penalty1.35; old8 low-penalty samples archived under before/listening.json.');listing['samples']=[byid.get(r['id'],r) for r in old['samples']];assert all(r['settings']['repetition_penalty']==1.35 for r in listing['samples']);write(T/'listening.json',listing)
# Matched listening gain, attenuation only, separately for each common sentence.
comparison=read(O/'gpt-epochs.json')
for suffix in ['mama','calm']:
 group=[r for r in comparison['samples'] if r['id'].endswith('-'+suffix)];active=[]
 for r in group:
  y,sr=sf.read(r['native_float'],dtype='float32');assert sr==32000;frames=np.pad(y,(0,(-len(y))%640)).reshape(-1,640);rms=np.sqrt(np.mean(frames*frames,axis=1));mask=rms>max(.001,rms.max()*.1);active.append(float(np.sqrt(np.mean(rms[mask]**2))))
 target=min(active)*.9
 for r,rms in zip(group,active):
  y,sr=sf.read(r['native_float'],dtype='float32');gain=min(1.,target/rms);path=Path(r['native_float']).parent/'listen-equalized.wav';sf.write(path,np.r_[np.zeros(5120,dtype='float32'),y*gain,np.zeros(10240,dtype='float32')],sr,subtype='PCM_24');r.update(playback=str(path),playback_sha256=sha(path),comparison_gain_db=float(20*np.log10(gain)),comparison_active_rms_target=target,positive_gain=False)
comparison.update(equal_loudness='Attenuation-only active RMS match within each sentence; full original samples retained.',all_five_GPTs_fresh_ProPlus_exports=True,SoVITS_epoch_fixed=10,default_not_automatically_changed=True,human_quality_verified=False);write(O/'gpt-epochs.json',comparison)
selected=read(T/'selected-models.json');selected['gpt_selection_basis']='Provisional: lowest validation loss among the newly trained even-epoch exports, not a listening-approved best. Old V5 e6 is a different file and was not reused.';selected['sovits_selection_basis']='Controlled human comparison: e10 preferred over e2 over official. This ranking does not establish that electrical artifacts are gone.';selected['human_naturalness_verified']=False;write(T/'selected-models.json',selected)
deployment=read(T/'deployment.json');deployment.update(models=selected,human_quality_verified=False,known_quality_issue='User reported electric timbre; repeat-specific parameter fixed, final timbre unresolved pending listening.',inference_repair='rp135-no-lexical-exception',generated_test_samples=11);write(T/'deployment.json',deployment)
dataset=read(T/'dataset/manifest.json');counts={}
for row in dataset['train']:
 assert sha(row['path'])==row['sha256'];key=row.get('separator','unknown');counts[key]=counts.get(key,0)+1
write(O/'training-audio-provenance.json',{'train_rows':len(dataset['train']),'separators_in_frozen_manifest':counts,'all_source_wave_sha256_unchanged':True,'limitation':'Frozen training targets were MelBand vocal stems, not the later context-Karaoke reference derivatives. Possible background-singer or separation artifacts require actual listening; a manifest or ASR match cannot establish absence.'})
for name in ['nailv_proplus_voice.py','synthesize.py','nailv_audio_export.py','diagnose_inference.py','diagnose_gpt.py','compare_gpt_epochs.py','analyze_diagnosis.py','audit_features_diagnosis.py','check_reference_alignment.py','check_diagnosis_text.py','check_repair_and_epochs.py','prepare_rp_repair.py','finalize_inference_diagnosis.py']:
 ast.parse((here/name).read_text(encoding='utf-8'));shutil.copy2(here/name,T/'scripts'/name)
shutil.copy2(here/'nailv_proplus_voice.py',ROOT/'tools/nailv_proplus_voice.py');shutil.copy2(here/'voice-proplus.html',ROOT/'outputs/奶绿V2ProPlus双阶段语音.html');shutil.copy2(here/'voice-proplus.html',T/'scripts/voice-proplus.html')
verify_protected()
for key in ['gpt','sovits']:assert sha(selected[key]['path'])==selected[key]['sha256']
report='''# V2 ProPlus 推理排查记录（2026-10-25）

## 已复现并修正

- 重复词曾被特殊设置为 repetition_penalty=1.10。这个参数作用于语音编码，而不是文字重复。固定新GPT第6轮、SoVITS第10轮、同参考和种子42，改为1.35后，“妈妈妈妈，这么喜欢叫妈妈吗”从129个语音编码/5.16秒降至70个/2.80秒；最长同码连续段从16降至3。没有改字、插停顿或加快播放。
- 本地SenseVoice对修正版保留全部重复字的转写与输入一致。识别辅助不等于自然度或无电音通过。
- 试听页8条旧样本仍沿用1.10；已重生成并替换，旧文件与清单留在before和generated/test。新的11条试听统一1.35。

## 已确认的选择依据

- 此次ProPlus GPT是从官方s1v3重新训练的独立模型，保留2/4/6/8/10轮。默认6来自新检查点的自动验证初选，和以前V5的第6轮不是同一文件，也尚未经人评确定最好。
- 固定语音编码、文字、参考、解码种子777，仅更换声学模型的人评为：SoVITS第10轮优于第2轮，优于官方底模。因此保留声学第10轮；不据此推断15～20轮一定更好。
- 新GPT五个轮次均已做同文对照，音色固定第10轮、参数1.35、速度1、同参考和解码种子。两句共10条，按句统一试听响度，只降低音量。8轮的“妈妈”达6.60秒而6轮2.80秒、10轮2.72秒，这说明不同轮次对单句的节奏并不单调改善；时长也不单独用作听感裁判。

## 电音部分的证据与局限

- 当前ProPlus使用其原生VITS解码，未调用V5 CFM或V5高频声码器。不能把这次问题继续直接归因于V5流匹配。
- 已保存原始浮点波形，原生32000Hz PCM24 WAV导出；未有损压缩、输出重采样、剪字、输出降噪或正增益。当前受测波形无NaN/Inf/削顶。
- 固定输入的FP16/FP32对照没有数值爆炸，波形相关约0.9984～0.9996；这不证明两者听感绝对一致，也不能据数值宣布电音解决。
- 10条现用参考音频经本地ASR辅助检查，保留重复和语气词的发音对比未见明显整句错配。没有自动裁短或擅自换掉已确认的参考。ASR不能证明逐字边界完美或音频绝对纯净。
- 冻结训练集仍是较早的MelBand人声分离版本，后来去背景歌声的Karaoke处理用于参考条。这是训练目标可能含背景歌声/分离伪影的线索，尚非已由人耳证实的本次电音根因。GPT和声学训练均可能受音频目标影响，不能保证训练会自动滤掉底噪。
- “爸爸爸爸”的额外回归识别有一字差异；未宣称所有叠词、所有随机种子或所有词语组合已经穷尽通过。

## 对截图建议的判断

参考音频与文字对齐值得检查，已经辅助检查；“官方底模最差，所以继续训练必然消电音”缺乏充分证据。当前默认音色本来就是第10轮，截图提到按Loss选第2轮与本项目现状不符。Loss初选的是新GPT第6轮，两个阶段必须分开。没有追加到15～20轮，没有重筛或改写训练数据，没有覆盖任何权重。

## 文件与回退

- before/：本轮前的代码、监听清单和配置快照。
- generation.json、decoder-matrix.json、gpt-matrix.json、gpt-epochs.json：受控生成记录。
- content-check.json、reference-alignment/content-check.json：本地识别辅助记录。
- numeric-checks.json、precision-comparison.json、feature-scale-audit.json：数值与特征核查。
- 页面 /voice-proplus#gpt-compare：新GPT轮次试听；/voice-proplus#listen：更新参数后的多情绪试听。

当前电音听感仍待比较，未标记修好；未接入QQ、未调用云端音频、未发送外部消息。原模型和原训练素材保持不变。
'''
(O/'排查说明.md').write_text(report,encoding='utf-8');write(O/'repair-receipt.json',{'known_repeat_parameter_defect_fixed':True,'stale_low_RP_samples_replaced':8,'GPT_epochs_compared':[2,4,6,8,10],'SoVITS_default_epoch':10,'GPT_provisional_epoch':6,'models_and_dataset_unchanged':True,'human_electrical_artifact_resolved':False,'new_training_started':False,'cloud_audio_uploaded':False,'QQ_connected':False});status('proplus-inference-repaired',repetition_penalty=1.35,gpt_epoch=6,sovits_epoch=10,human_electrical_artifact_resolved=False)
