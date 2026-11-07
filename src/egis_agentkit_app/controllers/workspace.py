"""User workspace HTTP endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from ..security import current_user
from .dependencies import services
from .responses import file_response

router = APIRouter()


@router.get("/workspace/files")
async def list_workspace_files(
    request: Request, path: str = "", user=Depends(current_user)
):
    return await services(request).workspace.list_user_files(user, path)


@router.get("/workspace/file")
async def get_workspace_file(request: Request, path: str, user=Depends(current_user)):
    content, media_type = await services(request).workspace.read_user_file(user, path)
    return file_response(content, media_type, path)


@router.post("/workspace/files", status_code=201)
async def upload_workspace_file(
    request: Request,
    file: UploadFile = File(...),
    path: str | None = Query(None),
    form_path: str = Form("", alias="path"),
    user=Depends(current_user),
):
    workspace = services(request).workspace
    content = await file.read(workspace.max_upload_bytes + 1)
    return await workspace.upload_user_file(
        user, file.filename, content, path if path is not None else form_path
    )


@router.get("/workspace/preview")
async def preview_user_document(
    request: Request, path: str, user=Depends(current_user)
):
    result = await services(request).workspace.preview_user_document(user, path)
    return file_response(result, "application/pdf", Path(path).stem + ".pdf")
