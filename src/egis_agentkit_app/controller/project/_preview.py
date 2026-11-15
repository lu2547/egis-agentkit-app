"""项目 preview HTTP 接口；处理委托 Framework Service。"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from ..base import current_user, file_response, run_until_disconnect, services

router = APIRouter()


@router.get("/projects/{project_id}/preview")
async def preview_project_document(
    project_id: str,
    request: Request,
    area: str,
    path: str,
    checksum: str | None = None,
    page: int | None = None,
    user=Depends(current_user),
):
    result = await run_until_disconnect(
        request,
        services(request).project_files.preview_project_document(
            user, project_id, area, path, checksum=checksum, page=page
        ),
    )
    return file_response(result, "application/pdf", Path(path).stem + ".pdf")


@router.get("/projects/{project_id}/preview-options")
async def get_preview_options(
    project_id: str, request: Request, user=Depends(current_user)
):
    """返回当前项目文件框选引用所使用的非敏感限制。"""
    return await services(request).project_files.get_preview_options(user, project_id)
