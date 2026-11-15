"""team 领域的 HTTP 请求与响应模型。"""

from typing import Literal

from egis_agentkit.storage.model import DefinitionRef
from pydantic import Field

from ..base import Request


class TeamWrite(Request):
    team_name: str
    team_display_name: str
    orchestrator_config: dict
    members: list[DefinitionRef] = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    owner_version: int = Field(default=1, ge=1)
    owner_type: Literal["user", "system"] = "user"
    owner_id: str | None = None
