"""Native session task management and reply artifact HTTP endpoints."""

from egis_agentkit.service.team._collaboration import TeamCollaborationService
from fastapi import APIRouter, Depends, Request, Response

from ..base import current_user, services
from ._model import (
    ReplyFeedbackWrite,
    TaskCollaboratorsWrite,
    TaskNameWrite,
    TaskSettingsWrite,
    TaskWrite,
)

router = APIRouter()


@router.get("/tasks/{sid}/reply-feedback")
async def list_reply_feedback(sid: str, request: Request, user=Depends(current_user)):
    return {
        "items": await services(request).session_feedback.list_reply_feedback(user, sid)
    }


@router.post("/tasks/{sid}/replies/{reply_id}/branch", status_code=201)
async def add_session_branch(
    sid: str, reply_id: str, request: Request, user=Depends(current_user)
):
    return await services(request).sessions.add_session_branch(
        user, sid, reply_id, request.app.state.egis_bus
    )


@router.put("/tasks/{sid}/replies/{reply_id}/feedback")
async def save_reply_feedback(
    sid: str,
    reply_id: str,
    body: ReplyFeedbackWrite,
    request: Request,
    user=Depends(current_user),
):
    return await services(request).session_feedback.save_reply_feedback(
        user, sid, reply_id, body.comment
    )


@router.get("/admin/reply-feedback")
async def page_reply_feedback(
    request: Request,
    limit: int | None = None,
    cursor: str | None = None,
    user=Depends(current_user),
):
    return await services(request).session_feedback.page_reply_feedback(
        user, limit=limit, cursor=cursor
    )


@router.get("/tasks")
async def list_tasks(request: Request, user=Depends(current_user)):
    return {
        "items": await services(request).sessions.list_sessions(
            user, request.app.state.egis_bus
        )
    }


@router.post("/tasks", status_code=201)
async def add_task(body: TaskWrite, request: Request, user=Depends(current_user)):
    return await services(request).sessions.add_session(
        user,
        body.definition_id,
        body.resource_view_type,
        resource_version=body.resource_version,
        name=body.name,
        model_key=body.model_key,
        permission_mode=body.permission_mode,
        project_id=body.project_id,
    )


@router.get("/runtime-options")
async def get_runtime_options(request: Request, user=Depends(current_user)):
    modes = [
        ("default", "Default", "按规则请求操作权限"),
        ("accept_edits", "Accept Edits", "自动允许工作目录内的文件操作"),
        ("explore", "Explore", "只读探索，拒绝修改"),
        ("bypass", "Bypass", "跳过大部分工具权限检查"),
    ]
    tasks = services(request).sessions
    allowed = {mode.value for mode in tasks.list_permission_modes()}
    return {
        "permission_modes": [
            {
                "value": value,
                "label": label,
                "description": description,
                "is_enabled": value in allowed,
            }
            for value, label, description in modes
        ],
        "default_permission_mode": tasks.get_default_permission_mode().value,
    }


@router.post("/tasks/{sid}/collaborators")
async def invite_collaborators(
    sid: str, body: TaskCollaboratorsWrite, request: Request, user=Depends(current_user)
):
    kit = services(request)
    return await TeamCollaborationService.stage_collaborators(
        kit.sessions,
        user,
        sid,
        request.app.state.egis_bus,
        body.request_id,
        [expert.model_dump() for expert in body.experts],
    )


@router.patch("/tasks/{sid}/settings")
async def update_task_settings(
    sid: str, body: TaskSettingsWrite, request: Request, user=Depends(current_user)
):
    return await services(request).sessions.update_session_settings(
        user,
        sid,
        request.app.state.egis_bus,
        permission_mode=body.permission_mode,
        model_key=body.model_key,
    )


@router.patch("/tasks/{sid}/name")
async def rename_task(
    sid: str, body: TaskNameWrite, request: Request, user=Depends(current_user)
):
    return await services(request).sessions.update_session_name(
        user, sid, request.app.state.egis_bus, body.name
    )


@router.get("/tasks/{sid}")
async def get_task(sid: str, request: Request, user=Depends(current_user)):
    return await services(request).sessions.get_session(user, sid)


@router.delete("/tasks/{sid}", status_code=204)
async def delete_task(sid: str, request: Request, user=Depends(current_user)):
    await services(request).sessions.delete_session(
        user, sid, request.app.state.egis_bus
    )
    return Response(status_code=204)


@router.get("/tasks/{sid}/artifacts")
async def list_session_artifacts(
    sid: str, request: Request, user=Depends(current_user)
):
    return await services(request).project_files.session_artifacts(user, sid)
