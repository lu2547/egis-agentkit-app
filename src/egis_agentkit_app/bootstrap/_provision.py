"""Explicit additive provisioning and named demo fixtures; never run on serve."""

from egis_agentkit.bootstrap._demo_tools import deploy_demo_report_tools
from egis_agentkit.client._postgres import (
    create_postgres_engine_from_config,
    postgres_url,
)
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap
from egis_agentkit.client.nacos._config import LivePolicies
from egis_agentkit.core.message_bus import EgisMessageBus
from egis_agentkit.service.resource._catalog import ResourceService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.storage._schema import cleanup_schema
from egis_agentkit.storage.project._files import ProjectFileStorage
from egis_agentkit.storage.skill._archive import SkillArchiveStorage

from ._demo import seed_demo


async def provision(command, *, database=None, apply=False):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        settings = provider.snapshot
        postgres = settings.client.postgres
        url = postgres_url(postgres)
        engine = create_postgres_engine_from_config(postgres)
        try:
            if command in {"cleanup-db", "upgrade-db"}:
                if command == "upgrade-db":
                    from egis_agentkit.storage._schema import upgrade_schema

                    operation = upgrade_schema
                else:
                    operation = cleanup_schema
                options = {}
                if command == "upgrade-db":
                    options = {"skill_archive_limits": settings.skill.archive}
                    if settings.skill.storage.root is not None:
                        options["skill_archives"] = SkillArchiveStorage.from_settings(
                            settings.skill
                        )
                    elif apply:
                        raise ValueError("技能归档迁移必须先配置 NAS 挂载目录")
                result = await operation(
                    engine, database=database, apply=apply, **options
                )
                print(f"目标数据库 {result.database}，schema {result.schema}")
                for name, state in result.tables.items():
                    print(f"{name:<28} {state}")
                return

            storage = AgentKitStorage(url, engine)
            resources = ResourceService(
                storage,
                settings.workspace.runtime.root,
                policies=LivePolicies(provider),
                config=provider,
            )
            deploy_demo_report_tools(
                resources.tool_registry,
                ProjectFileStorage(settings.workspace.runtime.root),
            )
            bus = EgisMessageBus(engine=engine, kafka=settings.client.kafka)
            if command == "init-db":
                await storage.init_schema()
                await resources.seed_builtin_tools()

                await bus.init_schema()
                await bus.ensure_topics()
                print("已初始化 AgentScope、AgentKit 数据表和消息总线")
                return
            async with storage:
                await resources.seed_builtin_tools()
                await seed_demo(storage, provider, resources)
        finally:
            await engine.dispose()
