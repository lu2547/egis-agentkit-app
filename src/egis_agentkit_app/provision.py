"""Explicit additive provisioning and named demo fixtures; never run on serve."""

import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from agentscope.app.storage import AsyncSQLAlchemyStorage
from egis_agentkit.config import NacosClient, NacosConfigProvider
from egis_agentkit.extensions.hub import NacosMCPHub, NacosSkillHub
from egis_agentkit.extensions.message_bus import EgisMessageBus
from egis_agentkit.models import Asset, Definition, Grant, Group
from egis_agentkit.packages import PackageLoader
from egis_agentkit.service.agent.package import PackageService
from egis_agentkit.service.resource.service import (
    mcp_config_checksum,
    skill_archive_digest,
)
from egis_agentkit.service.team.definition import TeamService
from egis_agentkit.services import AgentService, PermissionService, UserService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.storage import tables as t
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from .bootstrap import nacos_bootstrap


def identifier(name):
    return uuid5(NAMESPACE_URL, "egis-agentkit-demo:" + name).hex


async def provision(command):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        settings = provider.snapshot.runtime
        url = os.environ[settings.database_url_env]
        engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
        storage = AgentKitStorage(url, engine)
        bus = EgisMessageBus(
            deployment_mode=settings.deployment_mode,
            engine=engine,
            kafka_bootstrap_servers=settings.kafka_bootstrap_servers,
            topic_prefix=settings.kafka_topic_prefix,
        )
        try:
            if command == "migrate":
                # Native create_all is additive and preserves any existing
                # AgentScope records. Existing-column upgrades remain native
                # Alembic deployment operations, not private schema rewrites.
                async with AsyncSQLAlchemyStorage(
                    url, engine=engine, create_tables=True
                ):
                    pass
                await storage.migrate_enterprise()
                await bus.migrate()
                await bus.ensure_topics()
                print(
                    "Provisioned native/enterprise PG tables and Kafka topics; existing rows preserved"
                )
                return
            async with storage:
                await seed_demo(storage, provider, client)
        finally:
            await engine.dispose()


async def seed_demo(storage, provider, client):
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
    loader = PackageLoader([Path(p) for p in provider.snapshot.runtime.release_roots])
    packages = PackageService(storage, loader)
    releases = Path(provider.snapshot.runtime.release_roots[0]) / "egis-demo"
    for version in ("1.0.0", "1.1.0"):
        await packages.register(admin, releases / version, owner_id="egis-demo")

    # These administrative imports catalog the two already published PRIVATE
    # Nacos demo sources. This callback is confined to this explicit seed CLI.
    async def seed_read(*_):
        return True

    skill = await NacosSkillHub(client, authorize=seed_read).get_skill_version(
        "demo.admin", "egis-demo-report", "1.0.0"
    )
    mcp = await NacosMCPHub(client, authorize=seed_read).get_mcp_version(
        "demo.admin", "egis-demo-tools", "1.0.0"
    )
    archive = await NacosSkillHub(client, authorize=seed_read).download(
        "demo.admin", "egis-demo-report", "1.0.0"
    )
    content = bytearray()
    try:
        async for chunk in archive.stream:
            content.extend(chunk)
            if len(content) > provider.snapshot.policies.max_skill_archive_bytes:
                raise ValueError("演示 Skill 包超过上传限制")
    finally:
        await archive.stream.aclose()
    checksums = {
        "skill": skill_archive_digest(bytes(content)),
        "mcp": mcp_config_checksum(
            {"transport": "streamable_http", "url": mcp.config_template.url}
        ),
    }
    for kind, name, display, description in (
        ("skill", "egis-demo-report", "结构化报告", skill.description),
        ("mcp", "egis-demo-tools", "报告与计算连接器", mcp.description),
    ):
        asset = Asset(
            resource_type=kind,
            resource_id=name,
            resource_version="1.0.0",
            owner_type="system",
            owner_id="egis-demo",
            checksum_sha256=checksums[kind],
            download_url=f"nacos://{kind}/{name}/1.0.0",
            payload={
                "nacos_name": name,
                "display_name": display,
                "description": description,
                **({"is_skill_market_visible": True} if kind == "skill" else {}),
            },
        )
        async with storage.transaction() as conn:
            await conn.execute(
                insert(t.assets)
                .values(
                    **asset.model_dump(),
                    created_by=admin.user_id,
                    updated_by=admin.user_id,
                )
                .on_conflict_do_nothing()
            )
            # Trusted, explicit enrollment of the named V1 demo fixtures only.
            # Never overwrite a previously pinned source with a changed hash.
            await conn.execute(
                update(t.assets)
                .where(
                    t.assets.c.resource_type == kind,
                    t.assets.c.resource_id == name,
                    t.assets.c.resource_version == "1.0.0",
                    t.assets.c.owner_type == "system",
                    t.assets.c.owner_id == "egis-demo",
                    t.assets.c.checksum_sha256 == "",
                )
                .values(checksum_sha256=checksums[kind])
            )
    agents, permissions = (
        AgentService(storage, provider.snapshot.policies),
        PermissionService(storage, provider.snapshot.policies),
    )
    bindings = [
        {
            "resource_type": kind,
            "resource_id": name,
            "resource_version": "1.0.0",
            "resource_view_type": "system",
        }
        for kind, name in (("skill", "egis-demo-report"), ("mcp", "egis-demo-tools"))
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
                select(t.definitions.c.id).where(t.definitions.c.id == definition_id)
            )
        if not exists:
            await agents.save(
                admin,
                Definition(
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
                        "implementation": {
                            "assembly_ref": "egis-demo",
                            "assembly_version": "1.0.0",
                        },
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
            await permissions.grant(
                admin,
                Grant(
                    principal_type="all_users",
                    principal_id="*",
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
            select(t.definitions.c.id).where(t.definitions.c.id == team_id)
        )
    if not exists:
        await TeamService(storage, provider.snapshot.policies).save(
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
    await permissions.grant(
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
    for uid in ("demo.admin", "demo.user"):
        await agents.personal(await users.get(uid))
    print(
        "Seeded demo.admin/demo.user, one Group, six experts, one fixed Team, two package versions and two Nacos catalog sources"
    )
    print(
        "Five expert grants and one Group Team grant explicitly configured; finance expert remains denied"
    )
