"""外部系统的技能导入 HTTP 接口。"""

from egis_agentkit.core.skill._avatar import AUTO_AVATAR
from egis_agentkit.service._virtual_user import EXTERNAL_SKILL_IMPORT_PATH
from egis_agentkit.storage.model import User
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from ..base import current_user, services
from ._model import SkillImportJob, SkillImportList

router = APIRouter(prefix=EXTERNAL_SKILL_IMPORT_PATH, tags=["integrations"])


async def _virtual_skill_import_user(
    request: Request, user: User = Depends(current_user)
) -> User:
    if not getattr(request.state, "egis_virtual_user", False):
        raise HTTPException(403, "外部技能导入仅接受虚拟用户凭证")
    return user


@router.post("", status_code=202, response_model=SkillImportJob)
async def upload_external_skill(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("other"),
    avatar: str = Form(AUTO_AVATAR),
    resource_id: str | None = Form(None, max_length=128),
    user: User = Depends(_virtual_skill_import_user),
):
    return await services(request).skill_imports.enqueue(
        user,
        file.file,
        filename=file.filename,
        category=category,
        avatar=avatar,
        virtual=True,
        resource_id=resource_id,
    )


@router.get("", response_model=SkillImportList)
async def list_external_skill_imports(
    request: Request, user: User = Depends(_virtual_skill_import_user)
):
    return {"items": await services(request).skill_imports.list(user)}


@router.get("/{job_id}", response_model=SkillImportJob)
async def get_external_skill_import(
    job_id: str, request: Request, user: User = Depends(_virtual_skill_import_user)
):
    return await services(request).skill_imports.get(user, job_id)


@router.post("/{job_id}/retry", status_code=202, response_model=SkillImportJob)
async def retry_external_skill_import(
    job_id: str, request: Request, user: User = Depends(_virtual_skill_import_user)
):
    return await services(request).skill_imports.retry(user, job_id)
