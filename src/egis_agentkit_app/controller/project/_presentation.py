"""项目 presentation HTTP 接口；处理委托 Framework Service。"""

from fastapi import APIRouter, Depends, Request

from ..base import current_user, services
from ._model import PresentationSlideWrite

router = APIRouter()


@router.get("/projects/{project_id}/presentation-options")
async def get_presentation_options(
    project_id: str, request: Request, user=Depends(current_user)
):
    return await services(request).presentations.get_options(user, project_id)


@router.get("/projects/{project_id}/presentation")
async def get_presentation(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    return await services(request).presentations.get_presentation(
        user, project_id, area, path
    )


@router.post("/projects/{project_id}/presentation/slides")
async def update_presentation_slides(
    project_id: str,
    body: PresentationSlideWrite,
    request: Request,
    area: str,
    path: str,
    user=Depends(current_user),
):
    checksum = request.headers.get("If-Match", "").strip('"')
    return await services(request).presentations.update_slides(
        user,
        project_id,
        area,
        path,
        body.operation_type,
        body.slide_id,
        checksum,
        body.target_index,
    )
