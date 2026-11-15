"""Aggregate the management HTTP controllers."""

from fastapi import APIRouter

from ..controller import (
    access,
    agent,
    composer,
    model,
    project,
    resource,
    session,
    team,
    user,
)
from ..controller.health import router as health_router
from ..controller.remote_agent import router as remote_agent_router
from ..controller.user import identity_router

manager_router = APIRouter(prefix="/manager", tags=["manager"])

for controller in (
    agent,
    team,
    access,
    model,
    session,
    project,
    resource,
    user,
    composer,
):
    manager_router.include_router(controller.router)


router = APIRouter()
for component in (manager_router, identity_router, health_router, remote_agent_router):
    router.include_router(component)
