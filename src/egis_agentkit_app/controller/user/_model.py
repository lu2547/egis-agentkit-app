"""user 领域的 HTTP 请求与响应模型。"""

from pydantic import Field

from ..base import Request


class LoginWrite(Request):
    user_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class PreferencesWrite(Request):
    agent_md: str
    soul_md: str
    user_md: str
