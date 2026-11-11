"""Compose native create_app. Never mount it under a second FastAPI lifespan."""

import hmac
import os
from contextlib import asynccontextmanager

from agentscope.app import create_app
from agentscope.app.deps import get_current_user_id
from egis_agentkit.backend.nacos import NacosClient, NacosConfigProvider, NacosError
from egis_agentkit.backend.nacos import nacos_bootstrap as nacos_bootstrap
from egis_agentkit.bootstrap import init_agentkit
from egis_agentkit.errors import AgentKitError, UploadNameConflict
from fastapi import HTTPException, Request
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse

from .controllers.remote_agent import router as remote_agent_router
from .identity import JWTIdentity
from .manager_router import router
from .schema import LoginWrite
from .security import IdentityGuard, native_user_id
from .streaming import StreamReady


async def build_app(
    config: NacosConfigProvider, client: NacosClient, *, engine=None, owns_client=True
):
    settings = config.snapshot
    identity_settings = settings.user.identity
    download = settings.workspace.download
    database_url = os.environ.get(settings.backend.postgres.connection.url_env)
    download_secret = os.environ.get(download.secret_env)
    if not database_url or not download_secret or len(download_secret) < download.min_secret_length:
        raise ValueError("必须配置 PG 连接和统一 download_secret 部署密钥")

    identity = JWTIdentity(identity_settings)
    kit = init_agentkit(
        config, client, database_url, engine=engine, owns_client=owns_client
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
        ],
        title="Egis AgentKit",
        version="0.1.0",
    )
    app.state.egis_services, app.state.egis_config = services, config
    app.state.egis_remote_agents = kit.remote_agents
    app.state.egis_bus = bus
    app.dependency_overrides[get_current_user_id] = native_user_id
    app.include_router(router)
    app.include_router(remote_agent_router)

    @app.exception_handler(AgentKitError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(UploadNameConflict)
    async def upload_conflict(request, exc):
        return JSONResponse(
            {"detail": str(exc), "code": "upload_name_conflict"},
            status_code=exc.status_code,
        )

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
        if identity_settings.mode != "demo":
            raise HTTPException(404, "请使用公司统一认证")
        if request.client is None or request.client.host not in (
            "127.0.0.1",
            "::1",
            "testclient",
        ):
            raise HTTPException(403, "演示登录仅对本机开放")
        password = os.environ.get(identity_settings.demo_password_env, "")
        if len(password) < identity_settings.demo_min_password_length or not hmac.compare_digest(password, body.password):
            raise HTTPException(401, "用户名或密码错误")
        try:
            user = await services.users.get(body.user_id)
        except AgentKitError:
            raise HTTPException(401, "用户名或密码错误") from None
        return {
            "access_token": identity.issue(user.user_id, user.username),
            "token_type": "bearer",
            "expires_in": identity_settings.jwt_lifetime_seconds,
        }

    @app.get("/health/ready", tags=["health"])
    async def ready():
        await kit.check_database()
        bus_health = bus.health()
        body = {
            "is_ready": bus_health["is_ready"],
            "message_bus": bus_health,
            "config_version": config.snapshot.revision,
            "is_nacos_connected": config.is_connected,
            "restart_required": config.restart_required,
            "deployment_mode": settings.backend.kafka.connection.deployment_mode,
        }
        return JSONResponse(body, status_code=200 if body["is_ready"] else 503)

    native_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with kit.lifespan(native_lifespan(application)):
            yield

    app.router.lifespan_context = lifespan
    return app
