# egis-agentkit-app

WorkBuddy 启动与 HTTP 组合应用。首版已实现，前端在相邻的 `egis-agentkit-frontend`。

首次环境初始化见 [初始化脚本与说明](../egis-agentkit-framework/scripts/init/README.md)，用于企业已经提供的 NAS、Nacos、Redis、Kafka 和 PG，不安装或拉起基础设施。

应用代码只保留 `bootstrap/` 和 `controller/` 两个职责目录，包入口为 `__main__.py`。`bootstrap` 装配原生应用、生命周期、路由和管理命令；`controller/base` 提供 HTTP 依赖、响应及异常映射，其他 Controller 按领域分包，请求/响应模型跟随领域。Project 接口按项目、文件、预览、PPT 页面操作拆分。JWT/JWKS 客户端、统一身份守卫和 SSE 适配归 Framework，业务规则与持久化继续由 Framework Service/Storage 提供。

- 主应用直接用原生 create_app，保留其 lifespan；由 bootstrap 挂载领域 Controller 和统一身份/接口策略。
- 共享规则在 framework：User/Group、当前 Definition、私有自用、共享审核、USE、资源按需加载。
- 只有 user/admin；系统注册默认无 USE；私有轻量资源保存自用无审核，只有共享审核。
- PG 保存会话状态及 NAS 日志的提交位置。standalone 使用原生内存总线。cluster 继续使用 Kafka 唤醒与广播、PG 待处理队列与租约，并将会话事件回放保存在 Redis Streams。
- 独立前端为 egis-agentkit-frontend，业务 Demo 在 demo/agentscope-demo/agentkit_demo。

完成首次初始化并由运行平台注入应用配置和密钥后，使用应用 Python 环境启动：

```sh
uv run python -m egis_agentkit_app serve
```

### Windows Agent 的 NAS 文件服务

在 Nacos 的 `agentkit.workspace.files` 中设置 `win: true`，将 `endpoint` 设为 Linux 文件服务的内网 HTTP(S) 地址，并通过 `tokenEnv` 指定两端注入同一凭据的环境变量名，默认是 `AGENTKIT_NAS_FILE_TOKEN`。Agent 继续用 `serve` 启动。已有本地挂载的 Agent 使用 `win: false`，默认走本地文件访问。项目 ReMe 记忆需要 `win: false`。

在 Linux 主机准备好 `agentkit.workspace.runtime.root` 和 `agentkit.skill.storage.root` 对应的 NAS 目录，以及 Nacos 连接配置，再启动独立文件服务。

```sh
uv run python -m egis_agentkit_app serve-files --host 127.0.0.1 --port 38093
```

跨主机部署时，由内网 HTTPS 代理转发到文件服务，或通过 `--host` 绑定受控的内网地址。文件服务启动时读取 Nacos 配置，文件访问设置或存储限额变更后需重启。HTTP 模式先部署与 API 同版本的文件服务，再启动 API/Worker。文件服务提供受管 NAS 访问，完整会话消息写入 `{workspace.runtime.root}/user/{uid}/session/history/{sid}/messages.jsonl`。PG、Kafka、Redis 及沙箱由 Agent 服务连接。

### 应用初始化

企业首次建表由部署流程或 DBA 执行 [pg.sql](../egis-agentkit-framework/scripts/init/pg.sql)，Kafka Topic、NAS 和 Redis 回放库等资源按[初始化脚本说明](../egis-agentkit-framework/scripts/init/README.md)准备。数据库变更、清理和资源预置由部署脚本负责。

应用 CLI 仅保留 `serve`、`serve-files` 和 `provision-admin`。首位管理员先完成登录登记，再由部署人员在本目录执行：

```sh
uv run python -m egis_agentkit_app provision-admin --user-id 用户ID
```

该命令仅调整指定用户的管理员角色；后续用户角色和组成员由管理台维护。

本机真实模型验收使用已有 agentscope-demo 的模型配置。正式公司推理网关可在 Nacos 更换模型、地址与凭据环境变量引用；当前 Adapter 使用原生 OpenAI 兼容协议，未把演示公共模型地址称作公司网关。

应用地址 `http://127.0.0.1:38092`，前端地址 `http://127.0.0.1:5179`。登录由外部身份服务处理，App 根据 Nacos 中的 RS256/JWKS、issuer 和 audience 校验令牌。开发登录见 [Egis AgentKit Mock](../egis-agentkit-mock/README.md)。`scripts/verify_live.py` 和 `scripts/verify_team.py` 从 `AGENTKIT_ACCESS_TOKEN` 读取已签发的访问令牌。

`/health/ready` 检查 PG 与 MessageBus 状态，并暴露 Nacos 连接、配置版本和重启需求。全框架读取一份 `agentkit.yaml`；更改内容必须递增 `agentkit.revision`。基础设施、认证、工作区和存储等固定装配配置变化需要重启；包含重启项的快照在旧进程中整份保留，重启后采用。

数据库连接参数统一由 Nacos `agentkit.client.postgres.connection` 提供，mode 为 key 时读取 password，mode 为 cyberark 时调用 CCP REST 取密；API 与管理命令均使用同一连接池创建入口，不读取 `.env` 完整连接串。日志由 `agentkit.logging` 配置，默认 INFO/JSON 输出到标准输出。填入 `directory` 绝对路径后，应用进程也会写入该目录下的 `agentkit-<主机名>-<PID>.log`。修改配置后重启服务生效。`client.tracing` 配置 Phoenix OTLP HTTP 导出，需开启 enabled。框架管理连接与关闭，埋点复用原生 TracingMiddleware。

专家可以使用平台工具、Skill 和 MCP。第三方专家由 HTTP 或 WebSocket 接入，会话运行时按权限加载定义和绑定资源。

部署时需预置系统 Skills 助手及公司组使用授权，应用 CLI 不提供资源初始化入口。用户可在助手对话中上传 ZIP 并要求安装，也可描述要复用的工作方法并要求创建个人技能。

外部系统上传 Skill 的鉴权和调用示例见 [Skill 接入指南](docs/Skill接入指南.md)。

技能发布时，默认用现有聊天模型根据 `SKILL.md` 的名称和简介生成简洁的 SVG 头像。生成的头像随技能版本存放在 NAS，并按技能权限读取。生成失败、图片不可读或关闭生成时，目录和详情会显示技能名首字。已有技能的预设头像继续使用。

在 Nacos `agentkit.skill.avatar` 下可设置 `enabled`、`modelKey` 和 `timeoutSeconds`。`modelKey` 为空时使用 `agentkit.model.selection.defaultKey`。技能导入和手动发布共用这份配置，使用 HTTP 文件模式的部署需同步更新 NAS 文件服务。

### 公司组与 MCP

用户首次登录时写入用户表并加入 Nacos `agentkit.access.companyGroupId` 指定的公司组，默认 ID 为 `company`。已有账号的成员关系由管理台维护。

管理员在「管理 → MCP 维护」登记、编辑和启停连接器。每个 ID 维护一条当前配置，启用后通过公司组在连接器广场可见。OAuth 连接器先由用户完成授权，再添加到个人助理。取消添加会保留授权。服务地址或认证配置变化后，用户需要重新授权。

OAuth 环境在 Nacos 配置 `agentkit.connector.oauth.redirectUri` 为前端 HTTPS 地址（路径 `/connectors/oauth/callback`），并按 `credentialKeyEnv` 注入凭据加密密钥。连接配置和授权存 PostgreSQL，会话开始时按当前权限装配到沙箱网关。

沙箱配置使用 `workspace.runtime.mode: pks` 和 `workspace.runtime.sandbox`。公司 PKS 的启动入口通过 `build_app(..., sandbox_client_factory=...)` 注入公司沙箱 Client 工厂，由 App 传给 Framework。直接运行 `serve` 时，Framework 使用开发适配器 OpenSandbox。用户工作区身份固定，各项目会话保留独立 cwd 和隔离执行绑定。文件、变更和预览管理归 Project。ReMe 为默认关闭的可选能力。

验收命令、结果与边界见 [实施记录](docs/实施记录.md)。Kafka 沿用原生 drain/spawn ACK 边界，不承诺运行完成后才 ACK，也不承诺业务 exactly-once；详情见 [MessageBus 验收](../egis-agentkit-framework/docs/MessageBus验收.md)。

管理列表默认每页 20 条，可通过 Nacos `agentkit.admin.pagination.defaultPageSize` 和 `maxPageSize` 设置。管理页从服务端按页取数据，回复反馈沿用游标分页。

聊天消息统一通过 `POST /chat/` 进入 AgentScope 原生 FIFO，返回 `status: "queued"` 和 `queue_item_id`。运行中补充也先排队，不传自研 delivery 字段。点击引导时，用 `POST /chat/queue/{item_id}/steer` 携带 `agent_id`、`session_id` 和当前 `reply_id`；注入发生在模型推理边界，不打断当前工具或模型请求。

通过 `GET /chat/queue` 读取队列，`PATCH /chat/queue/order` 排序，`PATCH/DELETE /chat/queue/{item_id}` 编辑或删除未消费项。所有入口均校验身份、会话、项目和资源权限。集群模式的待发输入保存在 PostgreSQL，由原有 Kafka 唤醒链路触发消费。Redis Streams 提供会话事件回放，保留期由 `agentkit.client.redis.retentionSeconds` 设置。单机内存模式的队列在服务重启时清空。

限制沿用 Nacos `agentkit.session.steering`；`/manager/runtime-options` 提供输入区限额。1.0.3 还增加 `/manager/schedules`、`/manager/schedule-runs` 定时任务与运行记录接口。完整发布说明和执行脚本见 [1.0.3 发布](../egis-agentkit-framework/scripts/releases/1.0.3/README.md)。
