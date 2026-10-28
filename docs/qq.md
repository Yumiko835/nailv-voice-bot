# AstrBot + NapCat 接入与运行

使用自己的独立QQ实例。此仓库无QQ号、Token、二维码、账号资料或原会话。建议仅白名单私聊/群，群内仅@回复。

## 接线

1. 从[AstrBot官方项目](https://github.com/AstrBotDevs/AstrBot)建立干净4.29.3基线实例，路径`runtime/astrbot/app`；独立安装依赖，不复制旧bot数据。
2. 从[NapCat官方项目](https://github.com/NapNeko/NapCatQQ)安装适合当前QQ版本的独立实例。原项目4.18.41只是历史基线，平台变化须核对官方文档。
3. 在AstrBot添加OneBot v11连接，与NapCat反向WebSocket地址、端口和Token对应。`config/onebot.example.json`是字段对照，不是可直接导入配置。
4. 将implementation里的astrbot_plugin_nailv放入本地实例plugins目录，按.env填bot/group/owner；让插件能找到release_config.py及角色tools。
5. 用本地run_astrbot.py加载nailv_provider适配。新建Provider指向自己的兼容接口和模型；密钥留本机。不要把占位字符串当真实Token运行。
6. 语音服务先在loopback49856启动。先验证文字，再验证Record/SILK实际收到并能播放。

源码中的NapCat小bootstrap仅描述独立profile与路径做法，不附QQ原生组件、wrapper.node或NapCat本体。没有对应上游补丁/兼容版本时，不应断言直接替换入口就能实现账号隔离；优先按当前官方部署方式独立安装。

## 日常操作

本地工作区的`runtime/astrbot/scripts/manage.py status/start/stop`管理本项目进程，检查PID创建时间和命令标记；先status再start，避免重复。控制面板代码也保留，但需要完整本地依赖和自己的登录配置。

AstrBot `/reset`清当前对话上下文，`/new`新建对话；`/stop`是停止当前agent任务，不等于关闭整个机器人。不同版本命令以实际管理界面为准。

QQ登录由用户在本地完成。保存profile可以减少重复扫码，仍可能失效；不保证永久免登录。不要为了“免扫码”在GitHub打包账号目录。

## 故障定位

- 只有文字：检查语音服务、生成结果、SILK编码、OneBot Record路径和超时，分别看日志。
- 语音文件本地正常但QQ缺首尾：先检查编码与播放路径，不先重训。
- 人设没加载：检查provider标记与系统上下文，不把普通Provider成功当作角色模块成功。
- 显存不足：确认只启动自己的worker，检查是否意外加载CV3 LLM/TRT/vLLM；不能按“所有python”杀进程。
- 可选插件受Packet实现限制时，如实记录；不要为插件功能关闭安全校验或复用普通QQ账号数据。
