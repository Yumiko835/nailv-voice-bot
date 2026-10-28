# Third-party notices and asset scope

本项目自有集成/工具代码使用AGPL-3.0-only。上游代码、模型和人物素材保留各自的权利；软件许可证不把它们重新许可为AGPL，也不授予真实人物声音和身份使用权。

| Component | Source | Observed license / treatment |
|---|---|---|
| AstrBot | https://github.com/AstrBotDevs/AstrBot | AGPL-3.0；本仓库包含自己的适配插件/launcher，不内置完整框架；文本在LICENSES |
| GPT-SoVITS | https://github.com/RVC-Boss/GPT-SoVITS | MIT；小型portable runtime兼容补丁保留MIT通知，其余自行获取 |
| CosyVoice | https://github.com/FunAudioLLM/CosyVoice | Apache-2.0；依赖源码自行获取，本仓库保留自己的调用/训练/评测代码 |
| NapCatQQ | https://github.com/NapNeko/NapCatQQ | 本体、原生wrapper和QQ组件不分发；使用者按对应版本上游许可安装 |
| SenseVoice / CAMPPlus / tokenizer / voice models | respective official model repositories | 权重不分发，各自模型条款独立核对 |
| Tencent SILK and codec dependencies | AstrBot/runtime dependency chain | 编解码依赖不内置，按对应上游说明获取 |

`vendor-patches/GPT-SoVITS/tools/portable_runtime.py`源自原本机MIT项目的兼容实现；随附`LICENSES/GPT-SoVITS-MIT.txt`，原版权通知适用。集成调用代码不表示所有上游功能均通过本项目测试。

文档中的少量原话作为工程分析例子保留来源标识和审核限制，不是完整人物数据授权包。原录音、字幕全文、376条表达卡全文、训练数据、个人权重、第三方头像、QQ资料和私聊均未包含。虚构示例明确标注fictional，不冒充原声证据。

官方许可证参考：[AstrBot](https://github.com/AstrBotDevs/AstrBot/blob/master/LICENSE)、[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/LICENSE)、[CosyVoice](https://github.com/FunAudioLLM/CosyVoice/blob/main/LICENSE)。具体版本的LICENSE和模型卡优先。
