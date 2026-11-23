"""为已登记的有效用户授予管理员角色。"""

from egis_agentkit.client._postgres import (
    create_postgres_engine_from_config,
    postgres_url,
)
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap
from egis_agentkit.service._user import UserService
from egis_agentkit.storage import AgentKitStorage


async def provision_admin(user_id: str):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        settings = provider.snapshot
        postgres = settings.client.postgres
        url = postgres_url(postgres)
        engine = create_postgres_engine_from_config(postgres)
        try:
            storage = AgentKitStorage(url, engine)
            users = UserService(storage, settings.access)
            user = await users.get(user_id)
            await users.provision_admin(user.user_id, actor="deployment-cli")
            print(f"已设置管理员 {user.user_id}")
        finally:
            await engine.dispose()
