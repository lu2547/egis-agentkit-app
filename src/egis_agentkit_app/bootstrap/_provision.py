"""Explicit additive provisioning and named demo fixtures; never run on serve."""

import os

from egis_agentkit.bootstrap._demo_tools import deploy_demo_report_tools
from egis_agentkit.bootstrap._skill_tools import deploy_skill_tools
from egis_agentkit.client._postgres import (
    create_postgres_engine_from_config,
    postgres_url,
)
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap
from egis_agentkit.client.nacos._config import LivePolicies
from egis_agentkit.core.message_bus import EgisMessageBus
from egis_agentkit.service._user import UserService, require_admin
from egis_agentkit.service.resource._catalog import ResourceService
from egis_agentkit.service.resource._skill_import import SkillImportService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.storage._schema import cleanup_schema
from egis_agentkit.storage._skill_reset import reset_skills
from egis_agentkit.storage.project._files import ProjectFileStorage

from ._demo import seed_demo
from ._skill_assistant import provision_skill_assistant


async def provision(command, *, database=None, apply=False, user_id=None):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        settings = provider.snapshot
        postgres = settings.client.postgres
        url = postgres_url(postgres)
        engine = create_postgres_engine_from_config(postgres)
        try:
            if command in {"cleanup-db", "upgrade-db", "reset-skills"}:
                if command == "reset-skills":
                    if os.name == "nt":
                        raise ValueError("请在挂载 NAS 的 Linux 宿主运行 reset-skills")
                    if apply and postgres.connection.host not in {
                        "127.0.0.1",
                        "::1",
                        "localhost",
                    }:
                        raise ValueError("reset-skills 只能应用到本机开发库")
                    workspace = settings.workspace.runtime.root
                    upload_root = settings.skill.storage.root
                    if upload_root is None:
                        raise ValueError("请先配置技能上传目录")
                    result = await reset_skills(
                        engine, workspace, upload_root, database=database, apply=apply
                    )
                elif command == "upgrade-db":
                    from egis_agentkit.storage._schema import upgrade_schema

                    result = await upgrade_schema(
                        engine, database=database, apply=apply
                    )
                else:
                    result = await cleanup_schema(
                        engine, database=database, apply=apply
                    )
                print(f"目标数据库 {result.database}，schema {result.schema}")
                for name, state in result.tables.items():
                    print(f"{name:<28} {state}")
                return

            storage = AgentKitStorage(url, engine)
            if command in {"provision-admin", "seed"}:
                users = UserService(storage, settings.access)
                user = await users.get(user_id)
                if command == "provision-admin":
                    await users.provision_admin(user.user_id, actor="deployment-cli")
                    print(f"已设置管理员 {user.user_id}")
                    return
                require_admin(user)

            resources = ResourceService(
                storage,
                settings.workspace.runtime.root,
                policies=LivePolicies(provider),
                config=provider,
            )
            deploy_demo_report_tools(
                resources.tool_registry,
                ProjectFileStorage(settings.workspace.runtime.root, config_provider=provider),
            )
            deploy_skill_tools(
                resources.tool_registry, SkillImportService(storage, resources)
            )
            if command == "init-db":
                await storage.init_schema()
            if command in {"init-db", "provision-skill-assistant"}:
                await resources.seed_builtin_tools()
                await provision_skill_assistant(storage, provider, resources.policies)
            if command == "provision-skill-assistant":
                print("Skills 助手已配置，已向公司组授权")
                return
            if command == "init-db":
                bus = EgisMessageBus(engine=engine, kafka=settings.client.kafka)
                await bus.init_schema()
                await bus.ensure_topics()
                print("已初始化 AgentScope、AgentKit 数据表和消息总线")
                return
            async with storage:
                await resources.seed_builtin_tools()
                await seed_demo(storage, provider, resources, user)
        finally:
            await engine.dispose()
