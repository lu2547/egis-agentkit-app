# Changelog

## 1.0.3 — 2026-11-23

- 升级配套 Framework 至 1.0.3，继续使用 AgentScope 2.0.12。
- 接入经过企业鉴权的原生队列 CRUD、排序和引导接口，以及用户消息编辑重发。
- 新增项目定时任务与运行记录接口，挂载受管调度生命周期。
- 虚拟用户技能导入改用独立 `/integrations/skills/imports` 入口。
- CLI 仅保留 `serve`、`serve-files`、`provision-admin`；结构初始化和升级走部署 SQL。

完整 [Release Notes](https://github.com/lu2547/egis-agentkit-framework/blob/1.0.3/scripts/releases/1.0.3/release-notes.md) 和 [SQL/部署说明](https://github.com/lu2547/egis-agentkit-framework/blob/1.0.3/scripts/releases/1.0.3/README.md)。
