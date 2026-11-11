# egis-agentkit-app

WorkBuddy 启动与 HTTP 组合应用。首版已实现，前端在相邻的 `egis-agentkit-frontend`。

- 主应用直接用原生 create_app，保留其 lifespan；挂薄 Controller/manager_router 和统一身份/接口策略。
- 共享规则在 framework：User/Group、当前 Definition、私有自用、共享审核、USE、资源按需加载。
- 只有 user/admin；系统注册默认无 USE；私有轻量资源保存自用无审核，只有共享审核。
- PG 复用现有 Docker；standalone 委托原生 InMemoryMessageBus，cluster 使用 Kafka 唤醒与广播、PG 状态与租约，不新增 Redis。
- 独立前端为 egis-agentkit-frontend，业务 Demo 在 demo/agentscope-demo/agentkit_demo。

从工作区根目录执行，Python 环境使用已有 Demo 的 `.venv`：

```sh
uv pip install --python demo/agentscope-demo/.venv/bin/python --index-url https://pypi.org/simple -e 'egis/egis-agentkit-framework[cluster,test]' -e egis/egis-agentkit-app
demo/agentscope-demo/.venv/bin/python egis/egis-agentkit-app/scripts/bootstrap_demo.py
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main init-db
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main seed
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main serve
```

`bootstrap_demo.py` 初始化本地 Nacos 的 `agentkit.yaml` 和部署密钥，保留同一 namespace/group 的已有配置。已有环境按[配置迁移表](../egis-agentkit-framework/docs/配置管理.md)整理后发布。 `seed` 从本地示例目录登记 Skill 和 MCP，并为示例专家绑定平台报告工具。运行 MCP 工具前启动 [示例 MCP 服务](../../demo/agentscope-demo/agentkit_demo/hub_cases/README.md)。首次部署用 `init-db` 创建首版表结构和 Kafka topic，演示授权由 `seed` 单独建立。 表归属、首版建表范围和存量清理命令见 [数据库表清单](docs/数据库表清单.md)。

本机真实模型验收使用已有 agentscope-demo 的模型配置。正式公司推理网关可在 Nacos 更换模型、地址与凭据环境变量引用；当前 Adapter 使用原生 OpenAI 兼容协议，未把演示公共模型地址称作公司网关。

应用地址 `http://127.0.0.1:38092`，前端地址 `http://127.0.0.1:5179`。演示用户 `demo.user`，管理员 `demo.admin`；演示登录密码保存在本项目 `.env` 的 `AGENTKIT_DEMO_PASSWORD`，不写入前端或文档。正式环境由 Nacos 配置 RS256/JWKS、issuer、audience，令牌由公司身份服务签发。

`/health/ready` 检查 PG 与 MessageBus 状态，并暴露 Nacos 连接、配置版本和重启需求。业务策略和模型配置经 Nacos 校验后整批切换；更改批次必须递增三个配置的 `config_version`。基础设施地址、认证和记忆开关变化需要重启。

专家可以使用平台工具、Skill 和 MCP。第三方专家由 HTTP 或 WebSocket 接入，会话运行时按权限加载定义和绑定资源。

工作区首版使用 local，工作文件与交付文件分开，预览接口做路径、所有权和 HTML 隔离。OpenSandbox 服务已存在，NAS/Sandbox Adapter 尚未实现，选择 sandbox 会明确启动失败。ReMe 为默认关闭的可选能力，见 [ReMe 接入](../egis-agentkit-framework/docs/ReMe接入.md)。

验收命令、结果与边界见 [实施记录](docs/实施记录.md)。Kafka 沿用原生 drain/spawn ACK 边界，不承诺运行完成后才 ACK，也不承诺业务 exactly-once；详情见 [MessageBus 验收](../egis-agentkit-framework/docs/MessageBus验收.md)。
