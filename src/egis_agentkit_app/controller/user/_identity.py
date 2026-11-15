"""本机演示登录接口；企业令牌由公司身份服务签发。"""

import hmac
import os

from egis_agentkit.errors import AgentKitError
from fastapi import APIRouter, HTTPException, Request

from ..base import services
from ._model import LoginWrite

router = APIRouter()


@router.post("/auth/login", tags=["identity"])
async def demo_login(body: LoginWrite, request: Request):
    identity = request.app.state.egis_identity
    identity_settings = identity.config
    if identity_settings.mode != "demo":
        raise HTTPException(404, "请使用公司统一认证")
    if request.client is None or request.client.host not in (
        "127.0.0.1",
        "::1",
        "testclient",
    ):
        raise HTTPException(403, "演示登录仅对本机开放")
    password = os.environ.get(identity_settings.demo_password_env, "")
    if len(
        password
    ) < identity_settings.demo_min_password_length or not hmac.compare_digest(
        password, body.password
    ):
        raise HTTPException(401, "用户名或密码错误")
    try:
        user = await services(request).users.get(body.user_id)
    except AgentKitError:
        raise HTTPException(401, "用户名或密码错误") from None
    return {
        "access_token": identity.issue(user.user_id, user.username),
        "token_type": "bearer",
        "expires_in": identity_settings.jwt_lifetime_seconds,
    }
