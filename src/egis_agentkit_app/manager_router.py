"""Compatibility entry point aggregating management HTTP controllers."""

from fastapi import APIRouter

from .controllers import (
    access,
    agent,
    composer,
    model,
    project,
    resource,
    session,
    team,
    user,
    workspace,
)

router = APIRouter(prefix="/manager", tags=["manager"])

for controller in (
    agent,
    team,
    access,
    model,
    session,
    project,
    workspace,
    resource,
    user,
    composer,
):
    router.include_router(controller.router)
