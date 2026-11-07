# WorkBuddy 界面复刻 Implementation Plan

> 执行采用 superpowers:executing-plans；独立的目录、聊天和文件记录部分按 dispatching-parallel-agents 并行，文件所有权分开。用户已要求“列计划改起来”，按已给定参考执行，不增加审批环节。项目不是 Git 仓库，不创建仓库或提交。

**Goal:** 以 `demo/workbuddy-web` 为视觉基准复刻现有 Vue 工作台，接回真实 AgentKit 能力，并支持完整深浅主题。

**Architecture:** 保留现有 Vue Router、PG、Nacos、原生 AgentScope service/SSE；参考 Demo 的组件和布局，替换其模拟数据及本地演示操作。样式分为主题变量、基础样式、各组件独立 CSS，不在组件中重复固定颜色。

**Tech Stack:** Vue3、TDesign、Lucide（与参考相同的图标）、现有 Python framework/app、PG。

**Spec:** 用户 2026-11-05 六条要求及“组件化、样式提取、深浅模式”补充；参考实际路径为 demo/workbuddy-web（用户称 workbuddy_web）。

## Global Constraints

- 不修改 harness/agentscope 源码，不复制其 Agent loop、Storage 或 SSE。
- 保留养老险GPT 名称、Logo，个人助理三文档和真实授权/安装规则。
- 权限模式放输入框左下角，加号之后；模型在右侧；不得再放页面顶部。
- 统一能力目录顺序：个人助理、专家、专家团、技能、连接器。
- 专家：我的专家、添加专家；专家团：我的专家团、添加专家团；技能：我安装的、添加技能；连接器：只有我安装的。
- 技能/MCP 安装启停只供个人助理使用；专家/专家团直接召唤，不能借安装改变其绑定。
- 资料库替换为知识库“待规划”，复用参考 BookOpen 图标；不实现知识库业务。
- 主题变量接口 --bg/--surface/--hover/--text/--muted/--border/--accent/--shadow，另设语义色。主题持久化，首次跟随系统。
- 所有新增样式独立 CSS；最终将受影响旧组件样式一并提取并迁移变量，弹窗、菜单、代码预览都验证两种主题。

## Tasks

### 1. 主题、导航和整体布局

Files: frontend src/styles/{tokens,base,tdesign,layout}.css, composables/useTheme.ts, components/navigation/AppSidebar.vue, layouts/WorkbenchLayout.vue, components/common/AppIcon.vue。

- [x] 复用参考侧栏、最近列表及菜单布局；真实用户与会话替换 Demo fixture。
- [x] 最近会话操作菜单支持重命名/删除；调用真实接口，失败保留表单和旧值。
- [x] 账号菜单切深浅模式，localStorage 保存；刷新保持，首次跟随 prefers-color-scheme。
- [x] 提取 CSS、主题化原有 UI；保留键盘焦点及窄屏侧栏。

### 2. 目录、资源卡和图标库

Files: frontend views/{ExpertCatalog,Skills,Connectors}View.vue, components/catalog/*, components/experts/*, components/skills/*, components/common/{CatalogAvatar,AvatarPicker}.vue, domain/catalogIcons.ts, public/catalog/*。

- [x] 从参考复制专家/技能/目录图标原文件，建立稳定 ID 的标准库；表单仅提交允许的 ID，不接受任意外链。
- [x] 复刻目录 Header、分类、卡片和详情；数据来自 manager。
- [x] 目录五入口和右侧按钮按上述规则实现；“我的/我安装的”是真实筛选，不伪造数量或使用量。
- [x] 新建/编辑专家、专家团和技能可选库中图标，保存并重新打开一致。

### 3. 聊天、输入框和交互

Files: frontend components/composer/*, components/runtime/*, components/conversation/*, views/{Home,Conversation}View.vue, components/layout/ConversationTopbar.vue。

- [x] 参考 Demo 的欢迎页、顶部工具栏、消息/产物/过程和输入框样式；不引入其模拟输出。
- [x] 输入框加号 + 权限模式在左；模型 + 发送/停止在右；保留实际原生模式和 Nacos 可用策略。
- [x] 保留独立确认卡、上传/会话切换保护和不可在运行中改设置的约束。
- [x] 对话内容搜索、顶部菜单动作实际生效；没有后端能力的操作不能伪造成功。

### 4. 对话重命名与文件变更记录

Files: framework services/tasks.py, services/file_changes.py, storage/{tables,postgres}.py, middleware/file_changes.py（按公开扩展点注入）, app manager_router.py/schema.py/bootstrap 装配，frontend api/workspace.ts、components/workspace/*。

Interfaces:
- PATCH /manager/tasks/{sid}/name {name:string} -> Task；所有者、非空长度校验、原生锁、手动命名关闭原生自动命名。
- GET /manager/tasks/{sid}/file-changes -> {items:[{change_id,path,area,change_type,observed_at,size,previous_size}], ...}；仅当前会话授权用户，PG 持久保存。
- 文件记录由安全快照比较实际内容；首次基线不捏造已有文件历史；之后记录新增/修改/删除。调用原生工具与上传/交付后均能观测。初版不包含文件回退或完整历史正文。

- [x] 先补 PG/HTTP 回归：跨用户拒绝、运行中重命名冲突、名称持久、同大小内容变化、删除记录、重启保留、路径/软链接隔离。
- [x] 实现记录与公开 middleware 扩展，复用 Storage engine，不另建 Repository。
- [x] 右栏按参考重组为可切换视图，保留计划/全局工作空间/当前产物/预览，增加真实变更记录；删除文件显示记录但不能假预览。

### 5. 集成与验证

- [x] 类型检查、前端单测、浏览器回归、相关 PG/HTTP 测试。
- [x] 对照参考以相同桌面宽度检查首页、目录、菜单、聊天和预览，验证深浅模式和窄屏无横向溢出。
- [x] 真后端验证重命名和文件记录；重启 App 加载新后端，保留现有 Nacos 配置和用户数据。
- [x] 更新实施记录：列已完成、验证结果及不支持的边界。

## Review Focus

1. UI 改样式不能把真实权限/模型操作换成 Demo 的本地布尔值。
2. 多会话切换时上传、设置保存和预览旧响应不能串入新会话。
3. 深浅模式覆盖 TDesign Teleport 弹窗与代码/文档预览，不仅是页面底色。
4. 文件扫描不跟随软链接，不跨用户，不把既有文件伪造为历史新增。
5. 图标库是展示资料，绑定关系、USE 和编辑权仍由后端决定。

## 验收结果（2026-11-05）

- 前端：26 个单元测试、36 个 Playwright 场景通过；类型检查及生产构建通过；生产依赖审计 0 漏洞。
- 后端：117 个测试通过，22 个可选外部集成测试未启用；原生已有一条弃用提示。
- 实际后端：重命名、上传、交付、同大小内容修改、删除记录及跨用户 403 均通过；真实模型 CreateDemoReport 和产物读取通过。
- 独立代码审查：未发现已确认的重要 P1/P2 问题。
- 截图对照：同为 1500×1000；参考输入框宽792、高134，当前复用同一几何尺寸；保留养老险GPT标识及已要求的功能差异。
- 不修改 AgentScope 原生源码；其唯一已有脏文件仍为 workspace/_sandboxed_base.py。
