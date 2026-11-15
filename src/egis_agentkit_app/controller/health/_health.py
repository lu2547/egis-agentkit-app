"""应用就绪检查 HTTP 接口。"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health/ready", tags=["health"])
async def ready(request: Request):
    kit = request.app.state.egis_kit
    config = request.app.state.egis_config
    bus = request.app.state.egis_bus
    await kit.check_database()
    bus_health = bus.health()
    body = {
        "is_ready": bus_health["is_ready"],
        "message_bus": bus_health,
        "config_version": config.snapshot.revision,
        "is_nacos_connected": config.is_connected,
        "restart_required": config.restart_required,
        "deployment_mode": request.app.state.egis_deployment_mode,
    }
    return JSONResponse(body, status_code=200 if body["is_ready"] else 503)
