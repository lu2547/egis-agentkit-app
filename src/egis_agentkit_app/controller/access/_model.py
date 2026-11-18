"""access 领域的 HTTP 请求与响应模型。"""

from collections.abc import Iterable
from typing import Annotated, Literal

from egis_agentkit.storage.model import ShareTarget
from pydantic import Field, field_validator

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


MAX_SKILL_BATCH_SIZE = 50
ResourceId = Annotated[str, Field(min_length=1, max_length=128)]
ReviewId = Annotated[str, Field(min_length=1, max_length=64)]


def _require_distinct(identifiers: Iterable[str]) -> None:
    identifiers = list(identifiers)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("批量操作不能包含重复的标识")


class SkillShareBatchWrite(Request):
    resource_ids: list[ResourceId] = Field(
        min_length=1, max_length=MAX_SKILL_BATCH_SIZE
    )
    target: ShareTarget

    @field_validator("resource_ids")
    @classmethod
    def distinct_resources(cls, values: list[str]) -> list[str]:
        _require_distinct(values)
        return values


class ShareDecisionBatchWrite(DecisionWrite):
    review_ids: list[ReviewId] = Field(min_length=1, max_length=MAX_SKILL_BATCH_SIZE)

    @field_validator("review_ids")
    @classmethod
    def distinct_reviews(cls, values: list[str]) -> list[str]:
        _require_distinct(values)
        return values


class SkillGrantResource(Request):
    resource_id: ResourceId
    resource_owner_id: str = Field(min_length=1, max_length=128)


class SkillGrantBatchWrite(Request):
    resources: list[SkillGrantResource] = Field(
        min_length=1, max_length=MAX_SKILL_BATCH_SIZE
    )
    target: ShareTarget

    @field_validator("resources")
    @classmethod
    def distinct_resources(
        cls, values: list[SkillGrantResource]
    ) -> list[SkillGrantResource]:
        _require_distinct(value.resource_id for value in values)
        return values


class BatchSuccess(Request):
    id: str
    success: Literal[True] = True


class BatchFailure(Request):
    id: str
    success: Literal[False] = False
    status_code: int
    detail: str


BatchResult = Annotated[BatchSuccess | BatchFailure, Field(discriminator="success")]


class BatchResponse(Request):
    items: list[BatchResult]
