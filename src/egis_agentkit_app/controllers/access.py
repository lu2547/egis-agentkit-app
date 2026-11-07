"""Grants and sharing review HTTP endpoints."""

from egis_agentkit.errors import Forbidden
from egis_agentkit.models import Grant
from fastapi import APIRouter, Depends, Request, Response

from ..schema import DecisionWrite, ShareWrite
from ..security import current_user
from .dependencies import services

router = APIRouter()


@router.post("/share-requests", status_code=201)
async def request_share(body: ShareWrite, request: Request, user=Depends(current_user)):
    return await services(request).sharing.submit(
        user, body.resource_type, body.resource_id, body.resource_version
    )


@router.get("/share-requests")
async def list_shares(request: Request, user=Depends(current_user)):
    return {"items": await services(request).sharing.list(user)}


@router.get("/admin/grants")
async def grants(request: Request, user=Depends(current_user)):
    return {"items": await services(request).permissions.list_grants(user)}


@router.post("/admin/grants")
async def grant(body: Grant, request: Request, user=Depends(current_user)):
    if body.grant_source_type != "manual":
        raise Forbidden("共享授权只能由审核用例创建")
    return await services(request).permissions.grant(user, body)


@router.delete("/admin/grants/{identifier}", status_code=204)
async def revoke_grant(identifier: str, request: Request, user=Depends(current_user)):
    await services(request).permissions.revoke(user, identifier)
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
