"""Identity, user administration and preferences HTTP endpoints."""

from egis_agentkit.errors import Forbidden
from egis_agentkit.storage.model import Group, User
from fastapi import APIRouter, Depends, Request, Response

from ..base import current_user, services
from ._model import (
    PreferencesWrite,
    VirtualUserAccount,
    VirtualUserCredential,
    VirtualUserList,
    VirtualUserStatus,
    VirtualUserWrite,
)

router = APIRouter()


@router.get("/admin/virtual-users", response_model=VirtualUserList)
async def virtual_users(request: Request, user=Depends(current_user)):
    accounts = services(request).virtual_users
    return {"items": await accounts.list(user)}


@router.post(
    "/admin/virtual-users", status_code=201, response_model=VirtualUserCredential
)
async def create_virtual_user(
    body: VirtualUserWrite,
    request: Request,
    response: Response,
    user=Depends(current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return await services(request).virtual_users.create(user, body.username)


@router.patch("/admin/virtual-users/{user_id}", response_model=VirtualUserAccount)
async def set_virtual_user_status(
    user_id: str, body: VirtualUserStatus, request: Request, user=Depends(current_user)
):
    accounts = services(request).virtual_users
    return await accounts.set_enabled(user, user_id, body.is_enabled)


@router.post(
    "/admin/virtual-users/{user_id}/rotate", response_model=VirtualUserCredential
)
async def rotate_virtual_user(
    user_id: str, request: Request, response: Response, user=Depends(current_user)
):
    response.headers["Cache-Control"] = "no-store"
    return await services(request).virtual_users.rotate(user, user_id)


@router.get("/me")
async def me(request: Request, user=Depends(current_user)):
    """在工作台完成登录前确保该用户已有默认项目。"""
    await services(request).projects.default(user)
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
