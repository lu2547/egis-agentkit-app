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
    return {
        **row,
        "resource_view_type": "system" if row["owner_type"] == "system" else "private",
        "is_editable": True,
    }
