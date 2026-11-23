"""企业入口保留原生聊天协议，拒绝未声明的请求字段。"""

from agentscope.app._router._schema import ChatRequest as NativeChatRequest
from agentscope.app._router._schema import ChatTriggerResponse as NativeChatResponse
from pydantic import ConfigDict, Field


class ChatRequest(NativeChatRequest):
    model_config = ConfigDict(extra="forbid")
    replace_message_id: str | None = Field(default=None, min_length=1, max_length=255)


class ChatResponse(NativeChatResponse):
    pass
