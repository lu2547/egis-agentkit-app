"""project 领域的 HTTP 请求与响应模型。"""

from typing import Literal

from pydantic import Field

from ..base import Request


class ProjectWrite(Request):
    project_name: str = Field(min_length=1, max_length=128)


class DeliveryWrite(Request):
    path: str = Field(min_length=1, max_length=2048)


class PresentationSlideWrite(Request):
    operation_type: Literal["add", "duplicate", "remove", "move"]
    slide_id: str = Field(min_length=1, max_length=128)
    target_index: int | None = Field(default=None, ge=1)
