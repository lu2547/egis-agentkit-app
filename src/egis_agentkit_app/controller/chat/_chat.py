"""统一聊天入口，使用原生持久队列、回复引导和审批协议。"""

from agentscope.app._manager import ChatRunRegistry
from agentscope.app._router._chat import chat as native_chat
from agentscope.app._router._schema import ChatRequest as NativeChatRequest
from agentscope.app._service import ChatService
from agentscope.app.deps import (
    get_chat_run_registry,
    get_chat_service,
    get_message_bus,
    get_storage,
)
from agentscope.app.message_bus import MessageBus
from agentscope.message import Msg
from egis_agentkit.core.session._chat_input import prepare_chat_inputs
from egis_agentkit.errors import InvalidRequest
from egis_agentkit.service.session._message_rewrite import MessageRewriteService
from fastapi import APIRouter, Depends, Request

from ..base import current_user, services
from ._model import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    body: ChatRequest,
    request: Request,
    user=Depends(current_user),
    storage=Depends(get_storage),
    chat_service: ChatService = Depends(get_chat_service),
    chat_run_registry: ChatRunRegistry = Depends(get_chat_run_registry),
    message_bus: MessageBus = Depends(get_message_bus),
):
    """普通消息先排队；只有显式调用队列引导接口才注入当前回复。"""
    tasks = services(request).sessions
    if isinstance(body.input, (Msg, list)):
        body.input = prepare_chat_inputs(
            user,
            body.input,
            tasks.get_steering_settings(),
        )
    if body.replace_message_id:
        if (
            not isinstance(body.input, list)
            or len(body.input) != 1
            or body.input[0].id != body.replace_message_id
        ):
            raise InvalidRequest("编辑重发必须包含一条与原消息 ID 一致的用户消息")
        body.input[0].metadata.pop("agentkit_delivery", None)

    async def submit():
        return await native_chat(
            request=NativeChatRequest.model_validate(
                body.model_dump(exclude={"replace_message_id"})
            ),
            user_id=user.user_id,
            storage=storage,
            chat_service=chat_service,
            chat_run_registry=chat_run_registry,
            message_bus=message_bus,
        )

    async with MessageRewriteService.input_guard(message_bus, body.session_id):
        if body.replace_message_id:
            async with tasks.rewrite_message(
                user,
                body.session_id,
                body.agent_id,
                body.replace_message_id,
                message_bus,
            ) as receipt:
                response = await submit()
                receipt.queue_item_id = response.queue_item_id
                receipt.replacement = body.input[0]
            return response
        return await submit()
