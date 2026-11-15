"""专家团定义和发布版本接口。"""

from typing import Annotated

from egis_agentkit.storage.model import ViewType
from fastapi import APIRouter, Depends, Query, Request, Response

from ..base import current_user, saved_definition, services
from ._model import TeamWrite

router = APIRouter()


@router.get("/teams")
async def list_teams(request: Request, user=Depends(current_user)):
    return {"items": await services(request).teams.list(user)}


@router.get("/teams/{identifier}")
async def get_team(
    identifier: str,
    request: Request,
    view: ViewType = "private",
    resource_version: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    user=Depends(current_user),
):
    """读取指定的专家团版本，包括该版本固定的成员引用。"""
    return await services(request).teams.read(
        user, identifier, view, version=resource_version
    )


@router.get("/teams/{identifier}/versions")
async def team_versions(identifier: str, request: Request, user=Depends(current_user)):
    """列出用户有权查看的专家团发布版本。"""
    return {"items": await services(request).teams.versions(user, identifier)}


async def save_team(request, user, body, identifier=None):
    values = body.model_dump()
    values["owner_id"] = values["owner_id"] or user.user_id
    if identifier:
        values["id"] = identifier
    return saved_definition(await services(request).teams.save(user, values))


@router.post("/teams", status_code=201)
async def create_team(body: TeamWrite, request: Request, user=Depends(current_user)):
    return await save_team(request, user, body)


@router.put("/teams/{identifier}")
async def update_team(
    identifier: str, body: TeamWrite, request: Request, user=Depends(current_user)
):
    return await save_team(request, user, body, identifier)


@router.delete("/teams/{identifier}", status_code=204)
async def delete_definition(
    identifier: str, request: Request, user=Depends(current_user)
):
    await services(request).teams.delete(user, identifier)
    return Response(status_code=204)
