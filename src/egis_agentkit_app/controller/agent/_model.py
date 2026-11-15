"""agent 领域的 HTTP 请求与响应模型。"""

from typing import Any, Literal

from pydantic import Field

from ..base import Request


class AgentWrite(Request):
    agent_type: Literal["expert", "remote"] = "expert"
    agent_name: str
    agent_display_name: str
    payload: dict[str, Any]
    owner_version: int = Field(default=1, ge=1)
    owner_type: Literal["user", "system"] = "user"
    owner_id: str | None = None
