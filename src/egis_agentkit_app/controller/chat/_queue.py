"""只开放经过企业身份、会话和资源鉴权的原生队列操作。"""

from agentscope.app._router import _chat as native
from agentscope.app._router._schema import (
    ChatQueueResponse,
    ReorderChatQueueRequest,
    SteerChatQueueItemRequest,
    UpdateChatQueueItemRequest,
)
from agentscope.app.deps import get_message_bus, get_storage
from egis_agentkit.core.session._chat_input import prepare_chat_inputs
from fastapi import APIRouter, Depends, Request

from ..base import current_user, services

router = APIRouter()


def queue_context(
    user=Depends(current_user),
    storage=Depends(get_storage),
    bus=Depends(get_message_bus),
):
    return {"user_id": user.user_id, "storage": storage, "message_bus": bus}


@router.get("/queue", response_model=ChatQueueResponse)
async def get_queue(agent_id: str, session_id: str, context=Depends(queue_context)):
    return await native.get_chat_queue(
        agent_id=agent_id, session_id=session_id, **context
    )


@router.patch("/queue/order", response_model=ChatQueueResponse)
async def reorder_queue(body: ReorderChatQueueRequest, context=Depends(queue_context)):
    return await native.reorder_chat_queue(request=body, **context)


@router.post("/queue/{item_id}/steer", response_model=ChatQueueResponse)
async def steer_queue(
    item_id: str, body: SteerChatQueueItemRequest, context=Depends(queue_context)
):
    return await native.steer_chat_queue_item(item_id=item_id, request=body, **context)


@router.patch("/queue/{item_id}", response_model=ChatQueueResponse)
async def update_queue(
    item_id: str,
    body: UpdateChatQueueItemRequest,
    request: Request,
    user=Depends(current_user),
    context=Depends(queue_context),
):
    body.input = prepare_chat_inputs(
        user, body.input, services(request).sessions.get_steering_settings()
    )
    return await native.update_chat_queue_item(item_id=item_id, request=body, **context)


@router.delete("/queue/{item_id}", response_model=ChatQueueResponse)
async def delete_queue(
    item_id: str, agent_id: str, session_id: str, context=Depends(queue_context)
):
    return await native.delete_chat_queue_item(
        item_id=item_id, agent_id=agent_id, session_id=session_id, **context
    )
