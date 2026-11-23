"""Aggregate the management HTTP controllers."""

from fastapi import APIRouter

from ..controller import (
    access,
    agent,
    composer,
    model,
    project,
    resource,
    schedule,
    session,
    team,
    user,
)
from ..controller.chat import router as chat_router
from ..controller.health import router as health_router
from ..controller.remote_agent import router as remote_agent_router
from ..controller.resource._external_skill_import import (
    router as external_skill_import_router,
)

manager_router = APIRouter(prefix="/manager", tags=["manager"])

for controller in (
    agent,
    team,
    access,
    model,
    session,
    project,
    resource,
    schedule,
    user,
    composer,
):
    manager_router.include_router(controller.router)


router = APIRouter()
for component in (
    manager_router,
    external_skill_import_router,
    health_router,
    remote_agent_router,
    chat_router,
):
    router.include_router(component)
