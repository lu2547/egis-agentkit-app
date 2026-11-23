"""统一聊天触发与运行中引导的 HTTP 入口。"""

from fastapi import APIRouter

from ._chat import router as chat_router
from ._queue import router as queue_router

router = APIRouter(prefix="/chat", tags=["chat"])
router.include_router(queue_router)
router.include_router(chat_router)

__all__ = ["router"]
