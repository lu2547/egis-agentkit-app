"""Provision only named local demo configuration; never print secret values."""

import asyncio
import os
import secrets
from pathlib import Path

import yaml
from dotenv import dotenv_values, load_dotenv, set_key
from sqlalchemy.engine import URL

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
    database_url = URL.create(
        "postgresql+asyncpg",
        username=pg["POSTGRES_USER"],
        password=pg["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=5433,
        database=pg["POSTGRES_DB"],
    ).render_as_string(hide_password=False)
    values = {
        "NACOS_SERVER_URL": "http://127.0.0.1:8848",
        "NACOS_CONSOLE_URL": "http://127.0.0.1:8080",
        "NACOS_IDENTITY_KEY": "agentkit",
        "NACOS_IDENTITY_VALUE": "agentkit-dev",
        "AGENTKIT_DATABASE_URL": database_url,
        "AGENTKIT_JWT_SECRET": secrets.token_urlsafe(48),
        "AGENTKIT_DOWNLOAD_SECRET": secrets.token_urlsafe(48),
        "AGENTKIT_DEMO_PASSWORD": secrets.token_urlsafe(24),
        "AGENTKIT_MODEL_API_KEY": demo.get("API_KEY", ""),
    }
    for key, value in values.items():
        if key not in existing and value:
            set_key(str(env_path), key, str(value))
    load_dotenv(env_path)
    from egis_agentkit.config import NacosClient, NacosConfigProvider

    from egis_agentkit_app.bootstrap import nacos_bootstrap

    version = 1
    runtime = {
        "config_version": version,
        "database_url_env": "AGENTKIT_DATABASE_URL",
        "workspace_root": str(APP / "var/workspace"),
        "release_roots": [str(ROOT / "demo/agentscope-demo/agentkit_demo/releases")],
        "workspace_mode": "local",
        "deployment_mode": "cluster",
        "kafka_bootstrap_servers": ["127.0.0.1:9092"],
        "kafka_topic_prefix": "egis-agentkit",
        "download_secret_env": "AGENTKIT_DOWNLOAD_SECRET",
        "auth": {
            "mode": "demo",
            "issuer": "egis-agentkit-demo",
            "audience": "egis-agentkit",
            "algorithm": "HS256",
        },
    }
    models = {
        "config_version": version,
        "default_key": "company",
        "models": [
            {
                "key": "company",
                "display_name": "公司模型服务",
                "model": demo.get("MODEL_NAME") or "configured-company-model",
                "base_url": demo.get("LLM_BASE_URL"),
                "api_key_env": "AGENTKIT_MODEL_API_KEY",
                "credential_type": "openai_credential",
                "model_class": "openai_chat",
                "parameters": {},
            }
        ],
    }
    policies = {
        "config_version": version,
        "allow_private_self_use": True,
        "allow_personal_self_use": True,
        "allow_model_override": True,
        "allowed_model_keys": ["company"],
        "max_upload_bytes": 20 * 1024 * 1024,
        "max_skill_archive_bytes": 50 * 1024 * 1024 - 1,
    }
    async with NacosClient(nacos_bootstrap()) as client:
        for kind, config in (
            ("runtime", runtime),
            ("models", models),
            ("policies", policies),
        ):
            data_id = f"agentkit-{kind}.yaml"
            # Inspect the actual response code; a network/auth error is not
            # permission to overwrite an existing configuration.
            response = await client.http.get(
                client.bootstrap.server_url + "/nacos/v3/client/cs/config",
                params={
                    "namespaceId": client.bootstrap.namespace_id,
                    "groupName": client.bootstrap.group,
                    "dataId": data_id,
                },
                headers=client._headers(),
            )
            response.raise_for_status()
            envelope = response.json()
            if envelope.get("code") == 20004:
                await client.publish_config(
                    data_id, yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
                )
                print(f"Created Nacos {data_id}")
            elif envelope.get("code") == 0:
                print(f"Preserved existing Nacos {data_id}")
            else:
                raise RuntimeError(
                    "Nacos configuration lookup failed; nothing overwritten"
                )
        provider = NacosConfigProvider(client)
        await provider.refresh()
        print(f"Validated Nacos configuration batch {provider.snapshot.config_version}")
    print(
        f"Deployment secrets saved with mode0600 to {env_path}; no secret values printed"
    )


if __name__ == "__main__":
    asyncio.run(main())
