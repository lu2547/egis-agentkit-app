# Skill 接入指南 · 虚拟用户

从管理员处获取 AgentKit 服务地址和虚拟用户 Token。每次请求都带 `Authorization: Bearer <token>`。下面用 `BASE_URL` 和 `SKILL_TOKEN` 表示这两个值。

## 接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/manager/skills/imports` | 上传 ZIP，返回 HTTP 202 和 `job_id` |
| GET | `/manager/skills/imports/{job_id}` | 查询指定任务 |
| GET | `/manager/skills/imports` | 查询本人提交的任务，返回 `items` |
| POST | `/manager/skills/imports/{job_id}/retry` | 重试 `failed` 任务，无需重新上传 ZIP，返回 HTTP 202 |

## 上传示例

上传使用 `multipart/form-data`。必传 `file`，可选 `category`。ZIP 内必须有一份 `SKILL.md`，在文件开头的 YAML 中填写 `version` 或 `metadata.version`，例如 `1.0.0`。虚拟用户提交的包归属为系统技能。

```bash
curl -fsS -X POST "$BASE_URL/manager/skills/imports" \
  -H "Authorization: Bearer $SKILL_TOKEN" \
  -F 'file=@daily-report.zip;type=application/zip' \
  -F 'category=办公协同'
```

响应中的关键字段

```json
{
  "job_id": "a1b2c3d4e5f6478890aabbccddeeff11",
  "status": "queued",
  "resource_id": "skill-a1b2c3d4e5f6478890aabbccddeeff11",
  "resource_version": null
}
```

## 查询、重试和更新

```bash
# JOB_ID 取上传响应的 job_id。
curl -fsS "$BASE_URL/manager/skills/imports/$JOB_ID" \
  -H "Authorization: Bearer $SKILL_TOKEN"

curl -fsS "$BASE_URL/manager/skills/imports" \
  -H "Authorization: Bearer $SKILL_TOKEN"

curl -fsS -X POST "$BASE_URL/manager/skills/imports/$JOB_ID/retry" \
  -H "Authorization: Bearer $SKILL_TOKEN"
```

`queued`、`running` 表示处理中，`pending_approval` 表示待管理员审核，`succeeded` 表示已发布。失败看 `error`，审核拒绝看 `review_reason`。

更新时用原虚拟用户再次调用上传接口，额外传 `-F "resource_id=$SKILL_ID"`。`SKILL_ID` 取已发布任务的 `resource_id`，同时将包里的版本改成新值。
