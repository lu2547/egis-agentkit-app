"""Team definition HTTP endpoints."""

from fastapi import APIRouter, Depends, Request

from ..schema import TeamWrite
from ..security import current_user
from .dependencies import services
from .responses import saved_definition

router = APIRouter()


@router.get("/teams")
async def list_teams(request: Request, user=Depends(current_user)):
    return {"items": await services(request).agents.list(user, definition_type="team")}


@router.get("/teams/{identifier}")
async def get_team(
    identifier: str, request: Request, view: str = "private", user=Depends(current_user)
):
    return await services(request).definition_details.get(user, identifier, view, "team")


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
