"""用户、组织组、偏好与登录接口。"""

from ._identity import router as identity_router
from ._user import router

__all__ = ["router", "identity_router"]
