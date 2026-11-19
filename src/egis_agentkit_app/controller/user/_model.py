"""user 领域的 HTTP 请求与响应模型。"""

from typing import Annotated

from egis_agentkit.service._admin_page import AdminPageResult
from pydantic import BaseModel, Field, StringConstraints

from ..base import Request


class PreferencesWrite(Request):
    agent_md: str
    soul_md: str
    user_md: str


class GroupCreate(Request):
    group_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    is_enabled: bool = True


class VirtualUserWrite(Request):
    username: str = Field(min_length=1, max_length=128)


class VirtualUserStatus(Request):
    is_enabled: bool


class VirtualUserAccount(BaseModel):
    user_id: str
    username: str
    is_enabled: bool


class VirtualUserCredential(VirtualUserAccount):
    token: str


class VirtualUserList(BaseModel):
    items: list[VirtualUserAccount]


VirtualUserPage = AdminPageResult[VirtualUserAccount]
