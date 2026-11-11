# AgentKit 首版能力归属与表结构改造计划

> 供评审。实施按下文四批推进，每批完成后独立验证。本文只记录方案，业务代码、Nacos 配置、表结构和运行环境待评审后改动。

**目标**　从个人助理、本地专家、主理人、远程专家开始，把写入、装配、调用和权限分别交还给业务拥有者。定义、资源和会话各保留一处权威记录。

**架构**　保留 `service/`、`storage/`、`extension/`、`backend/`、`bootstrap/` 和根目录 `errors.py`。Service 按业务能力组织，Storage 承担 SQL、事务和数据模型，Extension 对接 AgentScope。App 负责 HTTP 和鉴权入口，前端用领域接口渲染。

**技术栈**　现有 AgentScope、Python、PostgreSQL、Kafka、Nacos、Vue。继续沿用 AgentScope ChatService、原生消息、Team invite/inbox/TeamSay 和流式协议。

## 1. 现状核对

- `service/agent/_definition_base.py` 把 `build/save` 声明为抽象方法，又有 `_create_definition/_update_definition/_disable_definition`。专家和主理人多数是薄转发，个人助理的 `save` 永远返回 Forbidden。远程专家目前继承本地专家，通过 `payload.execution_type` 区分。
- 个人助理三份文档现在在 `_user.py::PreferenceService`，启用的 Skill/MCP 由 ResourceService 读原生 `skills/mcps` 安装记录，运行时又由 Workspace/Skill 扩展挑选。专家和主理人已有固定 `payload.bindings`。Team 已把主理人及成员引用写在版本 payload。
- `ExecutionGraph` 是从这些绑定重建的内存字典。授权、邀请、会话装配和工具加载都消费它，数据库没有 ExecutionGraph 表。Project ID 已写入原生 Session state，同时又写 `ak_project_sessions`。原生 `sessions.agent_id` 与业务定义 ID 是两个不同标识。
- `ak_resource_assets.payload` 主要保存 Skill、MCP、工具各自的配置和展示信息，也含 MCP 的认证方式等技术配置。使用授权的权威来源是 `ak_resource_grants`。某个环境里授权表是否有记录，需要单独查询该环境。
- Nacos 目前读取 `agentkit-runtime.yaml`、`agentkit-models.yaml`、`agentkit-policies.yaml` 三份配置。上传大小归在 Policies，PG/Kafka/远程回包混在 Runtime，部分超时、扫描限额和退避仍散落在实现中。
- 文件扫描按 `(project_id, area, path)` 定位文件，对实际读到的字节计算 SHA‑256 并累加字节数。两次的 `(digest, size)` 相等就跳过，任一项不同即记修改。新旧集合的增减分别记创建和删除。相同字节数的内容改动会被发现。大小供读取一致性、扫描上限和变更展示使用。mtime 和 inode 在一次读取前后用于防止写入中的文件形成错误基线。
- `ak_skill_imports` 已用于上传排队、领取、进度、重试。`ak_skill_archives` 已用于保留已注册 Skill 的原始包，供下载和物化。两处属于不同阶段。
- `ak_remote_agent_runs` 当前支持三种传输的重试和结果复用。异步 HTTP 用它核对回包签名及超时，Team 成员用它标记是否已通过 TeamSay 回报。它的写读路径都参与运行状态裁决。诊断日志继续走应用日志。

## 2. 目标代码结构与能力

一个 Service 文件只放一个 Service；能力用该 Service 的方法表达。目录只在确实有多项独立职责时分开。辅助对象跟随所属业务，Factory 由所属能力或注册回调持有。模块顶部用中文一句话说明职责，随后列核心能力；多阶段方法用中文标出校验、业务操作、提交等步骤。类和方法名用业务词。

| 文件或组件 | 负责的能力 |
| --- | --- |
| `service/agent/_definition_base.py` | 仅保留四类共同的定义能力。把固定类型的定义装成原生 Agent 运行记录，复用创建版本时的公共校验、落库和事务编排。共同的写入步骤只写一遍。保留一个真正有差异的抽象入口，用于按类型生成定义数据。下面的各类能力决定何时调用公共步骤。 |
| `service/agent/_personal_definition.py` | 按用户原子取得或创建个人助理。编辑 `AGENT.md`、`SOUL.md`、`USER.md`，组装个人提示和已有记忆。读取并启停个人在广场选用的 Skill/MCP，运行时按当前授权选资源。系统默认工具自动装配，个人助理不获得任何专家专属工具。三份文档与安装项使用各自的明确方法。 |
| `service/agent/_expert_definition.py` | 创建本地专家、保存下一版、校验固定 Skill/MCP/Tool 绑定、准备独立召唤及供 Team 成员装配。专家使用自己版本的提示和绑定，用户在广场改安装状态只影响个人助理。 |
| `service/agent/_orchestrator_definition.py` | 在 Team 创建、修改、停用的同一业务事务里维护主理人定义；按 Team 需求装配主理人的本地提示和协作能力。主理人只随所属 Team 使用。 |
| `service/agent/_remote_definition.py` | 固定远程类型，管理员登记、更新和校验协议、端点及凭据引用。远程专家与本地专家共享公共定义能力，各自维护业务校验。专家目录同时查询两类专家。 |
| `service/agent/_remote.py` 和同目录协议实现 | RemoteAgentService 负责选择协议、执行、取消、接收和校验回包、处理超时和重试。RemoteAgentBase 仅作为三种协议的既有接口，保留同步 HTTP(S)、异步 HTTP(S) 加回包、WebSocket 三个实现。 |
| `service/agent/_query.py` | Agent 定义分页和单条详情。编辑走单条详情，目录走分页，按类型、用户、资源范围过滤。定义详情由这里组装，Access 返回权限结论和授权来源。 |
| `service/team/_definition.py` | Team 的独立定义写入及读取。维护团队名称、显示信息、主理人和成员，校验成员资格并固定所引用的 Agent 版本。保存 Team 与主理人使用同一存储事务。 |
| `service/team/_collaboration.py` | 召唤固定 Team、个人助理临时邀请专家的规则、加入/唤醒、成员与组长的收发资格。专家如何运行由 Agent 决定，Team 负责 invite、inbox 和 TeamSay 的协作关系。 |
| `service/access/_permission.py` | 资源能否查、用、改、分享、停用，按所有者、用户、组、来源计算。独立使用和经某个 Agent/Team 使用分别检查。给 Storage 查询所需的权限范围。 |
| `service/access/_grant.py` | 管理员直接授权、撤销；产生/回收 Agent 和 Team 依赖授权。支持多个独立来源共存，撤销按来源回收。资源整体停用时同步收回权限；业务生命周期由相应资源模块执行。 |
| `service/access/_share.py` | 指定个人、团队组或公司组；提交共享和共享新版本；管理员审核；批准时切共享版本、更新依赖权限。 |
| `service/resource/_skill.py`、`_skill_import.py` | 技能目录、详情、注册、发布、包校验、下载和运行时物化；导入文件独立负责上传队列、领取、失败和重试。安装启停的业务入口归个人助理，技能模块提供可安装的资产。 |
| `service/resource/_connector.py`、`_connector_auth.py` | 连接器目录、配置、测试、运行时客户端；OAuth/API key 的配置、授权、回调、刷新、撤销和凭据读取。凭据与资源使用授权独立。Nacos 负责配置中心。 |
| `service/resource/_tool.py` | 管理平台默认工具与专家专属工具的注册、展示和装配。工具只走注册和配置绑定，无独立授权记录。系统默认工具默认勾选、不可取消。专家专属工具只在该专家的上下文装配。 |
| `service/_user.py` | 登录身份同步、启停、普通用户/管理员身份及公司/团队分组管理。 |
| `service/_project.py` | 项目创建、默认项目、列表、改名、删除、用户归属检查，调用 Workspace 初始化/清理目录，调用 Session 管理会话。 |
| `service/_session.py` | 创建/恢复/列表/改名/设置/删除会话；持久化项目和业务定义关联，使用原生会话、消息和 Agent 记录。输入区选项交给同领域小模块聚合现有能力；统一用 Session 命名替换内部 `tasks`。 |
| `service/workspace/_files.py`、`_changes.py`、`_preview.py` | 管项目文件路径、上传覆盖、下载、删除和交付；扫描基线、变更历史和回复产物关联；办公文档预览与转换。 |
| `service/_model.py` | 模型目录、默认模型、用户可选项、会话覆盖和供应商配置解析，独立于 Agent/Team 定义。Catalog/Selection 等仅单点使用的薄包装收回 ModelService 方法。 |

### 写入和读取约定

- 四种 Agent 类型在对应类和输入模型内固定，库内使用 `personal/expert/orchestrator/remote`。保留请求的业务身份、配置内容，去掉要求客户端同时填多个互相校验的类型字段。
- `build` 表示创建首版。个人助理 `build(user)` 可并发重复调用；专家和远程专家走共同首版写入；主理人由 Team 的事务调用。已有可编辑定义使用 `save` 写下一版，共享同一写入实现。个人助理有 `save_documents` 和安装启停能力，取消其无效的通用 `save`。只有确实不同的规则由子类实现。
- 可变更的资源配置在领域层校验一次，数据库约束兜底。Storage 处理行锁、并发版本、关联读写和原子提交。跨领域事务传事务内的 Storage 访问对象，Service、Controller、Extension 都不传 SQL `conn`。现存直接 SQL 按表归属搬到 Storage。
- AgentQuery 查定义，AgentScope 运行时的 Session/Agent 读取扩展查原生 Record 和调用权限，两条入口职责独立。列表查询先按授权范围过滤再分页；详情也使用相同权限。未授权 ID 不返回卡片、名称或版本。
- 去掉顶层 `_execution.py`、`_execution_graph.py` 和 session 里的 `agent_node_key`。Agent 读取自己的 `bindings`，Team 读取自己的成员引用，Access 基于同一组引用建立依赖授权；运行时只生成这次调用所需的 Agent 及工具配置。定义的 payload 是绑定关系唯一的来源。

### Extension、Backend 和 Bootstrap

| 组件 | 实现手段与职责 |
| --- | --- |
| Agent remote middleware / Agent tools callback | 前者通过原生 `on_model_call` 调用远程执行。独立会话正常返回文本，Team 成员通过已授权的原生 TeamSay 回报。后者是 AgentScope 工具构建回调，调用 Agent 和 Tool 组装结果。 |
| 个人助理偏好 middleware / Skill loader impl / Skill binding middleware | 提示注入只调用个人助理文档与记忆能力；Skill loader 实现原生加载器；Skill binding 在回复阶段绑定本轮技能上下文。 |
| Team invite callback / Team prompt middleware | 邀请回调调用 Team 的成员规则与 Agent 的装配能力，走原生 invite；提示中间件注入本轮 Team 成员和角色提示。 |
| Session storage override / Session lock override / Session middlewares callback | 保持原生存储、锁和中间件签名，绑定会话运行上下文、选择和接入所需的中间件。 |
| Tool access callback / middleware | 在原生工具注册和调用扩展点检查 Access、Skill/MCP 凭据、工具所属专家及会话操作策略。 |
| Workspace manager impl / local override / prompt、file changes、read guard middleware | 实现 AgentScope Workspace 接口及目录生命周期，向模型提供路径信息，委托 Workspace 记录文件变更和产物。Read 拦截二进制，返回明确工具错误。 |
| Resource hubs impl / message bus impl | 沿用 AgentScope 的 SkillHubBase、MCPHubBase 和 MessageBus 接口。Hub 读取本地 Skill/MCP 服务；Bus 扩展接 Kafka 和 PG。 |
| `backend/` | PostgreSQL 连接池和事务底层，Nacos 初始化、YAML 加载、类型校验、配置快照和热更新，Kafka 连接与消息传输。 |
| `bootstrap/_init.py` | `init_agentkit()` 创建依赖并装配给 App 和 AgentScope。生命周期启动、关闭各对象由已有入口负责。 |

Service 层默认用具体类。AgentDefinitionBase 保留。三种远程协议和 AgentScope 扩展使用既有多实现接口。Skill/MCP 暂时复用原生 Hub 接口，不再为单一的本地实现新建一层 RegistryBase。原来 `ProjectStoreBase` 如只剩本地 Workspace 一个使用点，收回到具体 Workspace 能力。

## 3. Nacos 配置与魔法值

Nacos Data ID 统一为 `agentkit.yaml`，文件根键为 `agentkit`。点路径固定为 `agentkit.<领域>.<能力>.<属性>`。例如文件上传上限用 `agentkit.workspace.upload.maxBytes`，技能归档上限用 `agentkit.skill.archive.maxBytes`。现有三份配置迁到这一份，按部署环境使用各自 namespace。下面的值仅展示格式，部署时按已生效的值核对迁入。

```yaml
agentkit:
  revision: 1
  agent:
    remote:
      callback:
        publicBaseUrl: https://agentkit.example.com
        maxClockSkewSeconds: 300
  skill:
    archive:
      maxBytes: 52428799
  session:
    permissions:
      defaultMode: bypass
  workspace:
    upload:
      maxBytes: 20971520
    scan:
      maxTotalBytes: 209715200
  backend:
    postgres:
      pool:
        size: 10
        maxOverflow: 10
```

| 路径 | 配置能力 |
| --- | --- |
| `agentkit.agent.personal`、`agentkit.agent.remote` | 个人助理初始化模板引用与记忆开关，远程请求/回包上限、超时、重试和回包地址。具体专家的提示、绑定、远端配置继续由对应定义维护。 |
| `agentkit.team.invite`、`agentkit.session.permissions` | Team 邀请和成员上限；会话默认及可选操作模式。 |
| `agentkit.skill.archive`、`agentkit.skill.import` | 包体积、解包安全限制，导入租约、重试与轮询。 |
| `agentkit.connector.oauth`、`agentkit.tool.defaults` | OAuth 安全策略、超时和刷新窗口；工具配置使用已注册的平台工具标识。工具实现和注册由代码管理。 |
| `agentkit.access`、`agentkit.user.identity` | 资源访问和共享的可运维策略；用户身份来源、JWT 校验和认证配置。 |
| `agentkit.project`、`agentkit.workspace` | 项目默认设置；工作区目录、执行模式、上传、扫描、预览、交付和下载限制。 |
| `agentkit.model.catalog`、`agentkit.model.selection` | 模型目录、模型参数、默认模型、允许选择及覆盖的范围。 |
| `agentkit.backend.postgres`、`agentkit.backend.kafka`、`agentkit.backend.nacos.refresh` | 连接引用、PG 池、Kafka 地址与主题、Nacos 刷新间隔和失败处理。 |

- 业务判断、循环和类初始化里禁止出现裸写的阈值、超时、容量、批大小、重试次数、默认地址和功能开关。比如 `if total_bytes > settings.workspace.scan.max_total_bytes`。把配置值移入 Nacos YAML，由调用方拿类型化配置。单次操作读取同一份配置快照，避免中途混用两个版本。
- 初始化由 `backend/nacos` 连接、加载、验证和发布快照，`init_agentkit()` 获取已验证的配置。首启无有效配置则失败并指出具体键。刷新失败保留上一份有效快照并暴露状态。模型目录、限额、策略按快照更新，连接池、Kafka 连接、Workspace 根目录等基础设施参数标记为重启生效。
- 部署环境只提供连上 Nacos 所必需的地址、namespace、group 和认证凭据；数据库密码、JWT 签名密钥、API key 等使用 Nacos 中配置的密钥引用，由部署密钥注入实际值。用户选择、资源定义及授权是业务数据，仍由各自 Storage 保存。协议枚举和固定的协议/格式约定使用有语义的命名常量，数值型业务策略统一来自 Nacos。
- 逐个核对原有默认值、各环境配置和消费者，交付 YAML 样例、配置键说明和迁移映射。各批改造能力时同时迁移它的配置读法；末批验证缺键、错误类型、热更新、重启生效以及代码中残余的硬编码配置。

## 4. 授权、版本、会话

- 授权行按资源类型、稳定资源 ID、用户/组、来源记录。公司和团队用 Group，用户本人用 User。来源包括所有者、广场/管理员直接授权、来自某个 Agent 或 Team 的依赖。用根授权及直接来源关联回收，权限行无版本字段。例：三个专家和一次广场授权各有一条独立路径，撤销两个专家只收两条。
- 经 Agent/Team 获得的依赖权限限定在相应运行路径。公司能召唤专家 A，可以在专家 A 内使用它的 Skill；若没有 Skill 广场授权，个人助理无法安装该 Skill。目录过滤在后端完成。
- 各资源有所有者最新版本、当前共享版本。发布序号由服务端分配，界面显示 `1.0 → 1.1 → … → 1.9 → 2.0`。Agent/Team 用现有整数版本字段作并发控制和内部引用。Skill/MCP 的平台发布序号与包本身的版本元数据分开，Skill 的现有上传、归档和导入流程照原逻辑运转。普通页面只显示当前可用版，召唤旁显示淡色版本，不列历史版本。
- 第一次共享选定个人或组，审核任务固定当时的发布序号。已有共享且发布了新版本时，出现“共享新版本”，每个资源同时只允许一条待处理升级任务。批准时切唯一共享版本，并按现有有效受众重新计算派生权限。A/B/C 的直接授权行原样复用；若审核期间又发布一版，本次批准仍对应提交时的版本。管理员直接授权当前已共享版时立即生效，权限变更不会意外发布新私有配置。
- 专家和 Team 的版本固定资源/成员引用。普通新会话按当时用户可访问的版本创建。原生 Session 持久化项目 ID、Agent 或 Team 定义 ID、选中的版本、原生实例关联和实际使用的授权来源。再次打开仍是当初的专家或专家团。已有会话采用启动时固定的版本，每轮重验当前根权限和实际依赖权限。撤销权限或停用后阻止继续执行。已记录的消息与回复产物按会话所有者读取。版本更新导致旧会话的某项依赖失去授权时，明确阻止该依赖的执行，禁止静默换成其他专家。此项是本方案的会话策略，供评审。

## 5. PostgreSQL 变更清单

| 所属 | 表和处理 |
| --- | --- |
| Agent | 保留 `ak_agent_definitions`、`ak_agent_definition_versions`。主表放身份、启停、所有者最新及共享版本号，版本表放固定提示与绑定。按 Agent 类型持久化本地/远程区别。 |
| Team | 保留 `ak_team_definitions`、`ak_team_definition_versions`。主表放生命周期和版本指针，版本表放固定主理人和成员引用。 |
| 资源 | 保留 `ak_resource_assets`，存 Skill/MCP/Tool 的各版本配置；以同资源单调发布序号标识最新，唯一共享标记定位共享版。Tool 继续使用其注册版本，安装选择复用原生 `skills/mcps`。 |
| 权限 | 保留 `ak_resource_grants`、`ak_share_reviews`。Grant 删除资源版本字段，唯一键按稳定资源、受众、来源；Review 记录目标发布序号和申请类型，升级任务不重复保存原有受众。 |
| 用户 | 保留 `ak_users`、`ak_groups`。 |
| Skill / MCP | 保留 `ak_skill_archives`、`ak_skill_imports`、`ak_mcp_credentials`，分别承载已发布包、上传任务和用户连接凭据。 |
| Project / Session | 保留 `ak_projects`。原生 `sessions` 增加从该行会话绑定计算的可索引 `project_id`，同一行的业务引用支持恢复，移除 `ak_project_sessions`。 |
| Workspace | 保留文件基线、变更流水、回复产物这三份数据。将 `ak_file_fingerprints` 和 `ak_file_changes` 改为 `ak_workspace_file_fingerprints` 和 `ak_workspace_file_changes`，`ak_reply_artifacts` 按其业务名称保留。 |
| 远程 Agent | 将 `ak_remote_agent_runs` 改为 `ak_agent_remote_runs`。保留仍用于请求去重、跨进程回包、结果恢复及 TeamSay 回报的状态；不新增远程执行日志表。评估以固定连接引用代替整份配置，先验证恢复、重试、回包验签后再收减字段。 |
| MessageBus | `egis_bus_{keys,entries,registry,leases,broadcast_payloads}` 改为 `ak_bus_*`。这五张是当前自定义总线的序号/过期、队列与日志、注册、租约、广播载荷；只在 cluster 模式初始化。 |
| AgentScope | 保留 `agents/sessions/messages/teams/skills/mcps/credentials/schedules`。计划记录依然参与原生 Agent 删除流程。已有 `channels/knowledge_bases/knowledge_documents/sops/sop_runs` 由独立 AgentKit 库清理命令预检后清理。 |
| 已退场与库扩展 | `ak_definitions/ak_tool_installations` 只进入旧库清理清单。`spatial_ref_sys` 归 PostGIS，由库扩展管理。 |

首版空库预计 standalone 25 张应用表，cluster 30 张，包含 8 张 AgentScope 原生表。交付 `init-db` 的空库路径和有目标库检查、清单预览、依赖检查的升级/清理路径。旧开发库的业务授权迁移到版本无关模式时，若同一资源已有多个历史授权版，脚本报告冲突并停止该次升级，避免猜测当前共享版。已有总线采用原表改名保留运行数据。项目关系数据核对一致后才删除冗余表。脚本不靠运行时双写或旧字段兼容分支。

## 6. 实施与每批验收

### 第一批　Agent、Team 和绑定

- [ ] 建立 `agentkit.yaml` 类型化加载与快照，先迁 Agent/Team 配置，后续每批迁对应领域。
- [ ] 改造 framework 的 `service/agent`、`service/_team.py`、`storage/_definition.py`、`storage/model/_definition.py`，更新 App 的 Agent/Team controller。固定类型、去除重复写入入口，迁回个人文档/安装入口和远程执行。
- [ ] 把固定绑定和会话引用的消费迁到 Agent、Team、Access。逐个替换 Session、邀请回调、权限、工具和 Skill 加载中的图节点读法，再删除两个 execution 模块。
- [ ] 验证四类构造、个人助理并发初始化、个人三份文档、本地专家更新、主理人随 Team 回滚、远程专家独立召唤和邀请回包。运行 `test_definition_versions.py`、`test_remote_agents.py`、`test_remote_agent_native.py`、`test_collaboration.py`。

### 第二批　权限、共享和目录

- [ ] 改造 framework 的 Access、Resource 和对应 Storage；统一 App 的共享、授权和资源响应；更新前端专家、专家团、技能、连接器、工具和管理页。管理员管理入口依角色显示，管理接口同时由服务端鉴权。
- [ ] 实现稳定授权和独立来源撤销、当前共享版与单升级申请、过滤后分页、当前可用版展示和服务器版本生成。工具默认选中且不可取消。
- [ ] 验证越权目录/详情、多个派生来源分别撤销、三组共享升级只出一单、审批时又编辑一版、原接收者不变、依赖权限更新、`1.9 → 2.0`、管理员直授及 OAuth/API key 不泄漏。运行 `test_access_sources.py`、`test_versioned_authorization.py`、`test_asset_versions.py`、`test_local_resources.py` 和目录/管理页 Playwright 回归。

### 第三批　项目、会话、Workspace

- [ ] 改造 `service/_project.py`、`service/_session.py`、`service/_workspace.py`、Session Storage 扩展和项目/会话路由的内部调用。去掉 `ak_project_sessions` 写入与读取。项目、会话、文件各自归位，模型独立。
- [ ] 验证召唤专家 A 后刷新和进程重启仍是 A，召唤 Team 后成员仍归原 Team；多项目列表和删除隔离，已有消息与回复文件保留，邀请成员会话带同一项目 ID。用同大小内容替换、仅改时间戳、上传覆盖、删除、产物追踪验证 Workspace。运行 `test_projects.py`、`test_tasks.py`、`test_collaboration.py`、`test_file_changes.py` 和项目/会话浏览器回归。

### 第四批　发版脚本、命名、端到端

- [ ] 整理各领域 Storage/模型，收口残余 Service 层 SQL，切换 workspace、远程 Agent 和 Bus 表名。更新 App 的 `init-db`、清理入口和数据库表清单，交付各环境 Nacos 配置迁移与剩余魔法值扫描。
- [ ] 在一次性 PostgreSQL 上验证两种空库模式、旧库预览、升级重跑、失败回滚和实际表数；检查消息总线原数据随改名保留。运行 `test_schema_provisioning.py`、Bus 集成测试、框架全量相关测试、前端类型检查与真实页面走查。
- [ ] 最后分别实际走一条个人助理、一条本地专家、一条 Team、一条远程专家链路，检查目录、建会话、发消息、重开、权限撤销和产物。
