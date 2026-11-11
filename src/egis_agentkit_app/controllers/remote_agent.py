"""Third-party callbacks authenticated by their registered connection."""

import re

from egis_agentkit.service.agent._remote_base import CALLBACK_PATH
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
callback_path = re.compile(rf"{CALLBACK_PATH}/[a-zA-Z0-9_-]{{1,64}}/result")


@router.post(f"{CALLBACK_PATH}/{{run_id}}/result", tags=["remote-agents"])
async def remote_agent_result(run_id: str, request: Request):
    if not callback_path.fullmatch(request.scope["path"]):
        raise HTTPException(404, "远程任务不存在")
    service = request.app.state.egis_remote_agents
    maximum = service.settings.callback.max_bytes
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum:
            raise HTTPException(413, "远程回包过大")
    return {
        "status": await service.accept_callback(run_id, request.headers, bytes(body))
    }
