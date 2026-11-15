"""项目、文件、预览及演示文稿 HTTP 接口。"""

from fastapi import APIRouter

from ._file import router as file_router
from ._presentation import router as presentation_router
from ._preview import router as preview_router
from ._project import router as project_router

router = APIRouter()
for component in (project_router, file_router, preview_router, presentation_router):
    router.include_router(component)

__all__ = ["router"]
