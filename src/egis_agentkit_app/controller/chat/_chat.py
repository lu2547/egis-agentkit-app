"""分派统一 /chat/ 请求，普通消息和审批继续使用原生实现。"""

from agentscope.app._manager import ChatRunRegistry
from agentscope.app._router._chat import chat as native_chat
from agentscope.app._router._schema import ChatRequest as NativeChatRequest
from agentscope.app._service import ChatService
from agentscope.app.deps import get_chat_run_registry, get_chat_service, get_message_bus
from agentscope.app.message_bus import MessageBus
from egis_agentkit.core.session._steering import ChatDelivery
from fastapi import APIRouter, Depends, Request

from ..base import current_user, services
from ._model import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    request: Request,
    user=Depends(current_user),
    chat_service: ChatService = Depends(get_chat_service),
    chat_run_registry: ChatRunRegistry = Depends(get_chat_run_registry),
    message_bus: MessageBus = Depends(get_message_bus),
):
    """引导进入 Inbox，其余请求保留原生执行及重复提交保护。"""
    if body.delivery == ChatDelivery.STEER:
        return await services(request).sessions.steering.submit(
            user, body.session_id, body.agent_id, body.input, message_bus
        )
    return await native_chat(
        request=NativeChatRequest.model_validate(body.model_dump(exclude={"delivery"})),
        user_id=user.user_id,
        chat_service=chat_service,
        chat_run_registry=chat_run_registry,
        message_bus=message_bus,
    )
