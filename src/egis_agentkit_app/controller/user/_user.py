"""Identity, user administration and preferences HTTP endpoints."""

from egis_agentkit.errors import Forbidden
from egis_agentkit.storage.model import Group, User
from fastapi import APIRouter, Depends, Request

from ..base import current_user, services
from ._model import PreferencesWrite

router = APIRouter()


@router.get("/me")
async def me(user=Depends(current_user)):
    return user


@router.get("/preferences")
async def preferences(request: Request, user=Depends(current_user)):
    return await services(request).personal.get_preferences(user)


@router.put("/preferences")
async def save_preferences(
    body: PreferencesWrite, request: Request, user=Depends(current_user)
):
    return await services(request).personal.save_preferences(user, body.model_dump())


@router.get("/admin/users")
async def users(request: Request, user=Depends(current_user)):
    return {"items": await services(request).users.list_users(user)}


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str, body: User, request: Request, user=Depends(current_user)
):
    if user_id != body.user_id:
        raise Forbidden("用户标识不可修改")
    return await services(request).users.update_user(user, body)


@router.get("/admin/groups")
async def groups(request: Request, user=Depends(current_user)):
    return {"items": await services(request).users.list_groups(user)}


@router.post("/admin/groups")
@router.put("/admin/groups/{group_id}")
async def save_group(
    body: Group,
    request: Request,
    group_id: str | None = None,
    user=Depends(current_user),
):
    if group_id is not None and group_id != body.group_id:
        raise Forbidden("分组标识不可修改")
    return await services(request).users.save_group(user, body)
