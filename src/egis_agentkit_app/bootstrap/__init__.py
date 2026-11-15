"""应用装配与命令入口。"""

from egis_agentkit.client.nacos import nacos_bootstrap

from ._cli import main
from ._init import build_app

__all__ = ["build_app", "main", "nacos_bootstrap"]
