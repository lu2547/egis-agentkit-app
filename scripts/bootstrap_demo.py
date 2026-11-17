"""Provision only named local demo configuration; never print secret values."""

import asyncio
import os
import secrets
from pathlib import Path

import yaml
from dotenv import dotenv_values, load_dotenv, set_key

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "egis/egis-agentkit-app"


async def main():
    env_path = APP / ".env"
    if not env_path.exists():
        descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    os.chmod(env_path, 0o600)
    existing = dotenv_values(env_path)
    pg = dotenv_values(ROOT / "deploy/agentkit-infra/pg.env")
    demo = dotenv_values(ROOT / "demo/agentscope-demo/.env")
    values = {
        "NACOS_SERVER_URL": "http://127.0.0.1:8848",
        "NACOS_CONSOLE_URL": "http://127.0.0.1:8080",
        "NACOS_IDENTITY_KEY": "agentkit",
        "NACOS_IDENTITY_VALUE": "agentkit-dev",
        "AGENTKIT_JWT_SECRET": secrets.token_urlsafe(48),
        "AGENTKIT_DOWNLOAD_SECRET": secrets.token_urlsafe(48),
        "AGENTKIT_DEMO_PASSWORD": secrets.token_urlsafe(24),
        "AGENTKIT_MODEL_API_KEY": demo.get("API_KEY", ""),
    }
    for key, value in values.items():
        if key not in existing and value:
            set_key(str(env_path), key, str(value))
    load_dotenv(env_path)
    from egis_agentkit.client.nacos import (
        AGENTKIT_DATA_ID,
        CONFIG_NOT_FOUND_CODE,
        NacosClient,
        NacosConfigProvider,
        NacosError,
        load_agentkit_config,
    )

    from egis_agentkit_app.bootstrap import nacos_bootstrap

    example = APP.parent / "egis-agentkit-framework/examples/nacos/agentkit.yaml"
    document = yaml.safe_load(example.read_text())
    settings = document["agentkit"]
    settings["client"]["postgres"]["connection"] = {
        "mode": "key",
        "host": "127.0.0.1",
        "port": 5433,
        "database": pg["POSTGRES_DB"],
        "username": pg["POSTGRES_USER"],
        "password": pg["POSTGRES_PASSWORD"],
        "connectTimeoutSeconds": 10.0,
        "sslMode": "disable",
    }
    settings["workspace"]["runtime"]["root"] = str(APP / "var/workspace")
    settings["client"]["kafka"]["connection"]["deploymentMode"] = "cluster"
    settings["user"]["identity"].update(
        mode="demo", issuer="egis-agentkit-demo", algorithm="HS256", jwksUrl=None
    )
    settings["model"]["catalog"]["models"][0].update(
        displayName="DeepSeek V4 Flash",
        model="deepseek-v4-flash-0731",
        baseUrl=demo.get("LLM_BASE_URL"),
    )
    content = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    load_agentkit_config(content)
    async with NacosClient(nacos_bootstrap()) as client:
        provider = NacosConfigProvider(client)
        try:
            current = await provider.refresh()
        except NacosError as exc:
            if exc.operation_code != CONFIG_NOT_FOUND_CODE:
                raise
            await client.publish_config(AGENTKIT_DATA_ID, content)
            print(f"Created Nacos {AGENTKIT_DATA_ID}")
            current = await provider.refresh()
        else:
            print(f"Preserved existing Nacos {AGENTKIT_DATA_ID}")
        print(f"Validated Nacos revision {current.revision}")
    print(
        f"Deployment secrets saved with mode0600 to {env_path}; no secret values printed"
    )


if __name__ == "__main__":
    asyncio.run(main())
