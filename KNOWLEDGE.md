# AgentKit 知识库接入

本说明以三个 Git worktree 的父目录 `egis-agentkit-knowledge/` 为根；入口 `README.md` 指向本文件。这里包含 `framework/`、`app/`、`frontend/`，分支均为 `feat/knowledge-base-integration`。原来的三个工作目录和运行中的服务没有被替换。

## 看效果

- 前端：http://127.0.0.1:5189
- 知识库目录：http://127.0.0.1:5189/knowledge-bases
- 独立 API：http://127.0.0.1:38096
- 验收报告与截图：`.runtime/acceptance/`

使用原开发环境的 `demo.user` / `demo.admin` 账号和密码登录。本环境的 JWT 密钥、数据库、Nacos 组、Kafka topic 和 NAS 子目录单独隔离，旧环境登录令牌不能直接使用。

仅在当前契约验收模式，查看资料原文前可访问 http://127.0.0.1:5189/knowledge/__contract/login 设置测试知识库 Cookie；该入口只存在于测试服务，真实 Java 模式使用其自己的登录/SSO。

当前启用 **接口契约验收环境**。使用两份接口/建表文档中的内容作为固定验收资料，真实 DeepSeek 模型通过正常 `/chat/`、原生工具执行和 SSE 产生回答。Java 地址、HMAC 应用和密钥尚未提供，因此不能把此验收说成已经联通现网 Java/LlamaIndex。生产客户端没有固定答案或本地检索回退。

## 能力和边界

```text
用户提问
  → 原生 ChatService / 模型决定调用 SearchKnowledge
  → KnowledgeManager 重读平台用户和启用组
  → 显式用户授权 ∩ Java 应用可见库
  → JavaKnowledgeClient 签名 POST /openapi/v1/query
  → 既有 Java → LlamaIndex
  → 原生 ToolResult 保存检索片段、文档身份与引用标记
  → 模型回答；正文引用和右侧“知识来源”定位到同一份依据
```

检索工具是系统默认只读工具；仅给有显式知识库授权的本地 Agent 装配，远程 Agent 不额外注入。沿用 AgentScope 的模型/工具循环，不拦截 `on_model_call`，不维护第二套聊天接口。

平台用户权限使用 `agentkit.knowledge.access.grants` 的个人/启用组映射，默认拒绝，管理员也没有隐式权限。这是集成层显式授权，**不会自动继承 Java PMS 的用户或文档权限**。HMAC 应用的 `kb_scope` 必须限定为允许对该平台授权人群开放的知识库；存在不同文档级权限的库不能仅凭库级映射向所有成员开放。

原文访问还要经过平台会话归属、已保存的真实成功工具结果、当前知识库权限检查，再由浏览器携带 Java 自己的 Cookie 请求其原文接口。平台 Bearer、应用 HMAC Secret 不发给浏览器的 Java 请求。Java Cookie 过期只显示知识库登录错误，不退出平台。

来源随原生消息持久化，刷新可以恢复；同一回答多次检索同一文档会合并展示，引用身份仍分别保留。无命中时不返回无依据的上游答案。前端将文档正文作为文字显示，引用只从匹配的成功工具结果生成；原文地址按配置的 HTTP(S) origin 白名单校验。

右侧展示检索时保存的片段、章节、文档名称；上游不提供页码或明确版本时不编造。`查看当前原文` 打开 Java 当前原件/预览，不承诺历史版本原件。切换会话和来源会取消旧的原文请求，不覆盖工作区未保存的编辑。

## 目录与分工

```text
framework/src/egis_agentkit/
├── client/knowledge/
│   ├── _client.py       JavaKnowledgeClient：连接池、精确请求、响应限额和安全错误
│   ├── _signing.py      HMAC 原始字节签名，不包含 servlet context
│   └── _models.py       Java 返回 DTO（保留原文档别名）
├── client/nacos/_knowledge_settings.py  连接、检索、授权、原文配置
├── core/knowledge/
│   ├── _access.py       用户/启用组与知识库的范围规则
│   └── _sources.py      引用归一化、去重及原生工具消息恢复
├── service/knowledge/_knowledge_manager.py
│                       目录、检索、当前授权和原件入口管理
└── extension/knowledge/_knowledge_search_tool_impl.py
                        原生 ToolBase 实现 SearchKnowledge

app/
├── src/egis_agentkit_app/controller/knowledge/_knowledge.py
│                       受平台认证保护的目录和原文入口
├── scripts/knowledge_dev.py            独立环境生命周期
└── tests/contracts/java_kb_server.py   仅显式启动的契约验收服务

frontend/src/
├── api/knowledge.ts                    两个认证域的请求和原件地址校验
├── domain/knowledgeSources.ts          原生消息解析、文档合并、引用定位
├── components/knowledge/               回复来源按钮、右侧来源及原文面板
└── views/KnowledgeBasesView.vue        当前用户有权访问的知识库目录
```

没有为这一功能新建数据库表。知识库和文档、版本、节点、索引仍由原 Java/LlamaIndex 管理。AgentKit 只使用现有用户/组、会话、消息存储；来源位于原生工具结果。没有原生 KnowledgeBase CRUD，也不复制 `llm_*` 表或直接连接 Java 业务数据库。

## Java / SQL 契约核对

原件完整归档在 `app/tests/contracts/documents/`，父目录的 `contracts/` 指向该目录，SHA256 在 `manifest.json`。提取的 `java-api.txt`、`database.txt` 只供阅读，**不是可执行迁移脚本**。

| 接口文档 | 实现 |
|---|---|
| 第 11.2 节 `GET /openapi/v1/kb` | 应用可见库；平台再次过滤用户授权 |
| 第 11.4 / 8.1 节 `POST /openapi/v1/query` | 精确发送 query / topK / threshold / sort / scope.kbIds |
| 第 11.1 节 HMAC | X-App-Id / X-Timestamp / X-Nonce / X-Signature；SHA256 实际 UTF-8 body；签名 PATH 不含 `/knowledge` |
| 第 4.11 节 `/kb/{kb_id}/documents/{doc_id}/raw/preview` | 知道 KB 身份时优先使用的 Cookie 预览接口 |
| 第 8 节 `/query/documents/{doc_id}/raw` | 来源未明确 KB 身份时的 Cookie 原件入口 |
| QueryResult / ReferenceItem | 接受 camelCase 与文档列明的 snake_case 别名；不添加页码、用户身份等不存在的 Java 字段 |

SQL 原件的 `llm_integration_app` 描述应用范围/密钥引用；实际 OpenAPI scope 按接口文档配置 `kb.read`、`query.run`。SQL 注释使用了冒号形式，两份文档有文字差异，部署时应与 Java 实际 scope 校验核对，客户端不会擅自修改两份文档或表定义。

`llm_document_version` 的 `(document_id, version_no)` 是唯一键；`llm_document_version_content.version_id` 唯一并关联 `llm_document_version.id`。本接入不改这些关系，也不执行 DOCX 中的 DDL。

## 接真实 Java

在 Java 管理端配置集成应用的 scope、kb_scope、IP 白名单、有效期及密钥引用。服务进程通过环境/密钥管理器注入 `AGENTKIT_KNOWLEDGE_SECRET`，密钥不要写进 Nacos。Nacos 配置的完整默认值见 `framework/examples/nacos/agentkit.yaml`：

```yaml
agentkit:
  knowledge:
    enabled: true
    label: 企业知识库
    connection:
      baseUrl: https://kb.example.com/knowledge
      appId: agentkit
      secretEnv: AGENTKIT_KNOWLEDGE_SECRET
    access:
      grants:
        - principalType: group
          principalId: company
          kbIds: [your_actual_kb_id]
    documents:
      publicBaseUrl: /knowledge
      allowedFileOrigins: [https://files.example.com]
```

连接/启用状态变更需要重启；检索限额、授权映射、原文入口支持现有 Nacos 热更新。若默认工具有 `registeredIds` 限定，须包含 `SearchKnowledge`。

推荐网关同源转发 `/knowledge/` 到 Java 的 `/knowledge/`，并让 Java 登录 Cookie 在该路径可用。跨域部署须配置带凭证的 CORS、Cookie SameSite/Secure，Java 或文件存储须允许本平台嵌入预览；地址为私有文件域时明确加入 `allowedFileOrigins`。开发 Vite 代理已按相同路径转发。原文无预览权限/网络不可用时，已检索的片段仍可读。

此版本提供查询和来源呈现，Java 继续承担知识库创建、上传、审核、解析、索引和原件管理。

## 运行与验证

以下命令在 `app/` 中运行，使用原项目可用的 Python 环境：

```bash
export PYTHONPATH=../framework/src:src
python scripts/knowledge_dev.py start --base-env /absolute/path/to/original-app/.env --contract-preview
python scripts/knowledge_dev.py status
python scripts/knowledge_dev.py stop
```

真实 Java 模式用 `--java-url https://host/knowledge --app-id <id> --kb-id <id>` 代替 `--contract-preview`；密钥放在上述环境或指定的 `--secret-env`。独立环境复用基础设施，但使用专用 `agentscope_knowledge` 库、`EGIS_AGENTKIT_KNOWLEDGE` 配置组、独立 Kafka topic 与 `workspaceRoot/knowledge-integration` NAS 前缀。数据库有目录归属标记，拒绝覆盖其他环境数据库；停止只针对脚本记录且进程启动时间匹配的进程组。

OpenSandbox 复用现有 Docker 运行时服务，工作文件使用独立 NAS 前缀。没有启动第二个扫描同一 Docker daemon 的 OpenSandbox 服务，避免影响原环境的沙箱生命周期。

前端 `npm test`、`npm run build`；真实模型端到端验收在 `frontend/` 执行：

```bash
AGENTKIT_PYTHON=/absolute/path/to/python node scripts/verify-knowledge.mjs --base-env /absolute/path/to/original-app/.env
```

验收账号的密码及令牌不会写入报告，`.runtime/` 中的密钥文件权限为 600。不要将运行数据和密钥提交 Git。

## 验收记录与实施决定

- 后端全量：555 通过、33 跳过；前端单测：137 通过；浏览器回归：183 通过；类型检查与生产构建通过。
- 真实模型端到端：两次自动 `SearchKnowledge` 调用、两份文档、正文引用、当前原文 Cookie 鉴权、刷新恢复、窄屏来源面板及跨会话清理通过。报告在 `.runtime/acceptance/report.json`。
- 独立终审发现公开 `/chat/` 允许调用方提交助手记录，现已限制为用户 text/data 消息、有效原生审批回包和空输入重触发。6 个伪造场景先失败，修复后与 4 个正常场景全部通过；真实接口验证伪造消息返回 403 且未落库。内部 Agent/Team 通信不经过该公开入口。
- 浏览器回归发现既有授权表仍显示一个空的版本列，已按“授权不绑定版本”去除，并修正测试等待表格加载后再断言，避免此前偶发漏检。
- 有一项较小的交互完善尚未做：命中片段块本身不能用键盘切换选中态；文档按钮和正文引用均可键盘操作，阅读与原文访问不受影响。

本次自主决定及边界：

1. 桌面 worktree 创建调用未返回且未产生工作树，检查后改用 Git worktree 建立三个独立分支目录；目录已完整保留，未合并、未推送。
2. 在没有真实 Java 地址/密钥时实现生产客户端，并显式运行测试契约服务验收 UI/工具链；代价是现网 Java/LlamaIndex、真实授权、网关 Cookie/CORS 与文件服务器 MIME/CSP 仍须部署联调验证。
3. HMAC 应用范围与平台个人/组授权取交集，当前不自动同步 PMS 文档权限；代价是部署方必须先正确配置应用和平台库级范围，不能将需要不同文档权限的库混作全员授权库。
4. 来源复用原生 ToolResult，不增加来源表；原文采用文档明确提供的 Cookie 入口，展示当前文件而非历史版本文件；代价是无法通过本版接口固定打开检索时的旧原件。
5. 复用原 OpenSandbox Docker 服务并隔离 NAS 前缀，避免第二实例扫描同一 Docker daemon；代价是沙箱服务容量仍与原环境共享。

两份提供文档的 scope 写法差异、真实文件预览策略及 PMS 权限继承都未擅自修改。本地测试没有验证这些部署条件，也没有修改 Java 业务表。
