
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
plan=read(T/'training-plan.json');receipt=read(T/'stage2-training-receipt.json');plan['SoVITS']['batch_size']=receipt['batch_size'];plan['SoVITS']['actual_epochs_completed']=receipt['epochs_completed'];write(T/'training-plan.json',plan)
models=read(T/'selected-models.json');bank=read(T/'prompts/manifest.json');s1=read(T/'training-receipt.json');s2=read(T/'stage2-training-receipt.json')
lines=['# 奶绿 V2 ProPlus 双阶段语音','','打开本机试听页：http://127.0.0.1:49850/voice-proplus','','## 怎么用','','在“要说的话”里输入中文，选一种语气，点击“生成语音”。选“自动匹配”时按文字语境与标点选择现有参考；也可直接写 `[调侃] 你又来了` 强制点播。','','沿用293段、约27.5分钟精炼集，没有重新筛选或识别原素材。GPT和SoVITS均完成10轮，隔2轮保留一个权重。默认GPT第'+str(models['gpt']['epoch'])+'轮（验证集损失暂选）、SoVITS第10轮（最后导出，听感待确认）。原版底模与V5文件未覆盖。','','输出原生32kHz、24位PCM无损WAV；无MP3编码、无输出重采样、无额外强降噪。训练不保证自动消除背景歌声或偶发噪音，最终以实际试听为准。','','## 参考条','','共10种情绪、11段参考。日常使用你最后确认的“外币／行李箱”段，温柔A、惊讶B；不采用慢速念稿B。口癖较多的备用条归开心兴奋，备用2归解释／向粉丝确认。','','| 情绪 | 实际参考文件 | 原话 |','|---|---|---|']
for key,p in bank['prompts'].items():lines.append('| '+p['label']+' | '+p['path']+' | '+p['text'].replace('|','／')+' |')
for key,p in bank['alternates'].items():lines.append('| 开心兴奋 · 口癖备用 | '+p['path']+' | '+p['text'].replace('|','／')+' |')
lines+=['','## 保存的模型','','| 阶段 | 轮数 | 文件 |','|---|---|---|']
for label,receipt in [('GPT',s1),('SoVITS',s2)]:
 for r in receipt['exports']:lines.append('| '+label+' | '+str(r['epoch'])+' | '+r['path']+' |')
lines+=['','每个模型与试听文件的来源、哈希和设置见 selected-models.json、generated/test/manifest.json。technical-verification.json 的转写检查只排查疑似错漏字，不能证明无电音或像本人。','','本次只接入本机多情绪试听与生成系统，未接入QQ。原有本机页面的启动方式和端口保持49850。']
(T/'使用说明.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
