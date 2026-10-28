# Security

不要把Token、API Key、QQ登录数据、二维码、私聊和真实账号配置发到Issue。发现凭据泄露先撤销/轮换，删除工作区文件不等于清除Git历史。

若仓库启用了GitHub Private vulnerability reporting，请通过Security页私密报告；否则只发不含利用细节/秘密的联系请求，等待维护者建立私密渠道。不要公开可直接滥用的生产信息。

服务默认只绑定loopback。不要直接开放原型HTTP接口到公网；这个版本没有提供公网多租户鉴权。离线release扫描是有限启发式，不能替代完整的依赖和安全审计。
