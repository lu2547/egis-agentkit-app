"""resource 领域的 HTTP 请求与响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from ..base import Request


class InstallWrite(Request):
    is_enabled: bool


class SkillImportJob(BaseModel):
    job_id: str
    filename: str
    category: str
    avatar: str
    status: Literal["queued", "running", "succeeded", "failed"]
    stage: str
    progress: int
    attempts: int
    resource_id: str
    resource_version: str | None = None
    error: str | None = None
    result: dict | None = None
    created_at: datetime
    updated_at: datetime


class SkillImportList(BaseModel):
    items: list[SkillImportJob]


class ConnectorKeyWrite(BaseModel):
    key: SecretStr


class ConnectorCallbackWrite(BaseModel):
    state: str = Field(min_length=1, max_length=256)
    code: SecretStr | None = None
