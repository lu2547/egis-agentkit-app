"""access 领域的 HTTP 请求与响应模型。"""

from typing import Literal

from egis_agentkit.storage.model import ShareTarget
from pydantic import Field

from ..base import Request


class ShareWrite(Request):
    """没有接收对象时，为当前受众提交一次版本升级。"""

    resource_type: Literal["agent", "team", "skill", "mcp"]
    resource_id: str = Field(min_length=1, max_length=128)
    target: ShareTarget | None = None


class GrantWrite(ShareTarget):
    """直接授权绑定资源身份、视图及受众。"""

    resource_type: Literal["agent", "team", "skill", "mcp"]
    resource_id: str = Field(min_length=1, max_length=128)
    resource_view_type: Literal["system", "shared"]
    resource_owner_type: Literal["user", "system"]
    resource_owner_id: str


class DecisionWrite(Request):
    is_approved: bool
    reason: str = Field(default="", max_length=2000)
