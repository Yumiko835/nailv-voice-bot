# Contributing

先开Issue描述问题和最小复现；小修可直接PR。保持文字、检索、声音、编码和QQ传输的职责边界。避免给一个字写特例来掩盖参考污染、分句或采样问题。

运行`python scripts/check_release.py`、`python -m unittest discover -s tests -v`和离线demo。源码适配文件有source-manifest哈希，修改后同步更新对应release_sha256并在PR说明原因；source_sha256保留导出锚点。

语音变更另列模型/参考/种子、CPU指标及人工听感；没做GPU/QQ测试明确写未测。不要上传个人权重、未经许可的片段、原始会话或平台凭据。贡献按本项目AGPL-3.0范围提交，第三方代码保留原许可证和归属。
