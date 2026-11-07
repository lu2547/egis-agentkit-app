"""Skill and connector resource HTTP endpoints."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from ..schema import InstallWrite, SkillImportJob, SkillImportList
from ..security import current_user
from .dependencies import services

router = APIRouter()


def add_resource_routes():
    for path, resource_type in (("skills", "skill"), ("connectors", "mcp")):

        def endpoints(kind):
            async def listing(request: Request, user=Depends(current_user)):
                return {"items": await services(request).resources.list(user, kind)}

            async def detail(
                identifier: str,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request).resources.detail(user, kind, identifier, version)

            async def save(
                body: dict,
                request: Request,
                identifier: str | None = None,
                user=Depends(current_user),
            ):
                if identifier:
                    body = {**body, "resource_id": identifier}
                service = services(request).resources
                return await (
                    service.save_skill(user, body)
                    if kind == "skill"
                    else service.save_mcp(user, body)
                )

            async def install(
                identifier: str,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request).resources.install(user, kind, identifier, version)

            async def toggle(
                identifier: str,
                body: InstallWrite,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request).resources.set_installation(
                    user, kind, identifier, version, body.is_enabled
                )

            return listing, detail, save, install, toggle

        listing, detail, save, install, toggle = endpoints(resource_type)
        router.add_api_route(f"/{path}", listing, methods=["GET"], name=f"list_{path}")
        router.add_api_route(f"/{path}", save, methods=["POST"], name=f"create_{path}")
        router.add_api_route(
            f"/{path}/{{identifier}}", detail, methods=["GET"], name=f"get_{path}"
        )
        router.add_api_route(
            f"/{path}/{{identifier}}", save, methods=["PUT"], name=f"update_{path}"
        )
        router.add_api_route(
            f"/{path}/{{identifier}}/install",
            install,
            methods=["POST"],
            name=f"install_{path}",
        )
        router.add_api_route(
            f"/{path}/{{identifier}}/installation",
            toggle,
            methods=["PATCH"],
            name=f"toggle_{path}",
        )


@router.post("/skills/imports", status_code=202, response_model=SkillImportJob)
@router.post("/skills/upload", status_code=202, response_model=SkillImportJob)
async def upload_skill(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("other"),
    avatar: str = Form("book"),
    user=Depends(current_user),
):
    return await services(request).skill_imports.enqueue(
        user, file.file, filename=file.filename, category=category, avatar=avatar
    )


@router.get("/skills/imports", response_model=SkillImportList)
async def list_skill_imports(request: Request, user=Depends(current_user)):
    return {"items": await services(request).skill_imports.list(user)}


@router.get("/skills/imports/{job_id}", response_model=SkillImportJob)
async def get_skill_import(job_id: str, request: Request, user=Depends(current_user)):
    return await services(request).skill_imports.get(user, job_id)


@router.post("/skills/imports/{job_id}/retry", status_code=202, response_model=SkillImportJob)
async def retry_skill_import(job_id: str, request: Request, user=Depends(current_user)):
    return await services(request).skill_imports.retry(user, job_id)


@router.get("/skills/{identifier}/download")
async def download_skill(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    content = await services(request).resources.download_skill(user, identifier, version)
    return Response(
        content,
        media_type="application/zip",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(identifier + ".zip"),
        },
    )


@router.post("/connectors/{identifier}/test")
async def test_connector(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    return await services(request).resources.test_mcp(user, identifier, version)


add_resource_routes()
