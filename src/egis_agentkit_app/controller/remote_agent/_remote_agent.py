"""Third-party callbacks authenticated by their registered connection."""

from egis_agentkit.client.remote_agent._base import CALLBACK_PATH, CALLBACK_RESULT_PATH
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post(f"{CALLBACK_PATH}/{{run_id}}/result", tags=["remote-agents"])
async def remote_agent_result(run_id: str, request: Request):
    if not CALLBACK_RESULT_PATH.fullmatch(request.scope["path"]):
        raise HTTPException(404, "远程任务不存在")
    service = request.app.state.egis_remote_agents
    maximum = service.settings.callback.max_bytes
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum:
            raise HTTPException(413, "远程回包过大")
    return {
        "status": await service.save_callback_result(
            run_id, request.headers, bytes(body)
        )
    }
