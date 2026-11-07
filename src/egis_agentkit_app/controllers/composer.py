"""Composer discovery transport; policy and paging live in framework services."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from ..security import current_user
from .dependencies import services

router = APIRouter()


@router.get("/composer/options")
async def composer_options(
    request: Request,
    category: Literal["context", "experts", "skills", "commands"],
    query: str = Query("", max_length=500),
    cursor: str | None = Query(None, max_length=2048),
    limit: int = Query(10, ge=1, le=10),
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
