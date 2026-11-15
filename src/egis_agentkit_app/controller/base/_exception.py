"""将 Framework 异常转换成 HTTP 响应。"""

from egis_agentkit.client.nacos import NacosError
from egis_agentkit.errors import AgentKitError, UploadNameConflict
from fastapi.responses import JSONResponse


def register_exception_handlers(app):
    @app.exception_handler(AgentKitError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(UploadNameConflict)
    async def upload_conflict(request, exc):
        return JSONResponse(
            {"detail": str(exc), "code": "upload_name_conflict"},
            status_code=exc.status_code,
        )

    @app.exception_handler(NacosError)
    async def nacos_error(request, exc):
        return JSONResponse(
            {"detail": str(exc)}, status_code=getattr(exc, "status_code", 502)
        )

    @app.exception_handler(ValueError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)
