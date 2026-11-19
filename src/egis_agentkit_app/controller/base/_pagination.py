"""统一读取管理列表的分页请求。"""

from typing import Annotated

from egis_agentkit.client.nacos._settings import AdminPaginationConfig
from egis_agentkit.errors import InvalidRequest
from egis_agentkit.service._admin_page import AdminPage
from fastapi import Depends, Query, Request

MAX_PAGE_NUMBER = 2**31 - 1


def admin_page(
    request: Request,
    page: Annotated[int | None, Query(ge=1, le=MAX_PAGE_NUMBER)] = None,
    page_size: Annotated[int | None, Query(ge=1)] = None,
) -> AdminPage | None:
    if page is None and page_size is None:
        return None
    config = getattr(request.app.state, "egis_config", None)
    settings = (
        config.snapshot.admin.pagination
        if config is not None
        else AdminPaginationConfig()
    )
    size = settings.default_page_size if page_size is None else page_size
    if size > settings.max_page_size:
        raise InvalidRequest(f"每页记录数不能超过 {settings.max_page_size}")
    return AdminPage(number=page or 1, size=size)


AdminPagination = Annotated[AdminPage | None, Depends(admin_page)]
