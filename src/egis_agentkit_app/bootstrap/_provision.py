"""Explicit additive provisioning and named demo fixtures; never run on serve."""

import os

from egis_agentkit.client._postgres import create_postgres_engine
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap
from egis_agentkit.client.nacos._config import LivePolicies
from egis_agentkit.extension._demo_report_tool_impl import deploy_demo_report_tools
from egis_agentkit.extension._message_bus_impl import EgisMessageBus
from egis_agentkit.service.resource._catalog import ResourceService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.storage._schema import cleanup_schema
from egis_agentkit.storage.project._files import ProjectFileStorage

from ._demo import seed_demo


async def provision(command, *, database=None, apply=False):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        settings = provider.snapshot
        postgres = settings.client.postgres
        url = os.environ[postgres.connection.url_env]
        engine = create_postgres_engine(
            url,
            pool_size=postgres.pool.size,
            max_overflow=postgres.pool.max_overflow,
        )
        try:
            if command in {"cleanup-db", "upgrade-db"}:
                if command == "upgrade-db":
                    from egis_agentkit.storage._schema import upgrade_schema

                    operation = upgrade_schema
                else:
                    operation = cleanup_schema
                result = await operation(engine, database=database, apply=apply)
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
