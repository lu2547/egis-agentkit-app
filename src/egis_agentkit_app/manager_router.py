"""Thin HTTP controller. Rules, persistence and assembly live in framework."""

import asyncio
from pathlib import Path
from urllib.parse import quote

from egis_agentkit.errors import Forbidden
from egis_agentkit.models import Definition, Grant, Group, User
from egis_agentkit.services.users import require_admin
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

from .schema import (
    AgentWrite,
    DecisionWrite,
    DeliveryWrite,
    InstallWrite,
    PreferencesWrite,
    ProjectWrite,
    ShareWrite,
    TaskNameWrite,
    TaskSettingsWrite,
    TaskWrite,
    TeamWrite,
)
from .security import current_user

router = APIRouter(prefix="/manager", tags=["manager"])


def services(request):
    return request.app.state.egis_services


@router.get("/me")
async def me(user=Depends(current_user)):
    return user


@router.get("/assistant")
async def assistant(request: Request, user=Depends(current_user)):
    row = await services(request)["agents"].personal(user)
    return {
        **row,
        "resource_view_type": "private",
        "is_usable": True,
        "is_editable": True,
    }


@router.get("/agents")
async def list_agents(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["agents"].list(user)}


@router.get("/teams")
async def list_teams(request: Request, user=Depends(current_user)):
    return {
        "items": await services(request)["agents"].list(user, definition_type="team")
    }


async def definition_detail(request, user, identifier, view, expected_type):
    svc = services(request)
    source = await svc["storage"].get_definition(identifier)
    if source["definition_type"] != expected_type:
        raise HTTPException(404, "资源类型不匹配")
    editable = (
        user.role_type == "admin"
        or source["owner_type"] == "user"
        and source["owner_id"] == user.user_id
    )
    if view == "private" and not editable:
        raise Forbidden()
    if not editable and source["owner_type"] != "system":
        await svc["permissions"].require(user, expected_type, identifier, view)
    row = await svc["agents"].raw_view(identifier, view)
    result = {
        **row,
        "resource_view_type": view,
        "is_editable": editable,
        "is_deletable": editable,
        "is_usable": (
            await svc["permissions"].explain(user, expected_type, identifier, view)
        ).is_allowed,
    }
    if expected_type == "team" and editable:
        ref = row["payload"]["orchestrator"]
        leader = await svc["storage"].get_definition(ref["definition_id"])
        result["orchestrator_config"] = {
            k: leader[k]
            for k in ("agent_name", "agent_display_name", "payload", "config_version")
        }
    return result


@router.get("/agents/{identifier}")
async def get_agent(
    identifier: str, request: Request, view: str = "private", user=Depends(current_user)
):
    return await definition_detail(request, user, identifier, view, "agent")


@router.get("/teams/{identifier}")
async def get_team(
    identifier: str, request: Request, view: str = "private", user=Depends(current_user)
):
    return await definition_detail(request, user, identifier, view, "team")


async def save_agent(request, user, body, identifier=None):
    values = body.model_dump()
    values["owner_id"] = values["owner_id"] or user.user_id
    if identifier:
        values["id"] = identifier
    row = await services(request)["agents"].save(user, Definition(**values))
    return {
        **row,
        "resource_view_type": "system" if row["owner_type"] == "system" else "private",
        "is_editable": True,
    }


@router.post("/agents", status_code=201)
async def create_agent(body: AgentWrite, request: Request, user=Depends(current_user)):
    return await save_agent(request, user, body)


@router.put("/agents/{identifier}")
async def update_agent(
    identifier: str, body: AgentWrite, request: Request, user=Depends(current_user)
):
    return await save_agent(request, user, body, identifier)


async def save_team(request, user, body, identifier=None):
    values = body.model_dump()
    values["owner_id"] = values["owner_id"] or user.user_id
    if identifier:
        values["id"] = identifier
    row = await services(request)["teams"].save(user, values)
    return {
        **row,
        "resource_view_type": "system" if row["owner_type"] == "system" else "private",
        "is_editable": True,
    }


@router.post("/teams", status_code=201)
async def create_team(body: TeamWrite, request: Request, user=Depends(current_user)):
    return await save_team(request, user, body)


@router.put("/teams/{identifier}")
async def update_team(
    identifier: str, body: TeamWrite, request: Request, user=Depends(current_user)
):
    return await save_team(request, user, body, identifier)


@router.delete("/agents/{identifier}", status_code=204)
@router.delete("/teams/{identifier}", status_code=204)
async def delete_definition(
    identifier: str, request: Request, user=Depends(current_user)
):
    await services(request)["agents"].delete(user, identifier)
    return Response(status_code=204)


@router.get("/models")
async def list_models(request: Request, user=Depends(current_user)):
    return services(request)["models"].list()


@router.get("/tasks")
async def list_tasks(request: Request, user=Depends(current_user)):
    return {
        "items": await services(request)["tasks"].list(user, request.app.state.egis_bus)
    }


@router.post("/tasks", status_code=201)
async def create_task(body: TaskWrite, request: Request, user=Depends(current_user)):
    return await services(request)["tasks"].create(
        user,
        body.definition_id,
        body.resource_view_type,
        name=body.name,
        model_key=body.model_key,
        permission_mode=body.permission_mode,
        project_id=body.project_id,
    )


@router.get("/projects")
async def list_projects(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["projects"].list(user)}


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectWrite, request: Request, user=Depends(current_user)
):
    return await services(request)["projects"].create(user, body.project_name)


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request, user=Depends(current_user)):
    return await services(request)["projects"].get(user, project_id)


@router.patch("/projects/{project_id}")
async def rename_project(
    project_id: str, body: ProjectWrite, request: Request, user=Depends(current_user)
):
    return await services(request)["projects"].rename(
        user, project_id, body.project_name
    )


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request, user=Depends(current_user)):
    await services(request)["projects"].delete(
        user, project_id, request.app.state.egis_bus
    )
    return Response(status_code=204)


async def session_project_id(request, user, sid):
    session = await services(request)["tasks"].session(user, sid, require_use=False)
    return session.state.middle_context["egis_agentkit"]["project_id"]


@router.get("/runtime-options")
async def runtime_options(request: Request, user=Depends(current_user)):
    modes = [
        ("default", "Default", "按规则请求操作权限"),
        ("accept_edits", "Accept Edits", "自动允许工作目录内的文件操作"),
        ("explore", "Explore", "只读探索，拒绝修改"),
        ("bypass", "Bypass", "跳过大部分工具权限检查"),
        ("dont_ask", "Don't Ask", "自动拒绝需要确认的操作"),
    ]
    allowed = {
        mode.value for mode in services(request)["tasks"].allowed_permission_modes()
    }
    return {
        "permission_modes": [
            {
                "value": value,
                "label": label,
                "description": description,
                "is_enabled": value in allowed,
            }
            for value, label, description in modes
        ],
        "default_permission_mode": "default",
    }


@router.patch("/tasks/{sid}/settings")
async def update_task_settings(
    sid: str, body: TaskSettingsWrite, request: Request, user=Depends(current_user)
):
    return await services(request)["tasks"].update_settings(
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
    return await services(request)["tasks"].rename(
        user, sid, request.app.state.egis_bus, body.name
    )


@router.get("/projects/{project_id}/file-changes")
async def project_file_changes(
    project_id: str,
    request: Request,
    cursor: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
):
    svc = services(request)
    async with svc["projects"].guard(user, project_id):
        await svc["file_changes"].observe_safe(user.user_id, project_id)
        return await svc["file_changes"].list(project_id, cursor, limit)


@router.get("/tasks/{sid}/file-changes")
async def task_file_changes(
    sid: str,
    request: Request,
    cursor: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
):
    return await project_file_changes(
        await session_project_id(request, user, sid), request, cursor, limit, user
    )


@router.get("/tasks/{sid}")
async def get_task(sid: str, request: Request, user=Depends(current_user)):
    return await services(request)["tasks"].get(user, sid)


@router.delete("/tasks/{sid}", status_code=204)
async def delete_task(sid: str, request: Request, user=Depends(current_user)):
    await services(request)["tasks"].delete(user, sid, request.app.state.egis_bus)
    return Response(status_code=204)


@router.get("/workspace/files")
async def list_workspace_files(
    request: Request, path: str = "", user=Depends(current_user)
):
    return {
        "items": services(request)["files"].list_user(user.user_id, path),
        "path": path,
    }


@router.get("/workspace/file")
async def get_workspace_file(request: Request, path: str, user=Depends(current_user)):
    content, media_type = services(request)["files"].read_user(user.user_id, path)
    return file_response(content, media_type, path)


def file_response(content, media_type, path):
    return Response(
        content,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:",
            "Content-Disposition": "inline; filename*=UTF-8''" + quote(Path(path).name),
        },
    )


@router.post("/workspace/files", status_code=201)
async def upload_workspace_file(
    request: Request,
    file: UploadFile = File(...),
    path: str | None = Query(None),
    form_path: str = Form("", alias="path"),
    user=Depends(current_user),
):
    files = services(request)["files"]
    parts = files._parts(path if path is not None else form_path)
    if parts and parts[0] in ("work", "artifacts"):
        raise Forbidden("上传只能保存到 uploads")
    if parts and parts[0] == "uploads":
        parts = parts[1:]
    path = "/".join(parts)
    content = await file.read(files.max_bytes + 1)
    filename = Path(file.filename or "upload").name
    target = files.write_user(
        user.user_id, "/".join(filter(None, ["uploads", path, filename])), content
    )
    return {
        "name": target.name,
        "path": target.relative_to(files.user_root(user.user_id)).as_posix(),
        "is_directory": False,
        "size": len(content),
        "modified_at": target.stat().st_mtime,
    }


@router.get("/projects/{project_id}/files")
async def project_files(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    recursive: bool = False,
    user=Depends(current_user),
):
    svc = services(request)
    async with svc["projects"].guard(user, project_id):
        if area == "artifacts":
            await svc["file_changes"].observe_safe(
                user.user_id, project_id, discover=True
            )
        items = await asyncio.to_thread(
            svc["files"].list, user.user_id, project_id, area, path, recursive=recursive
        )
        return {
            "items": [{**item, "area": area} for item in items],
            "area": area,
            "path": path,
        }


@router.get("/tasks/{sid}/files")
async def list_files(
    sid: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    recursive: bool = False,
    user=Depends(current_user),
):
    return await project_files(
        await session_project_id(request, user, sid),
        request,
        area,
        path,
        recursive,
        user,
    )


@router.get("/projects/{project_id}/file")
async def project_file(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    svc = services(request)
    async with svc["projects"].guard(user, project_id):
        content, media_type = await asyncio.to_thread(
            svc["files"].read, user.user_id, project_id, area, path
        )
        return file_response(content, media_type, path)


@router.get("/tasks/{sid}/file")
async def get_file(
    sid: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    return await project_file(
        await session_project_id(request, user, sid), request, area, path, user
    )


@router.post("/projects/{project_id}/files", status_code=201)
async def upload_project_file(
    project_id: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    if area not in ("uploads", "work"):
        raise Forbidden("上传只能保存到项目根目录")
    svc = services(request)
    await svc["projects"].get(user, project_id)
    maximum = svc["files"].max_bytes
    content = await file.read(maximum + 1)
    filename = Path(file.filename or "upload").name
    async with svc["projects"].guard(user, project_id):
        changes = svc["file_changes"]
        await changes.observe_safe(user.user_id, project_id)
        async with changes.locked([project_id]):
            target = await asyncio.to_thread(
                svc["files"].write,
                user.user_id,
                project_id,
                "/".join(filter(None, [path, filename])),
                content,
                area="uploads",
            )
        await changes.observe_safe(user.user_id, project_id)
        return {
            "name": target.name,
            "path": target.relative_to(
                svc["files"].project_root(user.user_id, project_id)
            ).as_posix(),
            "area": "uploads",
            "is_directory": False,
            "size": len(content),
            "modified_at": target.stat().st_mtime,
        }


@router.post("/tasks/{sid}/files", status_code=201)
async def upload_file(
    sid: str,
    request: Request,
    area: str = "uploads",
    path: str = "",
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    return await upload_project_file(
        await session_project_id(request, user, sid), request, area, path, file, user
    )


@router.post("/projects/{project_id}/deliver", status_code=201)
async def project_deliver(
    project_id: str, body: DeliveryWrite, request: Request, user=Depends(current_user)
):
    svc = services(request)
    async with svc["projects"].guard(user, project_id):
        changes = svc["file_changes"]
        await changes.observe_safe(user.user_id, project_id)
        async with changes.locked([project_id]):
            target = await asyncio.to_thread(
                svc["files"].deliver, user.user_id, project_id, body.path
            )
        await changes.observe_safe(user.user_id, project_id)
        return {
            "path": target.relative_to(
                svc["files"].area_root(user.user_id, project_id, "artifacts")
            ).as_posix(),
            "area": "artifacts",
        }


@router.post("/tasks/{sid}/deliver", status_code=201)
async def deliver(
    sid: str, body: DeliveryWrite, request: Request, user=Depends(current_user)
):
    return await project_deliver(
        await session_project_id(request, user, sid), body, request, user
    )


@router.get("/preferences")
async def preferences(request: Request, user=Depends(current_user)):
    return await services(request)["preferences"].read(user)


@router.put("/preferences")
async def update_preferences(
    body: PreferencesWrite, request: Request, user=Depends(current_user)
):
    return await services(request)["preferences"].save(user, body.model_dump())


@router.post("/share-requests", status_code=201)
async def request_share(body: ShareWrite, request: Request, user=Depends(current_user)):
    return await services(request)["sharing"].submit(
        user, body.resource_type, body.resource_id, body.resource_version
    )


@router.get("/share-requests")
async def list_shares(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["sharing"].list(user)}


@router.get("/admin/users")
async def users(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["users"].list_users(user)}


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str, body: User, request: Request, user=Depends(current_user)
):
    if user_id != body.user_id:
        raise Forbidden("用户标识不可修改")
    return await services(request)["users"].update_user(user, body)


@router.get("/admin/groups")
async def groups(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["users"].list_groups(user)}


@router.post("/admin/groups")
@router.put("/admin/groups/{group_id}")
async def save_group(
    body: Group,
    request: Request,
    group_id: str | None = None,
    user=Depends(current_user),
):
    if group_id is not None and group_id != body.group_id:
        raise Forbidden("分组标识不可修改")
    return await services(request)["users"].save_group(user, body)


@router.get("/admin/grants")
async def grants(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["permissions"].list_grants(user)}


@router.post("/admin/grants")
async def grant(body: Grant, request: Request, user=Depends(current_user)):
    if body.grant_source_type != "manual":
        raise Forbidden("共享授权只能由审核用例创建")
    return await services(request)["permissions"].grant(user, body)


@router.delete("/admin/grants/{identifier}", status_code=204)
async def revoke_grant(identifier: str, request: Request, user=Depends(current_user)):
    await services(request)["permissions"].revoke(user, identifier)
    return Response(status_code=204)


@router.get("/admin/share-reviews")
async def share_reviews(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["sharing"].list(user, admin=True)}


@router.post("/admin/share-reviews/{identifier}/decision")
async def decide_share(
    identifier: str, body: DecisionWrite, request: Request, user=Depends(current_user)
):
    return await services(request)["sharing"].decide(
        user, identifier, body.is_approved, body.reason
    )


@router.get("/admin/packages")
async def packages(request: Request, user=Depends(current_user)):
    return {"items": await services(request)["packages"].list(user)}


@router.post("/admin/packages")
async def load_package(body: dict, request: Request, user=Depends(current_user)):
    require_admin(user)
    from urllib.parse import unquote, urlparse

    path = body.get("package_path") or unquote(
        urlparse(body.get("download_url", "")).path
    )
    if not path:
        raise HTTPException(400, "必须提供发布目录")
    return await services(request)["packages"].register(
        user,
        Path(path),
        checksum=body.get("checksum_sha256") or None,
        entrypoint=body.get("entrypoint"),
        owner_id=body.get("owner_id", "egis-demo"),
    )


@router.delete("/admin/packages/{identifier}", status_code=204)
async def disable_package(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    await services(request)["packages"].disable(user, identifier, version)
    return Response(status_code=204)


def add_resource_routes():
    for path, resource_type in (("skills", "skill"), ("connectors", "mcp")):

        def endpoints(kind):
            async def listing(request: Request, user=Depends(current_user)):
                return {"items": await services(request)["resources"].list(user, kind)}

            async def detail(
                identifier: str,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request)["resources"].detail(
                    user, kind, identifier, version
                )

            async def save(
                body: dict,
                request: Request,
                identifier: str | None = None,
                user=Depends(current_user),
            ):
                if identifier:
                    body = {**body, "resource_id": identifier}
                service = services(request)["resources"]
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
                return await services(request)["resources"].install(
                    user, kind, identifier, version
                )

            async def toggle(
                identifier: str,
                body: InstallWrite,
                request: Request,
                version: str = Query(...),
                user=Depends(current_user),
            ):
                return await services(request)["resources"].set_installation(
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


@router.post("/skills/upload", status_code=201)
async def upload_skill(
    request: Request,
    file: UploadFile = File(...),
    version: str = Query(...),
    user=Depends(current_user),
):
    maximum = services(request)["files"].max_bytes
    return await services(request)["resources"].upload_skill(
        user, await file.read(maximum + 1), version
    )


@router.get("/skills/{identifier}/download")
async def download_skill(
    identifier: str,
    request: Request,
    version: str = Query(...),
    user=Depends(current_user),
):
    content = await services(request)["resources"].download_skill(
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
    return await services(request)["resources"].test_mcp(user, identifier, version)


add_resource_routes()


@router.get("/workspace/preview")
async def preview_user_document(
    request: Request, path: str, user=Depends(current_user)
):
    content, _ = services(request)["files"].read_user(user.user_id, path)
    result = await services(request)["preview"].convert(content, path)
    return file_response(result, "application/pdf", Path(path).stem + ".pdf")


@router.get("/projects/{project_id}/preview")
async def preview_project_document(
    project_id: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    svc = services(request)
    async with svc["projects"].guard(user, project_id):
        content, _ = await asyncio.to_thread(
            svc["files"].read, user.user_id, project_id, area, path
        )
        result = await svc["preview"].convert(content, path)
        return file_response(result, "application/pdf", Path(path).stem + ".pdf")


@router.get("/tasks/{sid}/preview")
async def preview_task_document(
    sid: str, request: Request, area: str, path: str, user=Depends(current_user)
):
    return await preview_project_document(
        await session_project_id(request, user, sid), request, area, path, user
    )
