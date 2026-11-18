"""user 领域的 HTTP 请求与响应模型。"""

from pydantic import BaseModel, Field

from ..base import Request


class PreferencesWrite(Request):
    agent_md: str
    soul_md: str
    user_md: str


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
