"""resource 领域的 HTTP 请求与响应模型。"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr

from ..base import Request


class InstallWrite(Request):
    is_enabled: bool


class SkillImportJob(BaseModel):
    job_id: str
    filename: str
    category: str
    avatar: str
    status: Literal[
        "queued", "running", "pending_approval", "succeeded", "failed", "rejected"
    ]
    stage: str
    progress: int
    attempts: int
    resource_id: str
    resource_version: str | None = None
    error: str | None = None
    result: dict | None = None
    owner_type: Literal["user", "system"]
    uploader_type: Literal["user", "admin", "virtual"]
    uploaded_by: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class SkillImportList(BaseModel):
    items: list[SkillImportJob]


class SkillImportDecision(Request):
    job_ids: list[Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]]
    approved: bool
    reason: str = Field(default="", max_length=1000)


class ConnectorKeyWrite(BaseModel):
    key: SecretStr


class ConnectorCallbackWrite(BaseModel):
    state: str = Field(min_length=1, max_length=256)
    code: SecretStr | None = None
