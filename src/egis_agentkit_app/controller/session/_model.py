"""session 领域的 HTTP 请求与响应模型。"""

from typing import Literal

from agentscope.permission import PermissionMode
from pydantic import Field

from ..base import Request


class TaskWrite(Request):
    project_id: str | None = Field(default=None, max_length=64)
    definition_id: str
    resource_view_type: Literal["private", "system", "shared"]
    resource_version: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = None
    model_key: str | None = None
    permission_mode: PermissionMode | None = None


class CollaboratorRef(Request):
    definition_id: str = Field(min_length=1, max_length=128)
    resource_view_type: Literal["private", "system", "shared"]
    resource_version: str | None = Field(default=None, min_length=1, max_length=128)


class TaskCollaboratorsWrite(Request):
    request_id: str = Field(min_length=1)
    experts: list[CollaboratorRef]


class TaskNameWrite(Request):
    name: str = Field(min_length=1)


class ReplyFeedbackWrite(Request):
    comment: str = Field(min_length=1)


class TaskSettingsWrite(Request):
    permission_mode: PermissionMode | None = None
    model_key: str | None = None
