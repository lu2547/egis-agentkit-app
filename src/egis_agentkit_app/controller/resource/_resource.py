"""技能和连接器发布管理，以及个人助理可选工具配置。"""

from typing import Literal
from urllib.parse import quote

from egis_agentkit.client.nacos._settings import AdminPaginationConfig
from egis_agentkit.core.skill._avatar import AUTO_AVATAR
from egis_agentkit.service._admin_page import AdminPage, AdminPageResult
from egis_agentkit.service._user import require_admin
from egis_agentkit.storage.model import User
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)

from ..base import current_user, services
from ..base._pagination import AdminPagination
from ._model import (
    ConnectorCallbackWrite,
    ConnectorKeyWrite,
    InstallWrite,
    SkillImportDecision,
    SkillImportJob,
    SkillImportList,
)

router = APIRouter()


@router.delete("/skills/{identifier}", status_code=204)
async def delete_skill(
    identifier: str, request: Request, user: User = Depends(current_user)
) -> Response:
    await services(request).resources.delete_skill(user, identifier)
    return Response(status_code=204)


def add_resource_routes():
    for path, resource_type in (
        ("skills", "skill"),
        ("connectors", "mcp"),
        ("tools", "tool"),
    ):

        def build_endpoints(kind):
            async def list_resources(
                request: Request,
                catalog: bool = False,
                cursor: str | None = None,
                limit: int | None = Query(default=None, ge=1),
                query: str = "",
                category: str = "",
                mine: bool = False,
                resource_ids: list[str] | None = Query(default=None, max_length=100),
                runtime_names: list[str] | None = Query(default=None, max_length=100),
                owner_type: Literal["system"] | None = None,
                purpose: Literal["grant"] | None = None,
                user=Depends(current_user),
            ):
                service = services(request).resources
                if catalog or kind == "skill":
                    return await service.catalog_page(
                        user,
                        kind,
                        cursor=cursor,
                        limit=limit,
                        query=query,
                        category=category,
                        mine=mine,
                        resource_ids=resource_ids,
                        owner_type=owner_type,
                        purpose=purpose,
                        runtime_names=runtime_names,
                    )
                return {"items": await service.list(user, kind)}

            async def get_resource(
                identifier: str,
                request: Request,
                version: str | None = None,
                user=Depends(current_user),
            ):
                if version is None and kind != "mcp":
                    raise HTTPException(status_code=422, detail="version is required")
                return await services(request).resources.detail(
                    user, kind, identifier, version
                )

            async def save_resource(
                body: dict,
                request: Request,
                identifier: str | None = None,
                user=Depends(current_user),
            ):
                if identifier:
                    body = {**body, "resource_id": identifier}
                return await services(request).resources.save_skill(user, body)

            async def add_installation(
                identifier: str,
                request: Request,
                user=Depends(current_user),
            ):
                return await services(request).resources.install(user, kind, identifier)

            async def update_installation(
                identifier: str,
                body: InstallWrite,
                request: Request,
                user=Depends(current_user),
            ):
                return await services(request).resources.update_installation(
                    user, kind, identifier, body.is_enabled
                )

            async def remove_installation(
                identifier: str,
                request: Request,
                user: User = Depends(current_user),
            ) -> Response:
                await services(request).resources.remove_installation(
                    user, kind, identifier
                )
                return Response(status_code=204)

            async def list_versions(
                identifier: str, request: Request, user=Depends(current_user),
                cursor: str | None = None, limit: int | None = Query(default=None, ge=1),
                query: str = "",
            ):
                if kind == "skill":
                    return await services(request).resources.skill_versions_page(
                        user, identifier, cursor=cursor, limit=limit, query=query
                    )
                return {
                    "items": await services(request).resources.list_asset_versions(
                        user, kind, identifier
                    )
                }

            return (
                list_resources,
                get_resource,
                save_resource,
                add_installation,
                update_installation,
                list_versions,
                remove_installation,
            )

        (
            list_resources,
            get_resource,
            save_resource,
            add_installation,
            update_installation,
            list_versions,
            remove_installation,
        ) = build_endpoints(resource_type)
        router.add_api_route(
            f"/{path}", list_resources, methods=["GET"], name=f"list_{path}"
        )
        if resource_type == "skill":
            router.add_api_route(
                f"/{path}", save_resource, methods=["POST"], name=f"create_{path}"
            )
            router.add_api_route(
                f"/{path}/{{identifier}}",
                save_resource,
                methods=["PUT"],
                name=f"update_{path}",
            )
        router.add_api_route(
            f"/{path}/{{identifier}}", get_resource, methods=["GET"], name=f"get_{path}"
        )
        if resource_type != "mcp":
            router.add_api_route(
                f"/{path}/{{identifier}}/versions",
                list_versions,
                methods=["GET"],
                name=f"versions_{path}",
            )
        router.add_api_route(
            f"/{path}/{{identifier}}/install",
            add_installation,
            methods=["POST"],
            name=f"install_{path}",
        )
        router.add_api_route(
            f"/{path}/{{identifier}}/installation",
            update_installation,
            methods=["PATCH"],
            name=f"toggle_{path}",
        )
        router.add_api_route(
            f"/{path}/{{identifier}}/installation",
            remove_installation,
            methods=["DELETE"],
            status_code=204,
            name=f"remove_{path}_installation",
        )


async def _site_skill_import_user(
    request: Request, user: User = Depends(current_user)
) -> User:
    if getattr(request.state, "egis_virtual_user", False):
        raise HTTPException(403, "站内技能导入仅接受站内账号")
    return user


@router.post("/skills/imports", status_code=202, response_model=SkillImportJob)
async def upload_skill(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("other"),
    avatar: str = Form(AUTO_AVATAR),
    owner_type: Literal["user", "system"] = Form("user"),
    resource_id: str | None = Form(None, max_length=128),
    user: User = Depends(_site_skill_import_user),
):
    return await services(request).skill_imports.enqueue(
        user,
        file.file,
        filename=file.filename,
        category=category,
        avatar=avatar,
        owner_type=owner_type,
        resource_id=resource_id,
    )


@router.get("/skills/imports", response_model=SkillImportList)
async def list_skill_imports(
    request: Request, user: User = Depends(_site_skill_import_user)
):
    return {"items": await services(request).skill_imports.list(user)}


@router.get("/skills/imports/{job_id}", response_model=SkillImportJob)
async def get_skill_import(
    job_id: str, request: Request, user: User = Depends(_site_skill_import_user)
):
    return await services(request).skill_imports.get(user, job_id)


@router.post(
    "/skills/imports/{job_id}/retry", status_code=202, response_model=SkillImportJob
)
async def retry_skill_import(
    job_id: str, request: Request, user: User = Depends(_site_skill_import_user)
):
    return await services(request).skill_imports.retry(user, job_id)


@router.get(
    "/admin/skill-imports",
    response_model=AdminPageResult[SkillImportJob] | SkillImportList,
)
async def list_skill_import_reviews(
    request: Request, page: AdminPagination, user=Depends(current_user)
):
    imports = services(request).skill_imports
    if page is None:
        return {"items": await imports.list_reviews(user)}
    return await imports.list_reviews(user, page=page)


@router.post("/admin/skill-imports/batch/decision")
async def decide_skill_import_reviews(
    body: SkillImportDecision, request: Request, user=Depends(current_user)
):
    items = await services(request).skill_imports.decide_batch(
        user, body.job_ids, approved=body.approved, reason=body.reason
    )
    return {"items": items}


@router.get("/admin/skill-imports/{job_id}/download")
async def download_skill_import_review(
    job_id: str, request: Request, user=Depends(current_user)
):
    filename, content = await services(request).skill_imports.download_review(user, job_id)
    return _zip_download(content, filename)


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
    return _zip_download(content, identifier + ".zip")


@router.get("/skills/{identifier}/avatar")
async def read_skill_avatar(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    content = await services(request).resources.read_skill_avatar(
        user, identifier, version
    )
    return Response(
        content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _zip_download(content, filename):
    return Response(
        content,
        media_type="application/zip",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(filename, safe=""),
        },
    )


@router.post("/connectors/{identifier}/test")
async def test_connector(
    identifier: str,
    request: Request,
    user=Depends(current_user),
):
    return await services(request).resources.test_mcp(user, identifier)


add_resource_routes()


@router.get("/connectors/{identifier}/authorization")
async def connector_auth_status(
    identifier: str, request: Request, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, "status"
    )


@router.put("/connectors/{identifier}/authorization/key")
async def connector_api_key(
    identifier: str,
    body: ConnectorKeyWrite,
    request: Request,
    user=Depends(current_user),
):
    return await services(request).resources.mcp_auth_action(
        user,
        identifier,
        "set_api_key",
        key=body.key.get_secret_value(),
    )


@router.post("/connectors/{identifier}/authorize")
async def connector_oauth_start(
    identifier: str, request: Request, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, "start"
    )


@router.post("/connectors/{identifier}/authorization/callback")
async def connector_oauth_callback(
    identifier: str,
    body: ConnectorCallbackWrite,
    request: Request,
    user=Depends(current_user),
):
    return await services(request).resources.mcp_auth_action(
        user,
        identifier,
        "callback",
        state=body.state,
        code=body.code.get_secret_value() if body.code is not None else None,
    )


@router.delete("/connectors/{identifier}/authorization")
async def connector_revoke(
    identifier: str, request: Request, user=Depends(current_user)
):
    return await services(request).resources.mcp_auth_action(
        user, identifier, "revoke"
    )


@router.get("/admin/resources/{kind}")
async def admin_resources(
    kind: Literal["skill", "mcp"], request: Request, page: AdminPagination,
    user=Depends(current_user), query: str = "",
):
    resources = services(request).resources
    if page is None and kind == "skill":
        config = getattr(request.app.state, "egis_config", None)
        settings = config.snapshot.admin.pagination if config is not None else AdminPaginationConfig()
        page = AdminPage(number=1, size=settings.default_page_size)
    if page is None:
        return {"items": await resources.admin_list(user, kind)}
    return await resources.admin_list(user, kind, page=page, query=query)


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
    return await service.save_mcp(user, data)


@router.patch("/admin/resources/{kind}/{identifier}")
async def update_resource_availability(
    kind: Literal["skill", "mcp"],
    identifier: str,
    body: InstallWrite,
    request: Request,
    version: str | None = None,
    user=Depends(current_user),
):
    if version is None and kind != "mcp":
        raise HTTPException(status_code=422, detail="version is required")
    return await services(request).resources.set_asset_enabled(
        user,
        kind,
        identifier,
        version,
        body.is_enabled,
        admin=True,
    )
