# Skill/MCP 共享补齐

`ShareService.submit` 对 Skill/MCP 要求准确的 resource_version，只接受本人拥有且启用的资产，保存不可变 Asset 快照。批准时校验完整资产未变化，原子更新当前共享版本并创建 all_users USE；重复批准幂等。

HTTP 和前端详情抽屉已传递版本。Agent/Team 申请保留原契约。来源保存在 Nacos，PG 审核记录不复制正文。真实 PG 回归覆盖所有权、精确版本、停用、幂等及新版本共享；新增依赖边由 `test_shared_asset_edges.py` 验证精确审核版本，已审父级闭包保留固定依赖。
