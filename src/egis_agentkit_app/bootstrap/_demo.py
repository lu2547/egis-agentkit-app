"""Explicit additive provisioning and named demo fixtures; never run on serve."""

import io
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZipFile

from egis_agentkit.service._user import UserService
from egis_agentkit.service.access._grant import GrantService
from egis_agentkit.service.agent._agent_manager import AgentManager
from egis_agentkit.service.team._definition import TeamDefinition
from egis_agentkit.storage import tables as t
from egis_agentkit.storage.model import AgentDefinition, Grant, Group
from sqlalchemy import select


def identifier(name):
    return uuid5(NAMESPACE_URL, "egis-agentkit-demo:" + name).hex


async def seed_demo(storage, provider, resources):
    users = UserService(storage)
    await users.sync_identity("demo.admin", "演示管理员")
    await users.provision_admin("demo.admin", actor="explicit-demo-seed")
    admin = await users.get("demo.admin")
    await users.sync_identity("demo.user", "演示用户")
    await users.save_group(admin, Group(group_id="egis-demo", group_name="演示工作组"))
    for uid in ("demo.admin", "demo.user"):
        user = await users.get(uid)
        if "egis-demo" not in user.group_ids:
            user.group_ids.append("egis-demo")
            await users.update_user(admin, user)
    if await storage.assets.get("skill", "egis-demo-report", "1.0.0") is None:
        default_skill = (
            Path(__file__).resolve().parents[5]
            / "demo/agentscope-demo/agentkit_demo/hub_cases/egis-demo-report"
        )
        skill_dir = Path(os.environ.get("EGIS_DEMO_SKILL_DIR", str(default_skill)))
        if not (skill_dir / "SKILL.md").is_file():
            raise ValueError("请配置 EGIS_DEMO_SKILL_DIR 指向演示 Skill 目录")
        archive = io.BytesIO()
        with ZipFile(archive, "w", ZIP_DEFLATED) as output:
            for file in sorted(skill_dir.rglob("*")):
                if file.is_file():
                    output.write(file, file.relative_to(skill_dir))
        await resources.upload_skill(
            admin,
            archive.getvalue(),
            "1.0.0",
            category="数据分析",
            resource_id="egis-demo-report",
            owner_type="system",
            owner_id="egis-demo",
        )
    if await storage.assets.get("mcp", "egis-demo-tools", "1.0.0") is None:
        await resources.save_mcp(
            admin,
            {
                "resource_id": "egis-demo-tools",
                "resource_version": "1.0.0",
                "owner_type": "system",
                "owner_id": "egis-demo",
                "display_name": "报告与计算连接器",
                "config": {
                    "transport": "streamable_http",
                    "url": os.environ.get(
                        "EGIS_DEMO_MCP_URL", "http://127.0.0.1:8766/mcp"
                    ),
                },
            },
        )
    agents = AgentManager(storage, provider.snapshot.access, config_provider=provider)
    grants = GrantService(storage)
    bindings = [
        {
            "resource_type": kind,
            "resource_id": name,
            "resource_version": "1.0.0",
            "resource_view_type": "system",
        }
        for kind, name in (
            ("skill", "egis-demo-report"),
            ("mcp", "egis-demo-tools"),
            ("tool", "CreateDemoReport"),
        )
    ]
    examples = [
        (
            "report-analyst",
            "报告分析专家",
            "数据分析",
            "梳理材料与证据，形成结构清晰、可核验的报告。",
            "chart",
        ),
        (
            "product-manager",
            "产品经理",
            "产品设计",
            "用户研究、需求梳理、产品方案与路线图规划。",
            "product",
        ),
        (
            "data-analyst",
            "数据分析专家",
            "数据分析",
            "分析业务数据，核对指标口径，解释变化与原因。",
            "data",
        ),
        (
            "document-writer",
            "文档写作专家",
            "文档处理",
            "整理会议记录、项目方案与企业工作文档。",
            "document",
        ),
        (
            "code-reviewer",
            "研发顾问",
            "系统开发",
            "分析代码与架构问题，给出可执行的改进建议。",
            "code",
        ),
        (
            "finance-advisor",
            "财务分析专家",
            "金融保险",
            "财务指标分析与报告，使用前需管理员授权。",
            "finance",
        ),
    ]
    saved = []
    for index, (name, display, category, description, avatar) in enumerate(examples):
        definition_id = identifier(name)
        async with storage.engine.connect() as conn:
            exists = await conn.scalar(
                select(t.agent_definition_summary.c.id).where(
                    t.agent_definition_summary.c.id == definition_id
                )
            )
        if not exists:
            await agents.add_definition(
                admin,
                AgentDefinition(
                    id=definition_id,
                    owner_type="system",
                    owner_id="egis-demo",
                    agent_name=name,
                    agent_display_name=display,
                    payload={
                        "description": description,
                        "category": category,
                        "tags": [category, "演示案例"],
                        "avatar": avatar,
                        "bindings": bindings,
                        "system_prompt": f"你是{display}。{description} 用中文回答。需要交付文件时调用 CreateDemoReport，把完整报告写入交付目录并告诉用户文件名。先用 Skill 阅读报告规范。计算任务可使用连接器。工具结果必须核验，不能捏造引用。",
                        "starter_prompts": [
                            "把这些需求整理成一份报告并交付 report.md",
                            "帮我梳理完成这项工作的步骤",
                        ],
                    },
                ),
            )
        if index < 5:
            # Explicit administrator action, separate from registration. No
            # grant is silently added by runtime/installation/definition save.
            await grants.grant(
                admin,
                Grant(
                    principal_type="group",
                    principal_id="egis-demo",
                    resource_type="agent",
                    resource_id=definition_id,
                    resource_view_type="system",
                    resource_owner_type="system",
                    resource_owner_id="egis-demo",
                ),
            )
        saved.append(definition_id)
    team_id = identifier("report-team")
    async with storage.engine.connect() as conn:
        exists = await conn.scalar(
            select(t.team_definitions.c.id).where(t.team_definitions.c.id == team_id)
        )
    if not exists:
        await TeamDefinition(
            storage, provider.snapshot.access, config_provider=provider
        ).save(
            admin,
            {
                "id": team_id,
                "owner_type": "system",
                "owner_id": "egis-demo",
                "team_name": "report-team",
                "team_display_name": "报告交付专家团",
                "payload": {
                    "description": "主理人协调报告分析和文档写作两位专家，完成材料梳理与交付。",
                    "category": "文档处理",
                    "tags": ["固定专家团", "报告交付"],
                    "starter_prompts": ["请专家团一起整理这份材料并交付报告"],
                },
                "orchestrator_config": {
                    "agent_name": "report-orchestrator",
                    "agent_display_name": "报告主理人",
                    "payload": {
                        "system_prompt": "你是报告交付专家团的主理人。用 TeamSay 分配任务给 report-analyst 和 document-writer，等待他们通过 TeamSay 返回结果，再汇总交付。不得创建或邀请其他成员。",
                        "bindings": [],
                    },
                },
                "members": [
                    {"definition_id": saved[0], "resource_view_type": "system"},
                    {"definition_id": saved[3], "resource_view_type": "system"},
                ],
            },
        )
    await grants.grant(
        admin,
        Grant(
            principal_type="group",
            principal_id="egis-demo",
            resource_type="team",
            resource_id=team_id,
            resource_view_type="system",
            resource_owner_type="system",
            resource_owner_id="egis-demo",
        ),
    )
    personal = resources.personal
    for uid in ("demo.admin", "demo.user"):
        await personal.get_or_add_definition(await users.get(uid))
    print(
        "Seeded demo.admin/demo.user, one Group, six experts, one fixed Team, local Skill/MCP catalog and deployed report tool"
    )
    print(
        "Five expert grants and one Group Team grant explicitly configured; finance expert remains denied"
    )
