import argparse
import asyncio
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from egis_agentkit.config import NacosClient, NacosConfigProvider

from .bootstrap import build_app, nacos_bootstrap


async def serve(host, port):
    client = NacosClient(nacos_bootstrap())
    provider = NacosConfigProvider(client)
    try:
        await provider.refresh()
        app = await build_app(provider, client)
        await uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="info", access_log=True)
        ).serve()
    finally:
        await provider.close()
        await client.close()


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["serve", "migrate", "seed"], default="serve", nargs="?"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38092)
    args = parser.parse_args()
    if args.command == "serve":
        asyncio.run(serve(args.host, args.port))
    else:
        from .provision import provision

        asyncio.run(provision(args.command))


if __name__ == "__main__":
    main()
