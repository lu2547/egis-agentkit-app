"""Agent definitions and deployable packages."""

from pathlib import Path
from urllib.parse import unquote, urlparse

from egis_agentkit.models import Definition
from egis_agentkit.service.user.service import require_admin
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..schema import AgentWrite
from ..security import current_user
from .dependencies import services
from .responses import saved_definition

router = APIRouter()


@router.get("/assistant")
async def assistant(request: Request, user=Depends(current_user)):
    row = await services(request).agents.personal(user)
    return {
        **row,
        "resource_view_type": "private",
        "is_usable": True,
        "is_editable": True,
    }


@router.get("/agents")
async def list_agents(request: Request, user=Depends(current_user)):
    return {"items": await services(request).agents.list(user)}


@router.get("/agents/{identifier}")
async def get_agent(
    identifier: str, request: Request, view: str = "private", user=Depends(current_user)
):
    return await services(request).definition_details.get(user, identifier, view, "agent")


async def save_agent(request, user, body, identifier=None):
    values = body.model_dump()
    values["owner_id"] = values["owner_id"] or user.user_id
    if identifier:
        values["id"] = identifier
    return saved_definition(await services(request).agents.save(user, Definition(**values)))


@router.post("/agents", status_code=201)
async def create_agent(body: AgentWrite, request: Request, user=Depends(current_user)):
    return await save_agent(request, user, body)


@router.put("/agents/{identifier}")
async def update_agent(
    identifier: str, body: AgentWrite, request: Request, user=Depends(current_user)
):
    return await save_agent(request, user, body, identifier)


# Both resource kinds use the definition deletion use case; register it once.
@router.delete("/agents/{identifier}", status_code=204)
@router.delete("/teams/{identifier}", status_code=204)
async def delete_definition(
    identifier: str, request: Request, user=Depends(current_user)
):
    await services(request).agents.delete(user, identifier)
    return Response(status_code=204)


@router.get("/admin/packages")
async def packages(request: Request, user=Depends(current_user)):
    return {"items": await services(request).packages.list(user)}


@router.post("/admin/packages")
async def load_package(body: dict, request: Request, user=Depends(current_user)):
    require_admin(user)
    path = body.get("package_path") or unquote(urlparse(body.get("download_url", "")).path)
    if not path:
        raise HTTPException(400, "必须提供发布目录")
    return await services(request).packages.register(
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
    await services(request).packages.disable(user, identifier, version)
    return Response(status_code=204)
