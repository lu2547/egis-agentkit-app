"""项目 project HTTP 接口；处理委托 Framework Service。"""

from fastapi import APIRouter, Depends, Request, Response

from ..base import current_user, services
from ._model import ProjectWrite

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
    await services(request).projects.delete(
        user, project_id, request.app.state.egis_bus
    )
    return Response(status_code=204)
