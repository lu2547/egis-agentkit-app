"""扩展原生聊天请求，显式区分普通消息和运行中引导。"""

from agentscope.app._router._schema import ChatRequest as NativeChatRequest
from agentscope.app._router._schema import ChatTriggerResponse as NativeChatResponse
from egis_agentkit.core.session._steering import ChatDelivery
from pydantic import ConfigDict


class ChatRequest(NativeChatRequest):
    model_config = ConfigDict(extra="forbid")
    delivery: ChatDelivery = ChatDelivery.MESSAGE


class ChatResponse(NativeChatResponse):
    message_ids: list[str] | None = None
