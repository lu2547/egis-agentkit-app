import argparse
import asyncio
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap

from ._init import build_app


async def serve(host, port):
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        await provider.refresh()
        app = await build_app(provider, client, owns_client=False)
        await uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="info", access_log=True)
        ).serve()


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["serve", "init-db", "seed", "cleanup-db", "upgrade-db"],
        default="serve",
        nargs="?",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38092)
    parser.add_argument(
        "--apply", action="store_true", help="应用升级或清理，默认只预览"
    )
    parser.add_argument("--database", help="预期连接的数据库名")
    args = parser.parse_args()
    if args.command not in {"cleanup-db", "upgrade-db"} and (
        args.apply or args.database is not None
    ):
        parser.error("--apply 和 --database 仅用于 cleanup-db 或 upgrade-db")
    if args.apply and not args.database:
        parser.error("执行升级或清理时必须指定 --database")
    if args.command == "serve":
        asyncio.run(serve(args.host, args.port))
    else:
        from ._provision import provision

        try:
            asyncio.run(
                provision(args.command, database=args.database, apply=args.apply)
            )
        except ValueError as exc:
            if args.command not in {"cleanup-db", "upgrade-db"}:
                raise
            parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
