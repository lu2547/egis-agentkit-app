"""Aggregate the management HTTP controllers."""

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
)

router = APIRouter(prefix="/manager", tags=["manager"])

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
    router.include_router(controller.router)
