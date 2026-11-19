"""Compose native create_app. Never mount it under a second FastAPI lifespan."""

import os
from collections.abc import Callable
from contextlib import asynccontextmanager

from agentscope.app import create_app
from agentscope.app._router import chat_router as native_chat_router
from agentscope.app.deps import get_current_user_id
from egis_agentkit.bootstrap import init_agentkit
from egis_agentkit.client.identity import JWTIdentity
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider
from egis_agentkit.client.sandbox import SandboxClient
from egis_agentkit.middleware.http._http_identity_middleware_impl import IdentityGuard
from egis_agentkit.middleware.http._request_logging import RequestLogging
from egis_agentkit.middleware.http._stream_ready_middleware_impl import StreamReady
from fastapi.middleware import Middleware

from .. import __version__
from ..controller.base import native_user_id, register_exception_handlers
from ._router import router


async def build_app(
    config: NacosConfigProvider,
    client: NacosClient,
    *,
    engine=None,
    owns_client=True,
    manage_logging: bool = True,
    sandbox_client_factory: Callable[[], SandboxClient] | None = None,
):
    """组装 HTTP 应用，向 Framework 传递部署方提供的沙箱 Client 工厂。"""
    settings = config.snapshot
    identity_settings = settings.user.identity
    download = settings.project.download
    download_secret = os.environ.get(download.secret_env)
    if not download_secret or len(download_secret) < download.min_secret_length:
        raise ValueError("必须配置统一 download_secret 部署密钥")

    identity = JWTIdentity(identity_settings)
    kit = init_agentkit(
        config,
        client,
        engine=engine,
        owns_client=owns_client,
        manage_logging=manage_logging,
        sandbox_client_factory=sandbox_client_factory,
    )
    services, bus = kit.services, kit.bus
    app = create_app(
        storage=kit.native_storage,
        message_bus=bus,
        workspace_manager=kit.workspace,
        skill_hubs=[kit.skill_hub],
        mcp_hubs=[kit.mcp_hub],
        extra_agent_tools=kit.tools,
        extra_agent_middlewares=kit.middlewares,
        download_secret=download_secret,
        enable_scheduler=False,
        enable_channel_worker=False,
        enable_index_worker=False,
        extra_middlewares=[
            Middleware(IdentityGuard, identity=identity, services=services),
            Middleware(StreamReady),
            Middleware(RequestLogging, access_log=settings.logging.access_log),
        ],
        title="Egis AgentKit",
        version=__version__,
    )
    app.state.egis_services, app.state.egis_config = services, config
    app.state.egis_remote_agents = kit.remote_agents
    app.state.egis_bus = bus
    app.state.egis_kit = kit
    app.state.egis_deployment_mode = settings.client.kafka.connection.deployment_mode
    app.dependency_overrides[get_current_user_id] = native_user_id
    # App 接管同一个聊天入口；移除原生路由避免运行匹配与 OpenAPI 各走一份。
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if getattr(route, "original_router", None) is not native_chat_router
    ]
    app.include_router(router)
    register_exception_handlers(app)

    native_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with kit.lifespan(native_lifespan(application)):
            yield

    app.router.lifespan_context = lifespan
    return app
