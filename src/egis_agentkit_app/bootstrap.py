"""Compose native create_app. Never mount it under a second FastAPI lifespan."""

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from agentscope.app import create_app
from agentscope.app.deps import get_current_user_id
from egis_agentkit.auth import JWTIdentity
from egis_agentkit.config import (
    NacosBootstrap,
    NacosClient,
    NacosConfigProvider,
    NacosError,
)
from egis_agentkit.errors import AgentKitError
from egis_agentkit.hubs import NacosHubManagement, NacosMCPHub, NacosSkillHub
from egis_agentkit.packages import PackageLoader
from egis_agentkit.services import (
    AgentService,
    PermissionService,
    ShareService,
    UserService,
)
from egis_agentkit.services.assembly import ExecutionCoordinator, ScopedMessageBus
from egis_agentkit.services.document_preview import DocumentPreviewService
from egis_agentkit.services.factories import AgentFactories
from egis_agentkit.services.file_changes import FileChangeService
from egis_agentkit.services.models import ModelService
from egis_agentkit.services.packages import PackageService
from egis_agentkit.services.preferences import PreferenceService
from egis_agentkit.services.projects import ProjectService
from egis_agentkit.services.tasks import TaskService
from egis_agentkit.services.teams import TeamService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.workspace.files import WorkspaceFiles
from egis_agentkit.workspace.manager import EgisLocalWorkspaceManager
from fastapi import HTTPException, Request
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .manager_router import router
from .schema import LoginWrite
from .security import IdentityGuard, native_user_id
from .streaming import StreamReady


class _LivePolicies:
    """Services read the latest validated Nacos policy at each operation."""

    def __init__(self, provider):
        self.provider = provider

    def __getattr__(self, name):
        return getattr(self.provider.snapshot.policies, name)


def nacos_bootstrap():
    return NacosBootstrap(
        server_url=os.environ.get("NACOS_SERVER_URL", "http://127.0.0.1:8848"),
        console_url=os.environ.get("NACOS_CONSOLE_URL") or None,
        namespace_id=os.environ.get("NACOS_NAMESPACE_ID", "public"),
        group=os.environ.get("NACOS_GROUP", "EGIS_AGENTKIT"),
        identity_key=os.environ.get("NACOS_IDENTITY_KEY") or None,
        identity_value=os.environ.get("NACOS_IDENTITY_VALUE") or None,
        access_token=os.environ.get("NACOS_ACCESS_TOKEN") or None,
    )


async def build_app(config: NacosConfigProvider, client: NacosClient, *, engine=None):
    from egis_agentkit.services.resources import ResourceService

    settings = config.snapshot.runtime
    database_url = os.environ.get(settings.database_url_env)
    download_secret = os.environ.get(settings.download_secret_env)
    if not database_url or not download_secret or len(download_secret) < 32:
        raise ValueError("必须配置 PG 连接和统一 download_secret 部署密钥")
    if settings.workspace_mode != "local":
        raise ValueError(
            "当前工作区目录/产物 Adapter 为 local；配置 sandbox 前需要接入 NAS 路径映射"
        )
    owns_engine = engine is None
    engine = engine or create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        hide_parameters=True,
    )
    storage = AgentKitStorage(database_url, engine)
    bus = ScopedMessageBus(
        deployment_mode=settings.deployment_mode,
        engine=engine,
        kafka_bootstrap_servers=settings.kafka_bootstrap_servers,
        topic_prefix=settings.kafka_topic_prefix,
    )
    bus.coordinator = ExecutionCoordinator(storage, settings.workspace_root, config)
    loader = PackageLoader([Path(p) for p in settings.release_roots])
    identity = JWTIdentity(settings.auth)
    policies = _LivePolicies(config)
    services = {
        "storage": storage,
        "users": UserService(storage),
        "agents": AgentService(storage, policies),
        "teams": TeamService(storage, policies),
        "permissions": PermissionService(storage, policies),
        "sharing": ShareService(storage),
        "models": ModelService(storage, config),
        "files": WorkspaceFiles(
            Path(settings.workspace_root), config.snapshot.policies.max_upload_bytes
        ),
        "preferences": PreferenceService(storage, settings.workspace_root),
        "projects": ProjectService(storage, settings.workspace_root),
        "packages": PackageService(storage, loader),
    }

    async def authorize_hub(user_id, resource_type, resource_id, operation):
        return await services["resources"].authorize_hub(
            user_id, resource_type, resource_id, operation
        )

    skill_hub = NacosSkillHub(client, authorize=authorize_hub)
    mcp_hub = NacosMCPHub(client, authorize=authorize_hub)
    resources = ResourceService(
        storage,
        skill_hub,
        mcp_hub,
        NacosHubManagement(client),
        settings.workspace_root,
        policies=policies,
    )
    services["preview"] = DocumentPreviewService()
    services["file_changes"] = FileChangeService(storage, settings.workspace_root)
    services["resources"] = resources
    services["tasks"] = TaskService(
        storage, settings.workspace_root, services["models"], config
    )
    bus.coordinator.loader, bus.coordinator.models = loader, services["models"]
    bus.coordinator.packages = services["packages"]
    workspace = EgisLocalWorkspaceManager(settings.workspace_root, resources)
    factories = AgentFactories(
        storage, loader, settings.workspace_root, resources, config
    )
    app = create_app(
        storage=storage,
        message_bus=bus,
        workspace_manager=workspace,
        skill_hubs=[skill_hub],
        mcp_hubs=[mcp_hub],
        extra_agent_tools=factories.tools,
        extra_agent_middlewares=factories.middlewares,
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
    app.state.egis_loader, app.state.egis_bus = loader, bus
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
            user = await services["users"].get(body.user_id)
        except AgentKitError:
            raise HTTPException(401, "用户名或密码错误") from None
        return {
            "access_token": identity.issue(user.user_id, user.username),
            "token_type": "bearer",
            "expires_in": 3600,
        }

    @app.get("/health/ready", tags=["health"])
    async def ready():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
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
        try:
            await config.start()
            # Load configured immutable packages before native Dispatcher can
            # consume old durable wakeups during its startup drain.
            await services["packages"].restore_loaded()
            async with native_lifespan(application):
                yield
        finally:
            if factories.memory:
                await factories.memory.close()
            await config.close()
            await client.close()
            if owns_engine:
                await engine.dispose()

    app.router.lifespan_context = lifespan
    return app
