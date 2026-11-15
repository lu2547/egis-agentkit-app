"""提供受当前用户和会话保护的知识库原件入口，不代替 Java 的文档鉴权。"""

from egis_agentkit.errors import AgentKitError
from fastapi import APIRouter, Depends, Request

from ..base import current_user, services

router = APIRouter()


@router.get("/knowledge/bases")
async def list_knowledge_bases(request: Request, user=Depends(current_user)):
    """仅展示当前用户获准访问的库，复用 Java 目录，不复制知识库管理。"""
    manager = services(request).knowledge
    if manager is None:
        return {"enabled": False, "label": "企业知识库", "items": []}
    bases = await manager.list_knowledge_bases(user.user_id)
    return {
        "enabled": True,
        "label": manager.settings_label,
        "items": [base.model_dump() for base in bases],
    }


@router.get(
    "/tasks/{sid}/replies/{reply_id}/knowledge/{call_id}/{source_index}/document"
)
async def get_knowledge_document(
    sid: str,
    reply_id: str,
    call_id: str,
    source_index: int,
    request: Request,
    user=Depends(current_user),
):
    manager = services(request).knowledge
    if manager is None:
        raise AgentKitError("知识库接入尚未启用", 503)
    return await manager.document_resolver(
        user.user_id, sid, reply_id, call_id, source_index
    )
