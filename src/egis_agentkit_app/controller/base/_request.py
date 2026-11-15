"""HTTP 请求模型默认拒绝未知字段。"""

from pydantic import BaseModel, ConfigDict


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
