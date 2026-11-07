from datetime import datetime
from typing import Literal

from agentscope.permission import PermissionMode
from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentWrite(Request):
    agent_name: str
    agent_display_name: str
    payload: dict
    config_version: int = Field(default=1, ge=1)
    owner_type: Literal["user", "system"] = "user"
    owner_id: str | None = None


class TeamWrite(Request):
    team_name: str
    team_display_name: str
    orchestrator_config: dict
    members: list[dict]
    payload: dict = Field(default_factory=dict)
    config_version: int = Field(default=1, ge=1)
    owner_type: Literal["user", "system"] = "user"
    owner_id: str | None = None


class TaskWrite(Request):
    project_id: str | None = Field(default=None, max_length=64)
    definition_id: str
    resource_view_type: Literal["private", "system", "shared"]
    name: str | None = Field(default=None, max_length=200)
    model_key: str | None = None
    permission_mode: PermissionMode = PermissionMode.DEFAULT


class CollaboratorRef(Request):
    definition_id: str = Field(min_length=1, max_length=128)
    resource_view_type: Literal["private", "system", "shared"]


class TaskCollaboratorsWrite(Request):
    request_id: str = Field(min_length=1, max_length=128)
    experts: list[CollaboratorRef] = Field(max_length=16)


class TaskNameWrite(Request):
    name: str = Field(min_length=1, max_length=80)


class ProjectWrite(Request):
    project_name: str = Field(min_length=1, max_length=128)


class TaskSettingsWrite(Request):
    permission_mode: PermissionMode | None = None
    model_key: str | None = None


class ShareWrite(Request):
    resource_type: Literal["agent", "team", "skill", "mcp"]
    resource_id: str
    resource_version: str | None = None


class DecisionWrite(Request):
    is_approved: bool
    reason: str = Field(default="", max_length=2000)


class LoginWrite(Request):
    user_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class InstallWrite(Request):
    is_enabled: bool


class DeliveryWrite(Request):
    path: str = Field(min_length=1, max_length=2048)


class PreferencesWrite(Request):
    agent_md: str = Field(max_length=64000)
    soul_md: str = Field(max_length=64000)
    user_md: str = Field(max_length=64000)


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
