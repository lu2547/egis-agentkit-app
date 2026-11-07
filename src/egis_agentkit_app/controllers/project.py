"""Projects and project-scoped workspace HTTP endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from ..schema import DeliveryWrite, ProjectWrite
from ..security import current_user
from .dependencies import services
from .responses import file_response

router = APIRouter()


@router.get("/projects")
async def list_projects(request: Request, user=Depends(current_user)):
    return {"items": await services(request).projects.list(user)}


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectWrite, request: Request, user=Depends(current_user)
):
    return await services(request).projects.create(user, body.project_name)


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request, user=Depends(current_user)):
    return await services(request).projects.get(user, project_id)


@router.patch("/projects/{project_id}")
async def rename_project(
    project_id: str, body: ProjectWrite, request: Request, user=Depends(current_user)
):
    return await services(request).projects.rename(user, project_id, body.project_name)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request, user=Depends(current_user)):
    await services(request).projects.delete(user, project_id, request.app.state.egis_bus)
    return Response(status_code=204)


@router.get("/projects/{project_id}/file-changes")
async def project_file_changes(
    project_id: str,
    request: Request,
    cursor: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
):
    return await services(request).workspace.project_file_changes(user, project_id, cursor, limit)


@router.get("/projects/{project_id}/files")
async def project_files(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    recursive: bool = False,
    user=Depends(current_user),
):
    return await services(request).workspace.list_project_files(user, project_id, area, path, recursive)


@router.get("/projects/{project_id}/file")
async def project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    content, media_type = await services(request).workspace.read_project_file(user, project_id, area, path)
    return file_response(content, media_type, path)


@router.delete("/projects/{project_id}/files", status_code=204)
async def delete_project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    await services(request).workspace.delete_project_file(user, project_id, area, path)
    return Response(status_code=204)


@router.post("/projects/{project_id}/files", status_code=201)
async def upload_project_file(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    workspace = services(request).workspace
    content = await file.read(workspace.max_upload_bytes + 1)
    return await workspace.upload_project_file(user, project_id, file.filename, content, area, path)


@router.post("/projects/{project_id}/deliver", status_code=201)
async def project_deliver(
    project_id: str, body: DeliveryWrite, request: Request, user=Depends(current_user)
):
    return await services(request).workspace.deliver_project_file(user, project_id, body.path)


@router.get("/projects/{project_id}/preview")
async def preview_project_document(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    result = await services(request).workspace.preview_project_document(user, project_id, area, path)
    return file_response(result, "application/pdf", Path(path).stem + ".pdf")
