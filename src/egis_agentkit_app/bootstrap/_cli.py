import argparse
import asyncio
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from egis_agentkit.client.nacos import (
    NacosClient,
    NacosConfigProvider,
    NacosError,
    nacos_bootstrap,
)
from egis_agentkit.errors import AgentKitError

DATABASE_COMMANDS = {"cleanup-db", "upgrade-db", "reset-skills"}


async def serve(host, port):
    from ._init import build_app

    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        app = await build_app(provider, client, owns_client=False)
        await uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level=provider.snapshot.logging.level.lower(),
                access_log=provider.snapshot.logging.access_log,
            )
        ).serve()


async def serve_files(host, port):
    if sys.platform != "linux":
        raise ValueError("serve-files 必须在挂载 NAS 的 Linux 主机运行")

    from egis_agentkit.storage._nas_service import create_nas_file_app

    async with NacosClient(nacos_bootstrap()) as client:
        snapshot = await NacosConfigProvider(client).refresh()
    for path in (snapshot.workspace.runtime.root, snapshot.skill.storage.root):
        if not path or not Path(path).is_dir() or Path(path).resolve() != Path(path):
            raise ValueError("serve-files 需要已初始化的 NAS 工作区和技能上传目录")
    await uvicorn.Server(
        uvicorn.Config(
            create_nas_file_app(snapshot),
            host=host,
            port=port,
            log_level=snapshot.logging.level.lower(),
            access_log=False,
        )
    ).serve()


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "serve",
            "serve-files",
            "init-db",
            "seed",
            "provision-admin",
            "provision-skill-assistant",
            "cleanup-db",
            "upgrade-db",
            "reset-skills",
        ],
        default="serve",
        nargs="?",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--apply", action="store_true", help="应用升级或清理，默认只预览"
    )
    parser.add_argument("--database", help="预期连接的数据库名")
    parser.add_argument("--user-id", help="已登录并登记的平台用户 ID")
    args = parser.parse_args()
    if args.command not in DATABASE_COMMANDS and (
        args.apply or args.database is not None
    ):
        parser.error("--apply 和 --database 仅用于数据库维护命令")
    if args.apply and not args.database:
        parser.error("执行升级或清理时必须指定 --database")
    if args.command in {"seed", "provision-admin"}:
        if not args.user_id:
            parser.error("seed 和 provision-admin 必须指定 --user-id")
    elif args.user_id is not None:
        parser.error("--user-id 仅用于 seed 和 provision-admin")
    port = args.port
    if port is None:
        port = 38093 if args.command == "serve-files" else 38092
    if args.command == "serve":
        asyncio.run(serve(args.host, port))
    elif args.command == "serve-files":
        try:
            asyncio.run(serve_files(args.host, port))
        except (NacosError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
    else:
        from ._provision import provision

        try:
            asyncio.run(
                provision(
                    args.command,
                    database=args.database,
                    apply=args.apply,
                    user_id=args.user_id,
                )
            )
        except AgentKitError as exc:
            parser.exit(1, f"{exc}\n")
        except ValueError as exc:
            if args.command not in DATABASE_COMMANDS:
                raise
            parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
