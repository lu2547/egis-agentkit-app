"""Identity, user administration and preferences HTTP endpoints."""

from egis_agentkit.errors import Forbidden
from egis_agentkit.storage.model import Group, User
from fastapi import APIRouter, Depends, Request, Response

from ..base import current_user, services
from ..base._pagination import AdminPagination
from ._model import (
    GroupCreate,
    PreferencesWrite,
    VirtualUserAccount,
    VirtualUserCredential,
    VirtualUserList,
    VirtualUserPage,
    VirtualUserStatus,
    VirtualUserWrite,
)

router = APIRouter()


@router.get("/admin/virtual-users", response_model=VirtualUserPage | VirtualUserList)
async def virtual_users(
    request: Request, page: AdminPagination, user=Depends(current_user)
):
    accounts = services(request).virtual_users
    if page is not None:
        return await accounts.list_page(user, page)
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
async def users(
    request: Request,
    page: AdminPagination,
    user=Depends(current_user),
    group_id: str | None = None,
):
    service = services(request).users
    if page is not None:
        return await service.list_users_page(user, page, group_id=group_id)
    return {"items": await service.list_users(user)}


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str, body: User, request: Request, user=Depends(current_user)
):
    if user_id != body.user_id:
        raise Forbidden("用户标识不可修改")
    return await services(request).users.update_user(user, body)


@router.get("/admin/groups")
async def groups(
    request: Request,
    page: AdminPagination,
    include_members: bool = True,
    user=Depends(current_user),
):
    service = services(request).users
    if page is not None:
        return await service.list_groups_page(user, page)
    return {"items": await service.list_groups(user, include_members=include_members)}


@router.post("/admin/groups", status_code=201)
async def create_group(
    body: GroupCreate, request: Request, user=Depends(current_user)
):
    return await services(request).users.create_group(
        user, body.group_name, is_enabled=body.is_enabled
    )


@router.put("/admin/groups/{group_id}")
async def update_group(
    group_id: str, body: Group, request: Request, user=Depends(current_user)
):
    if group_id != body.group_id:
        raise Forbidden("分组标识不可修改")
    return await services(request).users.update_group(user, body)
