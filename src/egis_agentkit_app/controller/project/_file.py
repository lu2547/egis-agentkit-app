"""项目 file HTTP 接口；处理委托 Framework Service。"""

import hashlib

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from ..base import current_user, file_response, services
from ._model import DeliveryWrite

router = APIRouter()


@router.get("/projects/{project_id}/file-changes")
async def project_file_changes(
    project_id: str,
    request: Request,
    cursor: int | None = Query(None, ge=1),
    limit: int | None = Query(None, ge=1),
    user=Depends(current_user),
):
    return await services(request).project_files.project_file_changes(
        user, project_id, cursor, limit
    )


@router.get("/projects/{project_id}/files")
async def project_files(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    recursive: bool = False,
    user=Depends(current_user),
):
    return await services(request).project_files.list_project_files(
        user, project_id, area, path, recursive
    )


@router.get("/projects/{project_id}/file")
async def project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    content, media_type = await services(request).project_files.read_project_file(
        user, project_id, area, path
    )
    response = file_response(content, media_type, path)
    response.headers["ETag"] = '"' + hashlib.sha256(content).hexdigest() + '"'
    return response


@router.put("/projects/{project_id}/file")
async def update_project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    """流式接收编辑结果，限制请求大小并校验文件读取时的摘要。"""
    from egis_agentkit.errors import InvalidRequest

    manager = services(request).project_files
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > manager.max_upload_bytes:
            raise InvalidRequest("文件超过项目大小限制")
    checksum = request.headers.get("If-Match", "").strip('"')
    return await manager.update_project_file(
        user, project_id, area, path, bytes(content), checksum
    )


@router.get("/projects/{project_id}/workbook-options")
async def get_workbook_options(
    project_id: str, request: Request, user=Depends(current_user)
):
    return await services(request).project_files.get_workbook_options(user, project_id)


@router.delete("/projects/{project_id}/files", status_code=204)
async def delete_project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    await services(request).project_files.delete_project_file(
        user, project_id, area, path
    )
    return Response(status_code=204)


@router.post("/projects/{project_id}/files", status_code=201)
async def upload_project_file(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    overwrite: bool = False,
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    workspace = services(request).project_files
    content = await file.read(workspace.max_upload_bytes + 1)
    return await workspace.upload_project_file(
        user, project_id, file.filename, content, area, path, overwrite=overwrite
    )


@router.post("/projects/{project_id}/deliver", status_code=201)
async def project_deliver(
    project_id: str, body: DeliveryWrite, request: Request, user=Depends(current_user)
):
    return await services(request).project_files.deliver_project_file(
        user, project_id, body.path
    )
