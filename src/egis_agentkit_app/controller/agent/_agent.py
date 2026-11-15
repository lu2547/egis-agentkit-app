"""个人助理和专家定义。"""

from __future__ import annotations

from typing import Annotated, Any

from egis_agentkit.service.agent._agent_manager import CATALOG_TYPES
from egis_agentkit.storage.model import (
    AgentDefinition,
    AgentType,
    AgentUpdate,
    User,
    ViewType,
)
from fastapi import APIRouter, Depends, Path, Query, Request, Response

from ..base import current_user, saved_definition, services
from ._model import AgentWrite

router = APIRouter()


@router.get("/assistant")
async def get_personal_definition(
    request: Request, user: User = Depends(current_user)
) -> dict[str, Any]:
    row = await services(request).personal.get_or_add_definition(user)
    return {
        **row,
        "resource_version": row["resource_version"],
        "resource_view_type": "private",
        "is_usable": True,
        "is_editable": True,
    }


@router.get("/agents")
async def page_agents(
    request: Request,
    types: Annotated[list[AgentType] | None, Query(alias="type")] = None,
    cursor: str | None = None,
    limit: int | None = None,
    query: str = "",
    user: User = Depends(current_user),
) -> dict[str, Any]:
    return await services(request).agents.page_definitions(
        user, types=types or CATALOG_TYPES, cursor=cursor, limit=limit, query=query
    )


@router.get("/agents/{identifier}")
async def get_agent(
    definition_id: Annotated[str, Path(alias="identifier")],
    request: Request,
    view: ViewType = "private",
    resource_version: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """读取用户在指定视图下可见的专家发布版本。"""
    return await services(request).agents.get_definition(
        user, definition_id, view, version=resource_version
    )


@router.get("/agents/{identifier}/versions")
async def list_agent_versions(
    definition_id: Annotated[str, Path(alias="identifier")],
    request: Request,
    user: User = Depends(current_user),
) -> dict[str, list[dict[str, Any]]]:
    """列出用户有权查看的专家发布版本。"""
    return {"items": await services(request).agents.list_versions(user, definition_id)}


def build_agent_definition(body: AgentWrite, user: User) -> AgentDefinition:
    """将创建请求转换为专家定义，并补齐当前用户归属。"""
    definition_fields = body.model_dump()
    definition_fields["owner_id"] = definition_fields["owner_id"] or user.user_id
    return AgentDefinition(**definition_fields)


@router.post("/agents", status_code=201)
async def add_agent(
    body: AgentWrite, request: Request, user: User = Depends(current_user)
) -> dict[str, Any]:
    definition = build_agent_definition(body, user)
    kit = services(request)
    return saved_definition(await kit.agents.add_definition(user, definition))


@router.put("/agents/{identifier}")
async def update_agent(
    definition_id: Annotated[str, Path(alias="identifier")],
    body: AgentUpdate,
    request: Request,
    user: User = Depends(current_user),
) -> dict[str, Any]:
    kit = services(request)
    return saved_definition(
        await kit.agents.update_definition(user, definition_id, body)
    )


@router.delete("/agents/{identifier}", status_code=204)
async def delete_definition(
    definition_id: Annotated[str, Path(alias="identifier")],
    request: Request,
    user: User = Depends(current_user),
) -> Response:
    kit = services(request)
    await kit.agents.delete_definition(user, definition_id)
    return Response(status_code=204)
