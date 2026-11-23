"""Expose schedules and their execution history to the signed-in owner."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from egis_agentkit.service.schedule._rules import (
    ScheduleSettings,
    ScheduleTiming,
    next_occurrence,
)
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..base import current_user, services

router = APIRouter()


class ScheduleToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ScheduleIds(BaseModel):
    ids: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        min_length=1, max_length=500
    )


class ArchiveRun(BaseModel):
    archived: bool


@router.get("/schedules")
async def list_schedules(request: Request, user=Depends(current_user)):
    return {"items": await services(request).schedules.list(user)}


@router.post("/schedules/preview")
async def preview_schedule(body: ScheduleTiming, _user=Depends(current_user)):
    return {"next_run_at": next_occurrence(body, datetime.now(UTC))}


@router.post("/schedules", status_code=201)
async def create_schedule(
    body: ScheduleSettings, request: Request, user=Depends(current_user)
):
    return await services(request).schedules.create(user, body)


@router.post("/schedules/batch-delete", status_code=204)
async def batch_delete_schedules(
    body: ScheduleIds, request: Request, user=Depends(current_user)
):
    await services(request).schedules.delete(user, body.ids)
    return Response(status_code=204)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    body: ScheduleSettings | ScheduleToggle,
    request: Request,
    user=Depends(current_user),
):
    settings = body.enabled if isinstance(body, ScheduleToggle) else body
    return await services(request).schedules.update(user, schedule_id, settings)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str, request: Request, user=Depends(current_user)
):
    await services(request).schedules.delete(user, [schedule_id])
    return Response(status_code=204)


@router.post("/schedules/{schedule_id}/run", status_code=202)
async def run_schedule(schedule_id: str, request: Request, user=Depends(current_user)):
    return await services(request).schedules.run(user, schedule_id)


@router.get("/schedule-runs")
async def list_schedule_runs(
    request: Request,
    schedule_id: Annotated[str | None, Query(max_length=64)] = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
    q: Annotated[str | None, Query(max_length=128)] = None,
    archived: bool = False,
    user=Depends(current_user),
):
    return {
        "items": await services(request).schedules.list_runs(
            user, schedule_id=schedule_id, status=status, q=q, archived=archived
        )
    }


@router.patch("/schedule-runs/{run_id}")
async def archive_run(
    run_id: str, body: ArchiveRun, request: Request, user=Depends(current_user)
):
    return await services(request).schedules.archive_run(user, run_id, body.archived)


@router.delete("/schedule-runs/{run_id}", status_code=204)
async def delete_run(run_id: str, request: Request, user=Depends(current_user)):
    await services(request).schedules.delete_run(user, run_id)
    return Response(status_code=204)
