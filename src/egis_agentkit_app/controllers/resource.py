"""技能和连接器发布管理，以及工具目录的只读接口。"""

from typing import Literal
from urllib.parse import quote

from egis_agentkit.service._user import require_admin
from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field, SecretStr

from ..schema import InstallWrite, SkillImportJob, SkillImportList
from ..security import current_user
from .dependencies import services

router = APIRouter()


def add_resource_routes():
    for path, resource_type in (
        ("skills", "skill"),
        ("connectors", "mcp"),
        ("tools", "tool"),
    ):

        def endpoints(kind):
            async def listing(request: Request, user=Depends(current_user)):
                service = services(request).resources
                result = {"items": await service.list(user, kind)}
                if kind == "mcp":
                    dependencies = await service.mcp_dependency_authorizations(user)
                    if dependencies:
                        result["dependency_authorizations"] = dependencies
                return result

            async def detail(
                identifier: str,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request).resources.detail(
                    user, kind, identifier, version
                )

            async def save(
                body: dict,
                request: Request,
                identifier: str | None = None,
                user=Depends(current_user),
            ):
                if kind == "mcp" and "resource_version" in body:
                    raise ValueError("连接器版本由平台分配")
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
                return await services(
                    request
                ).personal_definition.installations.install(
                    user, kind, identifier, version
                )

            async def toggle(
                identifier: str,
                body: InstallWrite,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(
                    request
                ).personal_definition.installations.set_installation(
                    user, kind, identifier, version, body.is_enabled
                )

            async def versions(
                identifier: str, request: Request, user=Depends(current_user)
            ):
                return {
                    "items": await services(request).resources.list_asset_versions(
                        user, kind, identifier
                    )
                }

            return listing, detail, save, install, toggle, versions

        listing, detail, save, install, toggle, versions = endpoints(resource_type)
        router.add_api_route(f"/{path}", listing, methods=["GET"], name=f"list_{path}")
        if resource_type != "tool":
            router.add_api_route(
                f"/{path}", save, methods=["POST"], name=f"create_{path}"
            )
            router.add_api_route(
                f"/{path}/{{identifier}}", save, methods=["PUT"], name=f"update_{path}"
            )
        router.add_api_route(
            f"/{path}/{{identifier}}", detail, methods=["GET"], name=f"get_{path}"
        )
        router.add_api_route(
            f"/{path}/{{identifier}}/versions",
            versions,
            methods=["GET"],
            name=f"versions_{path}",
        )
        if resource_type != "tool":
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


@router.post(
    "/skills/imports/{job_id}/retry", status_code=202, response_model=SkillImportJob
)
async def retry_skill_import(job_id: str, request: Request, user=Depends(current_user)):
    return await services(request).skill_imports.retry(user, job_id)


@router.get("/skills/{identifier}/download")
async def download_skill(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    content = await services(request).resources.download_skill(
        user, identifier, version
    )
    return Response(
        content,
        media_type="application/zip",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(identifier + ".zip"),
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


class ConnectorKeyWrite(BaseModel):
    key: SecretStr


class ConnectorCallbackWrite(BaseModel):
    state: str = Field(min_length=1, max_length=256)
    code: SecretStr | None = None


@router.get("/connectors/{identifier}/authorization")
async def connector_auth_status(
    identifier: str, request: Request, version: str, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, version, "status"
    )


@router.put("/connectors/{identifier}/authorization/key")
async def connector_api_key(
    identifier: str,
    body: ConnectorKeyWrite,
    request: Request,
    version: str,
    user=Depends(current_user),
):
    return await services(request).resources.mcp_auth_action(
        user,
        identifier,
        version,
        "set_api_key",
        key=body.key.get_secret_value(),
    )


@router.post("/connectors/{identifier}/authorization/start")
async def connector_oauth_start(
    identifier: str, request: Request, version: str, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, version, "start"
    )


@router.post("/connectors/{identifier}/authorization/callback")
async def connector_oauth_callback(
    identifier: str,
    body: ConnectorCallbackWrite,
    request: Request,
    version: str,
    user=Depends(current_user),
):
    return await services(request).resources.mcp_auth_action(
        user,
        identifier,
        version,
        "callback",
        state=body.state,
        code=body.code.get_secret_value() if body.code is not None else None,
    )


@router.delete("/connectors/{identifier}/authorization")
async def connector_revoke(
    identifier: str, request: Request, version: str, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, version, "revoke"
    )


@router.get("/admin/resources/{kind}")
async def admin_resources(
    kind: Literal["skill", "mcp"], request: Request, user=Depends(current_user)
):
    return {"items": await services(request).resources.admin_list(user, kind)}


@router.post("/admin/resources/{kind}", status_code=201)
async def register_system_resource(
    kind: Literal["skill", "mcp"],
    body: dict,
    request: Request,
    user=Depends(current_user),
):
    require_admin(user)
    service = services(request).resources
    data = {**body, "owner_type": "system", "owner_id": "system"}
    if kind == "skill":
        return await service.save_skill(user, data)
    if "resource_version" in data:
        raise ValueError("连接器版本由平台分配")
    return await service.save_mcp(user, data)


@router.patch("/admin/resources/{kind}/{identifier}")
async def update_resource_availability(
    kind: Literal["skill", "mcp"],
    identifier: str,
    body: InstallWrite,
    request: Request,
    version: str,
    user=Depends(current_user),
):
    return await services(request).resources.set_asset_enabled(
        user,
        kind,
        identifier,
        version,
        body.is_enabled,
        admin=True,
    )
