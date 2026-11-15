"""Composer discovery transport; policy and paging live in framework services."""

from typing import Literal

from fastapi import APIRouter, Depends, Request

from ..base import current_user, services

router = APIRouter()


@router.get("/composer/options")
async def composer_options(
    request: Request,
    category: Literal["context", "experts", "skills", "commands"],
    query: str = "",
    cursor: str | None = None,
    limit: int | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    user=Depends(current_user),
):
    return await services(request).composer.options(
        user,
        category,
        query=query,
        cursor=cursor,
        limit=limit,
        session_id=session_id,
        project_id=project_id,
    )
