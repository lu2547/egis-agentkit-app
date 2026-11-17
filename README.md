# egis-agentkit-app

WorkBuddy 启动与 HTTP 组合应用。首版已实现，前端在相邻的 `egis-agentkit-frontend`。

首次环境初始化见 [初始化脚本与说明](../egis-agentkit-framework/scripts/init/README.md)，用于企业已经提供的 NAS、Nacos、Redis、Kafka 和 PG，不安装或拉起基础设施。

应用代码只保留 `bootstrap/` 和 `controller/` 两个职责目录，包入口为 `__main__.py`。`bootstrap` 装配原生应用、生命周期、路由和管理命令；`controller/base` 提供 HTTP 依赖、响应及异常映射，其他 Controller 按领域分包，请求/响应模型跟随领域。Project 接口按项目、文件、预览、PPT 页面操作拆分。JWT/JWKS 客户端、统一身份守卫和 SSE 适配归 Framework，业务规则与持久化继续由 Framework Service/Storage 提供。

- 主应用直接用原生 create_app，保留其 lifespan；由 bootstrap 挂载领域 Controller 和统一身份/接口策略。
- 共享规则在 framework：User/Group、当前 Definition、私有自用、共享审核、USE、资源按需加载。
- 只有 user/admin；系统注册默认无 USE；私有轻量资源保存自用无审核，只有共享审核。
- PG 使用平台提供的数据库；standalone 委托原生 InMemoryMessageBus，cluster 使用 Kafka 唤醒与广播、PG 状态与租约，不依赖 Redis。
- 独立前端为 egis-agentkit-frontend，业务 Demo 在 demo/agentscope-demo/agentkit_demo。

完成首次初始化并由运行平台注入应用配置和密钥后，使用应用 Python 环境启动：

```sh
python -m egis_agentkit_app serve
```

企业首次建表可交由 DBA 执行 [pg.sql](../egis-agentkit-framework/scripts/init/pg.sql)，应用启动时登记默认工具。现有 `init-db` CLI 也提供程序化建表和 Topic 初始化，但不创建初始管理员。`seed` 只用于导入演示用户、专家、Team、Skill/MCP 和演示授权，不属于企业首次初始化。`bootstrap_demo.py` 依赖已有本机基础设施和 Demo 密钥，不是企业环境初始化入口。

本机真实模型验收使用已有 agentscope-demo 的模型配置。正式公司推理网关可在 Nacos 更换模型、地址与凭据环境变量引用；当前 Adapter 使用原生 OpenAI 兼容协议，未把演示公共模型地址称作公司网关。

应用地址 `http://127.0.0.1:38092`，前端地址 `http://127.0.0.1:5179`。演示用户 `demo.user`，管理员 `demo.admin`；演示登录密码保存在本项目 `.env` 的 `AGENTKIT_DEMO_PASSWORD`，不写入前端或文档。正式环境由 Nacos 配置 RS256/JWKS、issuer、audience，令牌由公司身份服务签发。

`/health/ready` 检查 PG 与 MessageBus 状态，并暴露 Nacos 连接、配置版本和重启需求。全框架读取一份 `agentkit.yaml`；更改内容必须递增 `agentkit.revision`。基础设施、认证、工作区和存储等固定装配配置变化需要重启；包含重启项的快照在旧进程中整份保留，重启后采用。

数据库连接参数统一由 Nacos `agentkit.client.postgres.connection` 提供，mode 为 key 时读取 password，mode 为 cyberark 时调用 CCP REST 取密；API 与管理命令均使用同一连接池创建入口，不读取 `.env` 完整连接串。日志从 `agentkit.logging` 读取，默认 INFO/JSON 输出到标准输出；`client.tracing` 配置 Phoenix OTLP HTTP 导出，需开启 enabled。框架管理连接与关闭，埋点复用原生 TracingMiddleware。

专家可以使用平台工具、Skill 和 MCP。第三方专家由 HTTP 或 WebSocket 接入，会话运行时按权限加载定义和绑定资源。

沙箱配置使用 `workspace.runtime.mode: pks` 和 `workspace.runtime.sandbox`。Manager 与 Core 实现原生通用接口；当前开发适配器通过 OpenSandbox SDK 通信，公司 PKS 需注入实际沙箱 Client，配置命名不代表公司通信实现已接通。用户工作区身份固定，各项目会话保留独立 cwd 和隔离执行绑定。文件、变更和预览管理归 Project。ReMe 为默认关闭的可选能力。

验收命令、结果与边界见 [实施记录](docs/实施记录.md)。Kafka 沿用原生 drain/spawn ACK 边界，不承诺运行完成后才 ACK，也不承诺业务 exactly-once；详情见 [MessageBus 验收](../egis-agentkit-framework/docs/MessageBus验收.md)。
