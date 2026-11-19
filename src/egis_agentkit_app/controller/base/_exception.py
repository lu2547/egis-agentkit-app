"""将 Framework 异常转换成 HTTP 响应。"""

import logging

from egis_agentkit.client.nacos import NacosError
from egis_agentkit.errors import (
    AgentKitError,
    CollaborationSessionBusy,
    UploadNameConflict,
)
from egis_agentkit.middleware.http._request_logging import log_http_error
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


def _log(request, description, status, exc, *, system=False):
    log_http_error(
        logger,
        request.scope,
        description,
        status,
        component="register_exception_handlers",
        exc=exc,
        system=system,
    )


def register_exception_handlers(app):
    @app.exception_handler(AgentKitError)
    async def domain_error(request, exc):
        description = (
            "AgentKit operation failed"
            if exc.status_code >= 500
            else "AgentKit operation rejected"
        )
        _log(request, description, exc.status_code, exc)
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(UploadNameConflict)
    async def upload_conflict(request, exc):
        _log(request, "Upload name already exists", exc.status_code, exc)
        return JSONResponse(
            {"detail": str(exc), "code": "upload_name_conflict"},
            status_code=exc.status_code,
        )

    @app.exception_handler(CollaborationSessionBusy)
    async def collaboration_busy(request, exc):
        _log(request, "Collaboration session is busy", exc.status_code, exc)
        return JSONResponse(
            {
                "detail": str(exc),
                "code": exc.code,
                "session_id": exc.session_id,
                "agent_id": exc.agent_id,
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(NacosError)
    async def nacos_error(request, exc):
        _log(request, "Nacos request failed", exc.status_code, exc, system=True)
        return JSONResponse(
            {"detail": str(exc)}, status_code=exc.status_code
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code >= 500:
            _log(request, "HTTP operation failed", exc.status_code, exc)
            return JSONResponse(
                {"detail": "服务暂时不可用"},
                status_code=exc.status_code,
                headers=exc.headers,
            )
        _log(request, "HTTP operation rejected", exc.status_code, exc)
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        _log(request, "HTTP request validation failed", 422, exc)
        return JSONResponse(
            {
                "detail": [
                    {key: item[key] for key in ("type", "loc", "msg")}
                    for item in exc.errors()
                ]
            },
            status_code=422,
        )
