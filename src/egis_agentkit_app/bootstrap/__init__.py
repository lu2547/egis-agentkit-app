"""应用装配与命令入口。"""

from typing import TYPE_CHECKING

from egis_agentkit.client.nacos import nacos_bootstrap

from ._cli import main

if TYPE_CHECKING:
    from ._init import build_app as build_app

__all__ = ["build_app", "main", "nacos_bootstrap"]


def __getattr__(name):
    if name == "build_app":
        from ._init import build_app

        return build_app
    raise AttributeError(name)
