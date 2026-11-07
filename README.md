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
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main migrate
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main seed
demo/agentscope-demo/.venv/bin/python -m egis_agentkit_app.main serve
```

`bootstrap_demo.py` 显式初始化本地 Nacos 配置批次和部署密钥；已有配置不覆盖。Skill/MCP 案例先按 [Hub 案例说明](../../demo/agentscope-demo/agentkit_demo/hub_cases/README.md) 启动并导入。迁移和 seed 都是显式命令，`serve` 不自动建表或授权。

本机真实模型验收使用已有 agentscope-demo 的模型配置。正式公司推理网关可在 Nacos 更换模型、地址与凭据环境变量引用；当前 Adapter 使用原生 OpenAI 兼容协议，未把演示公共模型地址称作公司网关。

应用地址 `http://127.0.0.1:38092`，前端地址 `http://127.0.0.1:5179`。演示用户 `demo.user`，管理员 `demo.admin`；演示登录密码保存在本项目 `.env` 的 `AGENTKIT_DEMO_PASSWORD`，不写入前端或文档。正式环境由 Nacos 配置 RS256/JWKS、issuer、audience，令牌由公司身份服务签发。

`/health/ready` 检查 PG 与 MessageBus 状态，并暴露 Nacos 连接、配置版本和重启需求。业务策略和模型配置经 Nacos 校验后整批切换；更改批次必须递增三个配置的 `config_version`。基础设施地址、认证和记忆开关变化需要重启。

管理员注册包后，其他实例在下一次装配时从 PG 查到固定路径、摘要与入口，按需加载；无需重启 App 或重复 `create_app`。Definition 固定装配版本；正在执行的 Turn 持有旧对象。包必须位于配置的可信发布根目录，依赖冲突会拒绝加载；首版没有整轮跨进程 Worker。

工作区首版使用 local，工作文件与交付文件分开，预览接口做路径、所有权和 HTML 隔离。OpenSandbox 服务已存在，NAS/Sandbox Adapter 尚未实现，选择 sandbox 会明确启动失败。ReMe 为默认关闭的可选能力，见 [ReMe 接入](../egis-agentkit-framework/docs/ReMe接入.md)。

验收命令、结果与边界见 [实施记录](docs/实施记录.md)。Kafka 沿用原生 drain/spawn ACK 边界，不承诺运行完成后才 ACK，也不承诺业务 exactly-once；详情见 [MessageBus 验收](../egis-agentkit-framework/docs/MessageBus验收.md)。
