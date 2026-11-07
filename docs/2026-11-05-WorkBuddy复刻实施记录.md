# WorkBuddy 代码复用与接口适配

来源：`demo/workbuddy-web`。保留现有 Vue3/TDesign 应用、真实鉴权、PG/Nacos 和原生 AgentScope service。未把 Demo fixture 或本地安装布尔值带入运行应用。

| 参考组件 | 当前组件与职责 |
| --- | --- |
| AppSidebar、GlobalSearch | navigation：真实历史会话、重命名/删除、账号菜单和搜索 |
| CatalogHeader、CatalogPage、SkillCard | catalog/experts：五入口、真实筛选、详情和召唤 |
| ChatComposer、ComposerMenu、ContextPicker | composer：附件、资源选择、原生权限模式和模型 |
| AppTopbar、ConversationTimeline | layout/conversation：搜索、原生消息、过程和独立工具确认 |
| WorkspacePanel、ArtifactPreview | workspace：全局文件、当前产物、计划、预览与 PG 变更记录 |
| DialogShell、IconButton | common：共享弹窗、焦点约束及图标按钮 |

所有 Vue 组件样式已提取至独立 CSS。主题值集中于 `frontend/src/styles/tokens.css`；基础样式与 TDesign 变量分别在 `styles.css`、`styles/tdesign.css`。`useTheme` 提供切换，首次跟随系统，之后保留用户选择。文档自身的白纸/HTML 样式不被强制反色。

能力目录顺序：个人助理、专家、专家团、技能、连接器。个人助理仍维护 agent.md、soul.md、user.md。技能和 MCP 的安装、启停服务个人助理；专家/专家团仍由 Definition 固定装配并直接召唤。

图标原文件保存到 `frontend/public/catalog`，ID 注册表在 `domain/catalogIcons.ts`；新建/编辑专家、专家团、技能均可选择。Skill 图标随不可变资源版本写入 PG payload.avatar，内容仍在 Nacos。界面不加载任意外部头像 URL。

新增接口：

- `PATCH /manager/tasks/{sid}/name`：验证本人权限，取得原生会话锁，保存名称并关闭自动命名；运行中返回 409。
- `GET /manager/tasks/{sid}/file-changes`：先验证会话权限，再观察实际文件并读取持久记录；分页返回 `items / next_cursor / scan_error`。

文件记录由公开 Middleware 扩展和上传/交付接口触发，PG 使用 `ak_file_baselines / ak_file_fingerprints / ak_file_changes / ak_file_scan_errors` 四表。扫描在线程内执行，目录使用 no-follow 文件描述符，比较 SHA-256；首次只建基线，之后记录观察到的新增/修改/删除。扫描不完整时保留上一份快照，并返回扫描状态，不影响工具本身的结果。

初版扫描范围为当前会话 work/artifacts，限制 10,000 文件、总计 200 MiB、32 层目录和单路径 2,048 UTF-8 字节。记录的是观察时间与内容变化，不是每次文件系统写入的逐条事件，也不包含旧正文回退。全局 uploads 持续保留；会话附件复制到当前 work 后会生成对应记录。

验证：前端单测 26、浏览器场景 36；后端 117 通过、22 可选集成未启用；生产构建通过，存在已有大 chunk 提示。真实登录验证重命名/上传/交付/修改/删除及跨用户拒绝通过；真实模型调用 CreateDemoReport 并读取产物通过。截图在 `frontend/docs/screenshots/workbuddy/`。
