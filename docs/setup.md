# 安装与本地资产接入

这是源码发布，不是附带人物录音和训练权重的整合包。先跑离线演示，后准备模型，最后接QQ；不要直接把别人的已登录bot目录当运行环境。

## 1. 离线检查

Python3.12+，在仓库根执行：

```powershell
python -B scripts/offline_demo.py
python -B -m unittest discover -s tests -v
python -B scripts/check_release.py
Copy-Item .env.example .env
python -B scripts/bootstrap.py
```

bootstrap只向本仓库`.local/project`写入适配代码及虚构示例，拒绝覆盖没有标记的既有项目；不下载、不调用API、不启动QQ。`.env`由release_config读取，已有进程环境变量优先。空的NAILV_DATA_ROOT使用`.local/project`。

真实资产全部放在这个本地工作区。若要使用独立数据盘，先手动建立全新的目录并按implementation结构复制代码，再在.env设置NAILV_DATA_ROOT及NAILV_SOURCE_ROOT；不要指向当前已验收机器人的目录做实验。

## 2. 独立运行环境

原设备基线：Windows x64、Python3.12.15、Torch2.7.1+cu128、匹配torchaudio。驱动/CUDA兼容性由目标设备决定。`requirements/*-observed.txt`记录原环境，不是跨平台通用锁文件，不能混装两个文件。

- AstrBot：在`$DATA/runtime/astrbot/.venv`创建独立环境，安装AstrBot4.29.3官方依赖。
- 语音：在`$DATA/runtime/cosyvoice2/.venv`建立语音环境，再安装CV3-capable CosyVoice源码及ONNX、HyperPyYAML、soundfile、Praat等。历史cosyvoice2目录名是共用运行时命名，不表示默认使用CV2模型。
- GPT-SoVITS：单独获取官方源码与依赖，设置`NAILV_GPT_SOVITS_ROOT`。原项目用过共享环境，公开版不要求也不访问其他bot目录。
- FFmpeg：自行从可信发行获取，NAILV_FFMPEG_ROOT设置为ffmpeg可执行文件的绝对路径。必要时将vendor-patches的portable_runtime.py放入你自己的GPT-SoVITS/tools，保留MIT说明。

不要复制原机器的`.pth`、虚拟环境或site-packages。先核对实际导入路径，再做CPU导入，之后才加载GPU模型。

## 3. 人物文字数据

需要identity、facts、corpus、behaviors、实际style bank、本地SQLite索引，以及代码启用的补充/偏好/社区/关系数据。完整数据没有随公开仓库分发。

用[复刻流程](reproduce.md)从自己的授权材料生成这些文件。`examples/fictional-style-bank.json`仅供召回演示，不能当作完整人物库。`docs/expression-template.json`说明字段，`docs/prompt-components.json`保留实际提示结构。

正式文字主线：`tools/nailv_text_core.py`的choose_routing/messages_for + AstrBot原生Provider。core.chat和nailv_text_server属于早期试聊包装，其有界重写/历史费用逻辑不等于QQ正式链路。部分制作脚本读取当时的审批/进度文件，恢复新数据项目时须按流程生成，不能伪造已批准状态跳过。

CHAT_API_KEY在环境变量设置；或设置CHAT_API_KEY_FILE指向仓库外秘密文件。embedding使用自己的ZHIPU_API_KEY_FILE。修改聊天模型时一并检查Provider契约、JSON、费用和工具调用兼容性。本次公开整理没有调用这些API。

## 4. 语音资产

模型来源和固定revision见`models/upstream-models.json`。按各模型说明获取文件，不自动下载未知模型。

CV3模型目录：`runtime/cosyvoice3/models/Fun-CosyVoice3-0.5B-2512`。默认保留YAML、Flow、HiFT、S3 Tokenizer、CAMPPlus。默认D不需要llm.pt；如果改做CV3文字生成/训练，则需另外恢复相应模型与依赖。

GPT-SoVITS需自己训练/供应GPT和SoVITS权重，以及Chinese HuBERT、BERT、G2PW、SV等前处理资产。`config/selected-models.example.json`填实际权重绝对路径和SHA，放入`voice/training/v2proplus-newsource-20261025/selected-models.json`。不要沿用原人物轮次/哈希当作自己权重的证明。

准备六类真实参考，音频/逐字文本/SHA绑定。分别填写GPT与CV3参考清单，路径见`config/assets.example.json`。`micro_gate_plan`的实际字段以nailv_audio_export.prepare_reference为准；先用未处理参考，未验证时不要自造裁切计划。

执行`python scripts/doctor.py --require-ready`核对关键文件。doctor只查存在性，不加载模型；通过后仍须在自己的环境做初始化与最短句推理。

## 5. 启动顺序

完成资产后，在已staging的本地工作区运行对应解释器：

1. 语音环境执行`runtime/cosyvoice3/scripts/rhythm-bridge/live_bridge_server.py`，默认loopback49856。
2. 对同文字/参考固定种子，保存GPT源WAV及D输出，先人工确认。端口开启不代表音质验收。
3. 依[QQ文档](qq.md)建立新的AstrBot/NapCat实例。先确认文字，再确认SILK语音播放。

公开适配保留原模块结构和算法，但路径/账号配置有变化。它已做离线测试；没有宣称在另一机器做过GPU/QQ联调。遇到缺文件应补资产或修路径，不应通过删除校验来让模型“勉强启动”。
