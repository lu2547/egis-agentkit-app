"""Request-scoped access to the Framework service container."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from egis_agentkit.bootstrap import AgentKitServices


def services(request: Request) -> AgentKitServices:
    return request.app.state.egis_services


async def current_user(request: Request):
    user = getattr(request.state, "egis_user", None)
    if user is None:
        raise HTTPException(401, "请先登录")
    return user


async def native_user_id(request: Request):
    return (await current_user(request)).user_id
