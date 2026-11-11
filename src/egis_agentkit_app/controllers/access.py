"""精确发布版本的直接授权与共享审批接口。"""

from egis_agentkit.storage.model import Grant
from fastapi import APIRouter, Depends, Request, Response

from ..schema import DecisionWrite, GrantWrite, ShareWrite
from ..security import current_user
from .dependencies import services

router = APIRouter()


@router.post("/share-requests", status_code=201)
async def request_share(body: ShareWrite, request: Request, user=Depends(current_user)):
    """提交首次共享、追加受众或升级当前共享版本。"""
    return await services(request).sharing.submit(
        user,
        body.resource_type,
        body.resource_id,
        target=body.target,
    )


@router.get("/share-recipients")
async def share_recipients(request: Request, user=Depends(current_user)):
    return {"items": await services(request).sharing.recipients(user)}


@router.get("/share-requests")
async def list_shares(request: Request, user=Depends(current_user)):
    return {"items": await services(request).sharing.list(user)}


@router.get("/admin/grants")
async def grants(request: Request, user=Depends(current_user)):
    return {"items": await services(request).grants.list_grants(user)}


@router.get("/admin/grant-resources")
async def grant_resources(request: Request, user=Depends(current_user)):
    return {"items": await services(request).grants.grantable_resources(user)}


@router.post("/admin/grants")
async def grant(body: GrantWrite, request: Request, user=Depends(current_user)):
    """由管理员直接授权；审批授权由共享服务创建。"""
    return await services(request).grants.grant(user, Grant(**body.model_dump()))


@router.delete("/admin/grants/{identifier}", status_code=204)
async def revoke_grant(identifier: str, request: Request, user=Depends(current_user)):
    await services(request).grants.revoke(user, identifier)
    return Response(status_code=204)


@router.get("/admin/share-reviews")
async def share_reviews(request: Request, user=Depends(current_user)):
    return {"items": await services(request).sharing.list(user, admin=True)}


@router.post("/admin/share-reviews/{identifier}/decision")
async def decide_share(
    identifier: str, body: DecisionWrite, request: Request, user=Depends(current_user)
):
    return await services(request).sharing.decide(
        user, identifier, body.is_approved, body.reason
    )
