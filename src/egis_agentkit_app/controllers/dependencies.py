"""Request-scoped access to the Framework service container."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from egis_agentkit.bootstrap import AgentKitServices


def services(request: Request) -> AgentKitServices:
    return request.app.state.egis_services
