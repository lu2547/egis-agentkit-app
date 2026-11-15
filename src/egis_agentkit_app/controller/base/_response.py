"""Shared HTTP response formatting, without service orchestration."""

import asyncio
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Response


async def run_until_disconnect(request, operation):
    """预览请求被关闭或被更新版本替换时，回收其转换任务；不轮询计时。"""

    async def disconnected():
        while (await request.receive())["type"] != "http.disconnect":
            pass

    pending = asyncio.create_task(operation)
    disconnect = asyncio.create_task(disconnected())
    try:
        finished, _ = await asyncio.wait(
            {pending, disconnect}, return_when=asyncio.FIRST_COMPLETED
        )
        if pending in finished:
            return await pending
        raise HTTPException(status_code=499, detail="预览请求已取消")
    finally:
        for task in (pending, disconnect):
            if not task.done():
                task.cancel()
        await asyncio.gather(pending, disconnect, return_exceptions=True)


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


def saved_definition(row):
    """返回新发布定义的精确版本和所属视图。"""
    return {
        **row,
        "resource_version": row["resource_version"],
        "resource_view_type": "system" if row["owner_type"] == "system" else "private",
        "is_editable": True,
    }
