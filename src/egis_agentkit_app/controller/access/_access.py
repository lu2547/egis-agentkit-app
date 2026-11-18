"""精确发布版本的直接授权与共享审批接口。"""

import logging
from collections.abc import Awaitable, Callable, Iterable

from egis_agentkit.errors import AgentKitError, Forbidden
from egis_agentkit.service._user import require_admin
from egis_agentkit.storage.model import Grant
from fastapi import APIRouter, Depends, Request, Response

from ..base import current_user, services
from ._model import (
    BatchFailure,
    BatchResponse,
    BatchResult,
    BatchSuccess,
    DecisionWrite,
    GrantWrite,
    ShareDecisionBatchWrite,
    ShareWrite,
    SkillGrantBatchWrite,
    SkillShareBatchWrite,
)

router = APIRouter()
log = logging.getLogger(__name__)


async def _apply_batch(
    identifiers: Iterable[str], operation: Callable[[str], Awaitable[object]]
) -> BatchResponse:
    """独立提交每一项，按输入顺序返回结果。"""
    items: list[BatchResult] = []
    for identifier in identifiers:
        try:
            await operation(identifier)
        except AgentKitError as error:
            items.append(
                BatchFailure(
                    id=identifier, status_code=error.status_code, detail=str(error)
                )
            )
        except Exception:
            log.exception("Batch access operation failed for %r", identifier)
            items.append(
                BatchFailure(id=identifier, status_code=500, detail="操作失败，请重试")
            )
        else:
            items.append(BatchSuccess(id=identifier))
    return BatchResponse(items=items)


@router.post("/share-requests", status_code=201)
async def request_share(body: ShareWrite, request: Request, user=Depends(current_user)):
    """提交首次共享、追加受众或升级当前共享版本。"""
    return await services(request).sharing.submit(
        user,
        body.resource_type,
        body.resource_id,
        target=body.target,
    )


@router.post("/share-requests/batch")
async def request_skill_shares(
    body: SkillShareBatchWrite, request: Request, user=Depends(current_user)
) -> BatchResponse:
    """为多个个人技能提交同一接收对象的共享申请。"""
    if not user.is_enabled:
        raise Forbidden()
    sharing = services(request).sharing
    return await _apply_batch(
        body.resource_ids,
        lambda identifier: sharing.submit(
            user, "skill", identifier, target=body.target
        ),
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


@router.post("/admin/grants/batch")
async def grant_system_skills(
    body: SkillGrantBatchWrite, request: Request, user=Depends(current_user)
) -> BatchResponse:
    """由管理员将多个系统技能授权给同一对象。"""
    require_admin(user)
    grants = services(request).grants
    owners = {item.resource_id: item.resource_owner_id for item in body.resources}

    async def grant_skill(identifier: str):
        await grants.grant(
            user,
            Grant(
                **body.target.model_dump(),
                resource_type="skill",
                resource_id=identifier,
                resource_view_type="system",
                resource_owner_type="system",
                resource_owner_id=owners[identifier],
            ),
        )

    return await _apply_batch(owners, grant_skill)


@router.delete("/admin/grants/{identifier}", status_code=204)
async def revoke_grant(identifier: str, request: Request, user=Depends(current_user)):
    await services(request).grants.revoke(user, identifier)
    return Response(status_code=204)


@router.get("/admin/share-reviews")
async def share_reviews(request: Request, user=Depends(current_user)):
    return {"items": await services(request).sharing.list(user, admin=True)}


@router.post("/admin/share-reviews/batch/decision")
async def decide_shares(
    body: ShareDecisionBatchWrite, request: Request, user=Depends(current_user)
) -> BatchResponse:
    require_admin(user)
    sharing = services(request).sharing
    return await _apply_batch(
        body.review_ids,
        lambda identifier: sharing.decide(
            user, identifier, body.is_approved, body.reason
        ),
    )


@router.post("/admin/share-reviews/{identifier}/decision")
async def decide_share(
    identifier: str, body: DecisionWrite, request: Request, user=Depends(current_user)
):
    return await services(request).sharing.decide(
        user, identifier, body.is_approved, body.reason
    )
