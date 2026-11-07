"""Native session task management and session-scoped workspace HTTP endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from ..schema import (
    DeliveryWrite,
    TaskCollaboratorsWrite,
    TaskNameWrite,
    TaskSettingsWrite,
    TaskWrite,
)
from ..security import current_user
from .dependencies import services
from .responses import file_response

router = APIRouter()


@router.get("/tasks")
async def list_tasks(request: Request, user=Depends(current_user)):
    return {"items": await services(request).tasks.list(user, request.app.state.egis_bus)}


@router.post("/tasks", status_code=201)
async def create_task(body: TaskWrite, request: Request, user=Depends(current_user)):
    return await services(request).tasks.create(
        user,
        body.definition_id,
        body.resource_view_type,
        name=body.name,
        model_key=body.model_key,
        permission_mode=body.permission_mode,
        project_id=body.project_id,
    )


@router.get("/runtime-options")
async def runtime_options(request: Request, user=Depends(current_user)):
    modes = [
        ("default", "Default", "按规则请求操作权限"),
        ("accept_edits", "Accept Edits", "自动允许工作目录内的文件操作"),
        ("explore", "Explore", "只读探索，拒绝修改"),
        ("bypass", "Bypass", "跳过大部分工具权限检查"),
    ]
    allowed = {mode.value for mode in services(request).tasks.allowed_permission_modes()}
    return {
        "permission_modes": [
            {"value": value, "label": label, "description": description, "is_enabled": value in allowed}
            for value, label, description in modes
        ],
        "default_permission_mode": "default",
    }


@router.post("/tasks/{sid}/collaborators")
async def invite_collaborators(
    sid: str, body: TaskCollaboratorsWrite, request: Request, user=Depends(current_user)
):
    return await services(request).tasks.collaboration.stage(
        user, sid, request.app.state.egis_bus, body.request_id,
        [expert.model_dump() for expert in body.experts],
    )


@router.patch("/tasks/{sid}/settings")
async def update_task_settings(
    sid: str, body: TaskSettingsWrite, request: Request, user=Depends(current_user)
):
    return await services(request).tasks.update_settings(
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
    return await services(request).tasks.rename(user, sid, request.app.state.egis_bus, body.name)


@router.get("/tasks/{sid}/file-changes")
async def task_file_changes(
    sid: str,
    request: Request,
    cursor: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
):
    return await services(request).workspace.session_file_changes(user, sid, cursor, limit)


@router.get("/tasks/{sid}")
async def get_task(sid: str, request: Request, user=Depends(current_user)):
    return await services(request).tasks.get(user, sid)


@router.delete("/tasks/{sid}", status_code=204)
async def delete_task(sid: str, request: Request, user=Depends(current_user)):
    await services(request).tasks.delete(user, sid, request.app.state.egis_bus)
    return Response(status_code=204)


@router.get("/tasks/{sid}/artifacts")
async def session_artifacts(sid: str, request: Request, user=Depends(current_user)):
    return await services(request).workspace.session_artifacts(user, sid)


@router.get("/tasks/{sid}/files")
async def list_files(
    sid: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    recursive: bool = False,
    user=Depends(current_user),
):
    return await services(request).workspace.list_session_files(user, sid, area, path, recursive)


@router.get("/tasks/{sid}/file")
async def get_file(
    sid: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    content, media_type = await services(request).workspace.read_session_file(user, sid, area, path)
    return file_response(content, media_type, path)


@router.delete("/tasks/{sid}/files", status_code=204)
async def delete_session_file(
    sid: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    await services(request).workspace.delete_session_file(user, sid, area, path)
    return Response(status_code=204)


@router.post("/tasks/{sid}/files", status_code=201)
async def upload_file(
    sid: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    workspace = services(request).workspace
    content = await file.read(workspace.max_upload_bytes + 1)
    return await workspace.upload_session_file(user, sid, file.filename, content, area, path)


@router.post("/tasks/{sid}/deliver", status_code=201)
async def deliver(
    sid: str, body: DeliveryWrite, request: Request, user=Depends(current_user)
):
    return await services(request).workspace.deliver_session_file(user, sid, body.path)


@router.get("/tasks/{sid}/preview")
async def preview_task_document(
    sid: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    result = await services(request).workspace.preview_session_document(user, sid, area, path)
    return file_response(result, "application/pdf", Path(path).stem + ".pdf")
