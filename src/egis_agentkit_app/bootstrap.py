"""Compose native create_app. Never mount it under a second FastAPI lifespan."""

import hmac
import os
from contextlib import asynccontextmanager

from agentscope.app import create_app
from agentscope.app.deps import get_current_user_id
from egis_agentkit.auth import JWTIdentity
from egis_agentkit.bootstrap import build_components
from egis_agentkit.config import NacosClient, NacosConfigProvider, NacosError
from egis_agentkit.config import nacos_bootstrap as nacos_bootstrap
from egis_agentkit.errors import AgentKitError
from fastapi import HTTPException, Request
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse

from .manager_router import router
from .schema import LoginWrite
from .security import IdentityGuard, native_user_id
from .streaming import StreamReady


async def build_app(
    config: NacosConfigProvider, client: NacosClient, *, engine=None, owns_client=True
):
    settings = config.snapshot.runtime
    database_url = os.environ.get(settings.database_url_env)
    download_secret = os.environ.get(settings.download_secret_env)
    if not database_url or not download_secret or len(download_secret) < 32:
        raise ValueError("必须配置 PG 连接和统一 download_secret 部署密钥")

    identity = JWTIdentity(settings.auth)
    components = build_components(
        config, client, database_url, engine=engine, owns_client=owns_client
    )
    services, bus = components.services, components.bus
    app = create_app(
        storage=components.native_storage,
        message_bus=bus,
        workspace_manager=components.workspace,
        skill_hubs=[components.skill_hub],
        mcp_hubs=[components.mcp_hub],
        extra_agent_tools=components.tools,
        extra_agent_middlewares=components.middlewares,
        download_secret=download_secret,
        enable_scheduler=False,
        enable_channel_worker=False,
        enable_index_worker=False,
        extra_middlewares=[
            Middleware(IdentityGuard, identity=identity, services=services),
            Middleware(StreamReady),
        ],
        title="Egis AgentKit",
        version="0.1.0",
    )
    app.state.egis_services, app.state.egis_config = services, config
    app.state.egis_loader, app.state.egis_bus = components.loader, bus
    app.dependency_overrides[get_current_user_id] = native_user_id
    app.include_router(router)

    @app.exception_handler(AgentKitError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(NacosError)
    async def nacos_error(request, exc):
        return JSONResponse(
            {"detail": str(exc)}, status_code=getattr(exc, "status_code", 502)
        )

    @app.exception_handler(ValueError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.post("/auth/login", tags=["identity"])
    async def demo_login(body: LoginWrite, request: Request):
        if settings.auth.mode != "demo":
            raise HTTPException(404, "请使用公司统一认证")
        if request.client is None or request.client.host not in (
            "127.0.0.1",
            "::1",
            "testclient",
        ):
            raise HTTPException(403, "演示登录仅对本机开放")
        password = os.environ.get(settings.auth.demo_password_env, "")
        if len(password) < 16 or not hmac.compare_digest(password, body.password):
            raise HTTPException(401, "用户名或密码错误")
        try:
            user = await services.users.get(body.user_id)
        except AgentKitError:
            raise HTTPException(401, "用户名或密码错误") from None
        return {
            "access_token": identity.issue(user.user_id, user.username),
            "token_type": "bearer",
            "expires_in": 3600,
        }

    @app.get("/health/ready", tags=["health"])
    async def ready():
        await components.check_database()
        bus_health = bus.health()
        body = {
            "is_ready": bus_health["is_ready"],
            "message_bus": bus_health,
            "config_version": config.snapshot.config_version,
            "is_nacos_connected": config.is_connected,
            "restart_required": config.restart_required,
            "deployment_mode": settings.deployment_mode,
        }
        return JSONResponse(body, status_code=200 if body["is_ready"] else 503)

    native_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with components.lifespan(native_lifespan(application)):
            yield

    app.router.lifespan_context = lifespan
    return app
