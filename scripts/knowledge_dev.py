"""启动独立的知识库接入环境，复用基础设施并隔离应用数据和消息主题。

核心能力
- prepare：复制已验证的基础配置到独立 Nacos 组，创建专用数据库和 NAS 前缀。
- start：启动独立 API/前端；契约服务仅在 --contract-preview 显式选择时启用。
- status / stop：只检查、停止本脚本记录且启动时间仍匹配的进程。
密钥只保存在受保护的 .runtime/secrets.env，不写 Nacos 正文或终端。
"""

import argparse
import asyncio
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml
from dotenv import dotenv_values, load_dotenv
from egis_agentkit.client._postgres import create_postgres_engine
from egis_agentkit.client.nacos import NacosClient, NacosConfigProvider, nacos_bootstrap
from egis_agentkit.client.nacos._config import load_agentkit_config
from egis_agentkit.core.message_bus import EgisMessageBus
from egis_agentkit.service._user import UserService
from egis_agentkit.storage import AgentKitStorage
from egis_agentkit.storage.model import Group
from sqlalchemy import text
from sqlalchemy.engine import make_url

APP_ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = APP_ROOT.parent
FRAMEWORK_ROOT = DEV_ROOT / "framework"
FRONTEND_ROOT = DEV_ROOT / "frontend"
RUNTIME = DEV_ROOT / ".runtime"
STATE = RUNTIME / "state.json"
GROUP_ID = "knowledge-acceptance"
DATABASE_MARKER = "agentkit-knowledge-isolated:" + str(DEV_ROOT)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status", "stop"))
    parser.add_argument("--base-env", type=Path)
    parser.add_argument("--source-group", default="EGIS_AGENTKIT")
    parser.add_argument("--group", default="EGIS_AGENTKIT_KNOWLEDGE")
    parser.add_argument("--database", default="agentscope_knowledge")
    parser.add_argument("--api-port", type=int, default=38096)
    parser.add_argument("--frontend-port", type=int, default=5189)
    parser.add_argument("--contract-port", type=int, default=38097)
    parser.add_argument("--startup-timeout", type=float, default=120.0)
    parser.add_argument("--contract-preview", action="store_true")
    parser.add_argument("--java-url")
    parser.add_argument("--app-id")
    parser.add_argument("--secret-env", default="AGENTKIT_KNOWLEDGE_SECRET")
    parser.add_argument("--kb-id", action="append", default=[])
    parser.add_argument("--file-origin", action="append", default=[])
    args = parser.parse_args()
    if args.command == "start":
        if args.base_env is None or not args.base_env.is_file():
            parser.error("start 必须用 --base-env 指定现有开发配置文件")
        if args.group == args.source_group:
            parser.error("开发组不能与来源 Nacos 组相同")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", args.database):
            parser.error("数据库名仅允许小写字母、数字和下划线")
        if not args.contract_preview and not (
            args.java_url and args.app_id and args.kb_id
        ):
            parser.error(
                "必须显式选择 --contract-preview，或提供 --java-url / --app-id / --kb-id"
            )
        if args.contract_preview and args.java_url:
            parser.error("契约验收和真实 Java 连接不能同时选择")
    return args


def process_stamp(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def owned_processes():
    if not STATE.is_file():
        return []
    return [
        entry
        for entry in json.loads(STATE.read_text()).get("processes", [])
        if process_stamp(entry["pid"]) == entry["stamp"] and entry["stamp"]
    ]


def stop():
    entries = owned_processes()
    for entry in reversed(entries):
        try:
            os.killpg(entry["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    print(f"已向 {len(entries)} 个独立环境进程组发送停止信号；持久数据保留。")


async def status():
    if not STATE.is_file():
        print("独立环境尚未启动")
        return
    data = json.loads(STATE.read_text())
    checks = {
        "api_url": data["api_url"],
        "frontend_url": data["frontend_url"],
        "owned_processes": len(owned_processes()),
        "mode": data["mode"],
    }
    async with httpx.AsyncClient(timeout=3) as client:
        try:
            checks["ready"] = (
                (await client.get(data["api_url"] + "/health/ready"))
                .json()
                .get("is_ready", False)
            )
        except (httpx.HTTPError, ValueError):
            checks["ready"] = False
    print(json.dumps(checks, ensure_ascii=False, indent=2))


def private_environment(args):
    os.umask(0o077)
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / "logs").mkdir(exist_ok=True)
    load_dotenv(args.base_env)
    path = RUNTIME / "secrets.env"
    if not path.exists():
        values = {
            name: secrets.token_urlsafe(48)
            for name in (
                "AGENTKIT_KB_JWT_SECRET",
                "AGENTKIT_KB_DOWNLOAD_SECRET",
                "AGENTKIT_KNOWLEDGE_SECRET",
                "AGENTKIT_KNOWLEDGE_FIXTURE_COOKIE_SECRET",
            )
        }
        path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        path.chmod(0o600)
    values = {
        key: value for key, value in dotenv_values(path).items() if value is not None
    }
    env = dict(os.environ)
    env["AGENTKIT_KB_JWT_SECRET"] = values["AGENTKIT_KB_JWT_SECRET"]
    env["AGENTKIT_KB_DOWNLOAD_SECRET"] = values["AGENTKIT_KB_DOWNLOAD_SECRET"]
    if args.contract_preview:
        env.update(values)
        env["AGENTKIT_KNOWLEDGE_APP_ID"] = "agentkit-contract"
        env["AGENTKIT_KB_CONTRACT_DIR"] = str(APP_ROOT / "tests/contracts/documents")
    elif not env.get(args.secret_env):
        raise ValueError("真实 Java 接入所需的 HMAC Secret 环境变量未配置")
    env["PYTHONPATH"] = os.pathsep.join(
        (str(FRAMEWORK_ROOT / "src"), str(APP_ROOT / "src"))
    )
    return env


async def isolated_database(source_url, database, pool):
    source = make_url(source_url)
    if database == source.database:
        raise ValueError("开发数据库不能与来源数据库相同")
    admin = create_postgres_engine(
        source.set(database="postgres").render_as_string(hide_password=False),
        pool_size=pool.size,
        max_overflow=pool.max_overflow,
    )
    try:
        async with admin.connect() as raw:
            connection = await raw.execution_options(isolation_level="AUTOCOMMIT")
            current = (
                await connection.execute(
                    text("SELECT oid FROM pg_database WHERE datname=:name"),
                    {"name": database},
                )
            ).scalar()
            if current is None:
                await connection.execute(text(f'CREATE DATABASE "{database}"'))
                escaped = DATABASE_MARKER.replace("'", "''")
                await connection.execute(
                    text(f"COMMENT ON DATABASE \"{database}\" IS '{escaped}'")
                )
            else:
                marker = await connection.scalar(
                    text(
                        "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=:name"
                    ),
                    {"name": database},
                )
                if marker != DATABASE_MARKER:
                    raise ValueError("同名数据库不属于当前独立目录，拒绝复用")
    finally:
        await admin.dispose()
    return source.set(database=database).render_as_string(hide_password=False)


async def prepare(args, env):
    source_bootstrap = nacos_bootstrap().model_copy(update={"group": args.source_group})
    target_bootstrap = source_bootstrap.model_copy(update={"group": args.group})
    async with NacosClient(source_bootstrap) as source_client:
        source = load_agentkit_config(await source_client.get_config("agentkit.yaml"))
    config = source.model_dump(mode="json", by_alias=True)
    # 1. 开发数据使用 NAS 独立前缀，继续复用现有 OpenSandbox 服务和路径白名单。
    prefix = "knowledge-integration"
    workspace_root = Path(source.workspace.runtime.root) / prefix
    workspace_root.mkdir(exist_ok=True)
    link = RUNTIME / "workspace"
    if link.is_symlink() and link.resolve() != workspace_root.resolve():
        raise ValueError("独立环境工作区链接指向其他数据，拒绝覆盖")
    if not link.exists():
        link.symlink_to(workspace_root, target_is_directory=True)
    config["workspace"]["runtime"]["root"] = str(workspace_root)
    config["workspace"]["runtime"]["opensandbox"]["hostRoot"] = str(
        Path(source.workspace.runtime.opensandbox.host_root) / prefix
    )
    config["skill"]["storage"]["root"] = str(workspace_root / "skill-archives")
    config["project"]["preview"]["cache"]["root"] = str(RUNTIME / "preview-cache")
    config["agent"]["personal"]["memory"]["isEnabled"] = False
    config["user"]["identity"].update(
        signingSecretEnv="AGENTKIT_KB_JWT_SECRET",
        issuer=source.user.identity.issuer + "-knowledge",
        audience=source.user.identity.audience + "-knowledge",
    )
    config["project"]["download"]["secretEnv"] = "AGENTKIT_KB_DOWNLOAD_SECRET"
    config["client"]["kafka"]["connection"]["topicPrefix"] = (
        source.client.kafka.connection.topic_prefix + "-knowledge"
    )
    config["client"]["kafka"]["connection"]["consumerGroup"] = (
        source.client.kafka.connection.consumer_group + "-knowledge"
    )
    pg_env = source.client.postgres.connection.url_env
    env[pg_env] = await isolated_database(
        env[pg_env], args.database, source.client.postgres.pool
    )
    env["NACOS_GROUP"] = args.group
    # 2. 生产路径调用 Java；验收服务必须显式选择，不存在本地检索回退。
    java_url = (
        f"http://127.0.0.1:{args.contract_port}/knowledge"
        if args.contract_preview
        else args.java_url
    )
    kb_ids = ["kb_contract_docs"] if args.contract_preview else args.kb_id
    config["knowledge"] = {
        "enabled": True,
        "label": "接口契约验收环境" if args.contract_preview else "企业知识库",
        "connection": {
            "baseUrl": java_url,
            "appId": "agentkit-contract" if args.contract_preview else args.app_id,
            "secretEnv": "AGENTKIT_KNOWLEDGE_SECRET"
            if args.contract_preview
            else args.secret_env,
        },
        "access": {
            "grants": [
                {"principalType": "group", "principalId": GROUP_ID, "kbIds": kb_ids}
            ]
        },
        "documents": {
            "publicBaseUrl": "/knowledge",
            "allowedFileOrigins": args.file_origin,
        },
    }
    if config["tool"]["defaults"]["registeredIds"] is not None:
        config["tool"]["defaults"]["registeredIds"] = sorted(
            set(config["tool"]["defaults"]["registeredIds"]) | {"SearchKnowledge"}
        )
    async with NacosClient(target_bootstrap) as client:
        from egis_agentkit.client.nacos._client import CONFIG_NOT_FOUND_CODE, NacosError

        try:
            existing = load_agentkit_config(await client.get_config("agentkit.yaml"))
            if existing.workspace.runtime.root != str(workspace_root):
                raise ValueError("目标 Nacos 组已经用于其他环境，拒绝覆盖")
            revision = existing.revision + 1
        except NacosError as error:
            if error.operation_code != CONFIG_NOT_FOUND_CODE:
                raise
            revision = 1
        config["revision"] = revision
        content = yaml.safe_dump(
            {"agentkit": config}, allow_unicode=True, sort_keys=False
        )
        validated = load_agentkit_config(content)
        await client.publish_config("agentkit.yaml", content)
        deadline = time.monotonic() + args.startup_timeout
        while True:
            try:
                if (
                    load_agentkit_config(await client.get_config("agentkit.yaml"))
                    == validated
                ):
                    break
            except NacosError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("等待独立 Nacos 配置生效超时")
            await asyncio.sleep(0.5)
        provider = NacosConfigProvider(client)
        await provider.refresh()
        # 3. 只在专用数据库初始化原生 AgentKit 表；不执行或创建 llm_* 业务表。
        engine = create_postgres_engine(
            env[pg_env],
            pool_size=validated.client.postgres.pool.size,
            max_overflow=validated.client.postgres.pool.max_overflow,
        )
        try:
            storage = AgentKitStorage(env[pg_env], engine)
            await storage.init_schema()
            async with storage:
                users = UserService(storage)
                for uid, name in [
                    ("demo.admin", "知识库验收管理员"),
                    ("demo.user", "知识库验收用户"),
                ]:
                    await users.sync_identity(uid, name)
                await users.provision_admin(
                    "demo.admin", actor="knowledge-dev-bootstrap"
                )
                admin = await users.get("demo.admin")
                await users.save_group(
                    admin, Group(group_id=GROUP_ID, group_name="知识库接入验收")
                )
                for uid in ("demo.admin", "demo.user"):
                    user = await users.get(uid)
                    await users.update_user(
                        admin, user.model_copy(update={"group_ids": [GROUP_ID]})
                    )
            bus = EgisMessageBus(engine=engine, kafka=validated.client.kafka)
            await bus.init_schema()
            await bus.ensure_topics()
        finally:
            await engine.dispose()
    env["KNOWLEDGE_API_URL"] = java_url
    env["APP_API_URL"] = f"http://127.0.0.1:{args.api_port}"
    env["VITE_CACHE_DIR"] = str(RUNTIME / "vite-cache")
    return env, workspace_root


def launch(name, command, cwd, env):
    log = RUNTIME / "logs" / (name + ".log")
    with log.open("ab") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return {"name": name, "pid": process.pid, "stamp": process_stamp(process.pid)}


async def wait_ready(url, timeout):
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=3) as client:
        while time.monotonic() < deadline:
            try:
                if (await client.get(url)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("服务未就绪，请查看独立目录 .runtime/logs")


async def start(args):
    for port in [args.api_port, args.frontend_port] + (
        [args.contract_port] if args.contract_preview else []
    ):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError(f"端口 {port} 已被占用，请先检查独立环境状态")
    env = private_environment(args)
    env, workspace_root = await prepare(args, env)
    processes = []
    try:
        if args.contract_preview:
            processes.append(
                launch(
                    "contract-java",
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "java_kb_server:app",
                        "--app-dir",
                        str(APP_ROOT / "tests/contracts"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(args.contract_port),
                    ],
                    APP_ROOT,
                    env,
                )
            )
            await wait_ready(
                f"http://127.0.0.1:{args.contract_port}/knowledge/__contract/health",
                args.startup_timeout,
            )
        processes.append(
            launch(
                "api",
                [
                    sys.executable,
                    "-m",
                    "egis_agentkit_app",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.api_port),
                ],
                APP_ROOT,
                env,
            )
        )
        processes.append(
            launch(
                "frontend",
                [
                    "npm",
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.frontend_port),
                    "--strictPort",
                ],
                FRONTEND_ROOT,
                env,
            )
        )
        data = {
            "api_url": env["APP_API_URL"],
            "knowledge_url": env["KNOWLEDGE_API_URL"],
            "frontend_url": f"http://127.0.0.1:{args.frontend_port}",
            "processes": processes,
            "mode": "contract-acceptance" if args.contract_preview else "java",
            "database": args.database,
            "group": args.group,
            "workspace_root": str(workspace_root),
        }
        STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        STATE.chmod(0o600)
        await wait_ready(data["api_url"] + "/health/ready", args.startup_timeout)
        await wait_ready(data["frontend_url"], args.startup_timeout)
        print(
            json.dumps(
                data | {"processes": [entry["name"] for entry in processes]},
                ensure_ascii=False,
                indent=2,
            )
        )
    except BaseException:
        for entry in reversed(processes):
            if process_stamp(entry["pid"]) == entry["stamp"]:
                try:
                    os.killpg(entry["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    pass
        raise


if __name__ == "__main__":
    options = arguments()
    if options.command == "start":
        asyncio.run(start(options))
    elif options.command == "status":
        asyncio.run(status())
    else:
        stop()
