import argparse
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from egis_agentkit.client._logging import configure_process_logging
from egis_agentkit.client.nacos import (
    NacosClient,
    NacosConfigProvider,
    NacosError,
    nacos_bootstrap,
)
from egis_agentkit.client.nacos._settings import LoggingConfig
from egis_agentkit.errors import AgentKitError

logger = logging.getLogger(__name__)


async def serve(host, port):
    configure_process_logging(LoggingConfig())
    from ._init import build_app

    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        configure_process_logging(provider.snapshot.logging)
        app = await build_app(provider, client, owns_client=False, manage_logging=False)
        await uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_config=None,
                access_log=False,
            )
        ).serve()


async def serve_files(host, port):
    if sys.platform != "linux":
        raise ValueError("serve-files 必须在挂载 NAS 的 Linux 主机运行")

    from egis_agentkit.storage._nas_service import create_nas_file_app

    configure_process_logging(LoggingConfig())
    async with NacosClient(nacos_bootstrap()) as client:
        snapshot = await NacosConfigProvider(client).refresh()
    configure_process_logging(snapshot.logging)
    for path in (snapshot.workspace.runtime.root, snapshot.skill.storage.root):
        if not path or not Path(path).is_dir() or Path(path).resolve() != Path(path):
            raise ValueError("serve-files 需要已初始化的 NAS 工作区和技能上传目录")
    await uvicorn.Server(
        uvicorn.Config(
            create_nas_file_app(snapshot),
            host=host,
            port=port,
            log_config=None,
            access_log=False,
        )
    ).serve()


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["serve", "serve-files", "provision-admin"],
        default="serve",
        nargs="?",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--user-id", help="已登录并登记的平台用户 ID")
    args = parser.parse_args()
    if args.command == "provision-admin":
        if not args.user_id:
            parser.error("provision-admin 必须指定 --user-id")
    elif args.user_id is not None:
        parser.error("--user-id 仅用于 provision-admin")
    port = args.port
    if port is None:
        port = 38093 if args.command == "serve-files" else 38092
    if args.command == "serve":
        try:
            asyncio.run(serve(args.host, port))
        except Exception:
            logger.exception("AgentKit server failed to start")
            parser.exit(1)
    elif args.command == "serve-files":
        try:
            asyncio.run(serve_files(args.host, port))
        except (NacosError, ValueError) as exc:
            logger.exception("AgentKit file server failed to start")
            parser.exit(1, f"{exc}\n")
        except OSError:
            logger.exception("AgentKit file server failed to start")
            parser.exit(1)
    else:
        from ._provision import provision_admin

        try:
            asyncio.run(provision_admin(args.user_id))
        except AgentKitError as exc:
            parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
