# 语音教材、训练与验收

公开脚本在implementation/voice/training和implementation/runtime/cosyvoice3/scripts。运行前读脚本CLI；许多步骤依赖上一阶段清单，不能拿空目录直接训练。

## 数据

保留原音→切片→分离版本的关联。用自然句群与语气转折，保证文本对齐；不为长切片把不相邻片段拼成假上下文。叠词、语气词和轻声是风格的一部分，误识别时人工修正而不抹掉。

每条至少id/source_id/start/end/path/audio_sha256/text/transcription_review/speaker_review/emotion_review/split。训练和参考的使用范围分别记录，不把holdout用于优化器。代表性比一味增加小时数更重要。

## 原项目配置记录

GPT阶段官方s1v3初始化，batch1、梯度累计4、10轮、每2轮保存；实现热身与余弦学习率计划。SoVITS官方ProPlus初始化，batch1、LR1e-4、文本子模块倍率0.4、BF16计算/FP32谱损失、冻结量化器，保留原训练目标。最终GPT6/原SoVITS14来自人评。

CV2/3 LoRA试验只针对语音LLM q/v，r8、alpha16、dropout0.05，冻结声学部分；CV3必须用自己的tokenizer重提数据。它们不能代替聊天人格训练，也不能把GPT-SoVITS权重导入CV3。完整模型和训练数据不随公开源码分发。

训练前先做最小batch前后向、保存/重载。冻结模块、学习率、累计步数和截点都写入receipt。不能仅因第1轮人评更像，就证明第2轮差一定是学习率过高。

## CPU评测器

`runtime/cosyvoice3/scripts/audio_critic.py --help`可查看真实CLI，在自己的语音环境、自己的评测清单运行。它设置CUDA_VISIBLE_DEVICES=-1，仍需Torch/torchaudio、ONNX、Praat和本地识别模型。

维度：CAMPPlus声纹余弦；F0/能量/语速停顿代理；SenseVoice情绪与事件；弱信号/尾音高频异常。保留原始测量、阈值、内容flag和不确定性，不冒充自己已经听过。

同文复刻才考虑F0曲线DTW；不同文字比较分布，不能把汉语字调差异当不还原。气口的低HNR可能本来正常；高频毛刺也不直接等于电流音。只靠自动总分不能决定最终权重。

## 验收顺序

固定文案→GPT源声→同源D→PCM和SILK→QQ。叠词、短确认嗯、强情绪、轻声、长停顿、语气词与长解释分别留样。所有用户要求试听的候选保留，即使ASR或代理异常；发布新样本前给出内容与声学检查，但最终由真人判断。

正式QQ默认不逐条跑完整critic；代价更小的异常保护和失败回退保留。新参考、模型或参数改变后要重新比较，不把原项目的人评迁移为自己的认证。
