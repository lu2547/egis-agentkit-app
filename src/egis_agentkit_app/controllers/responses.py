"""Shared HTTP response formatting, without service orchestration."""

from pathlib import Path
from urllib.parse import quote

from fastapi import Response


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
        "resource_version": str(row["config_version"]),
        "resource_view_type": "system" if row["owner_type"] == "system" else "private",
        "is_editable": True,
    }
