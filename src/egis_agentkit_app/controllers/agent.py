"""个人助理和专家定义。"""

from typing import Annotated

from egis_agentkit.service.agent._query import CATALOG_TYPES
from egis_agentkit.storage.model import AgentType, Definition, ViewType
from fastapi import APIRouter, Depends, Query, Request, Response

from ..schema import AgentWrite
from ..security import current_user
from .dependencies import services
from .responses import saved_definition

router = APIRouter()


@router.get("/assistant")
async def assistant(request: Request, user=Depends(current_user)):
    row = await services(request).personal_definition.build(user)
    return {
        **row,
        "resource_version": str(row["config_version"]),
        "resource_view_type": "private",
        "is_usable": True,
        "is_editable": True,
    }


@router.get("/agents")
async def list_agents(
    request: Request,
    types: Annotated[list[AgentType] | None, Query(alias="type")] = None,
    cursor: str | None = None,
    limit: int | None = None,
    user=Depends(current_user),
):
    return await services(request).agent_query.list(
        user, types=types or CATALOG_TYPES, cursor=cursor, limit=limit
    )


@router.get("/agents/{identifier}")
async def get_agent(
    identifier: str,
    request: Request,
    view: ViewType = "private",
    resource_version: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    user=Depends(current_user),
):
    """读取用户在指定视图下可见的专家发布版本。"""
    return await services(request).agent_query.read(
        user, identifier, view, version=resource_version
    )


@router.get("/agents/{identifier}/versions")
async def agent_versions(
    identifier: str, request: Request, user=Depends(current_user)
):
    """列出用户有权查看的专家发布版本。"""
    return {"items": await services(request).agent_query.versions(user, identifier)}


def agent_write(body, user, identifier=None):
    values = body.model_dump()
    values["owner_id"] = values["owner_id"] or user.user_id
    if identifier is not None:
        values["id"] = identifier
    return Definition(**values)


@router.post("/agents", status_code=201)
async def create_agent(body: AgentWrite, request: Request, user=Depends(current_user)):
    data = agent_write(body, user)
    kit = services(request)
    definition = (
        kit.remote_definition
        if data.agent_type == "remote"
        else kit.expert_definition
    )
    return saved_definition(await definition.build(user, data))


@router.put("/agents/{identifier}")
async def update_agent(
    identifier: str, body: AgentWrite, request: Request, user=Depends(current_user)
):
    data = agent_write(body, user, identifier)
    kit = services(request)
    definition = (
        kit.remote_definition
        if data.agent_type == "remote"
        else kit.expert_definition
    )
    return saved_definition(await definition.save(user, data))


@router.delete("/agents/{identifier}", status_code=204)
async def delete_definition(
    identifier: str, request: Request, user=Depends(current_user)
):
    kit = services(request)
    source = await kit.agent_query.read(user, identifier, view=None)
    definition = (
        kit.remote_definition if source["agent_type"] == "remote" else kit.expert_definition
    )
    await definition.disable(user, identifier)
    return Response(status_code=204)
