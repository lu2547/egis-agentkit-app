"""Real App/PG/Nacos/Kafka/model acceptance. No simulated replies or credentials printed."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from agentscope.event import UserConfirmResultEvent
from dotenv import load_dotenv

APP = Path(__file__).resolve().parents[1]


async def run_reply(client, task, prompt, *, allow_write=None, interrupt=False):
    sid, aid = task["session_id"], task["agent_id"]
    events, reasons, confirmations = [], [], 0
    async with client.stream(
        "GET", f"/sessions/{sid}/stream", params={"agent_id": aid}
    ) as stream:
        stream.raise_for_status()
        trigger = await client.post(
            "/chat/",
            json={
                "agent_id": aid,
                "session_id": sid,
                "input": {
                    "role": "user",
                    "name": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            },
        )
        trigger.raise_for_status()
        async with asyncio.timeout(180):
            async for line in stream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                events.append(event)
                kind = event["type"].upper()
                if kind == "REPLY_START" and interrupt:
                    response = await client.post(
                        f"/sessions/{sid}/interrupt", params={"agent_id": aid}
                    )
                    response.raise_for_status()
                    interrupt = False
                if kind == "REQUIRE_USER_CONFIRM":
                    results = []
                    for call in event.get("tool_calls", []):
                        supplied = call.get("input") or {}
                        if isinstance(supplied, str):
                            supplied = json.loads(supplied)
                        approved = call.get("name") == "CreateDemoReport" or (
                            allow_write is not None
                            and call.get("name") == "Write"
                            and Path(supplied.get("file_path", "")).resolve()
                            == allow_write.resolve()
                        )
                        results.append(
                            {"confirmed": approved, "tool_call": call, "rules": None}
                        )
                    payload = UserConfirmResultEvent(
                        reply_id=event["reply_id"], confirm_results=results
                    ).model_dump(mode="json")
                    response = await client.post(
                        "/chat/",
                        json={"agent_id": aid, "session_id": sid, "input": payload},
                    )
                    response.raise_for_status()
                    confirmations += 1
                if kind == "REPLY_END":
                    reason = str(event.get("finished_reason", ""))
                    reasons.append(reason)
                    if reason.upper() not in (
                        "REQUIRE_USER_CONFIRM",
                        "REQUIRE_EXTERNAL_EXECUTION",
                    ):
                        break
    if reasons[-1].upper() == "ERROR":
        raise AssertionError("Native chat failed: " + str(events[-1].get("error")))
    return {
        "event_count": len(events),
        "event_types": sorted({e["type"] for e in events}),
        "end_reasons": reasons,
        "confirmations": confirmations,
        "reply_ids": sorted({e.get("reply_id") for e in events if e.get("reply_id")}),
    }


async def main(check_hitl, check_stop):
    load_dotenv(APP / ".env")
    summary = {}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:38092", timeout=180
    ) as client:
        login = await client.post(
            "/auth/login",
            json={
                "user_id": "demo.user",
                "password": os.environ["AGENTKIT_DEMO_PASSWORD"],
            },
        )
        login.raise_for_status()
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        response = await client.get("/manager/agents")
        response.raise_for_status()
        catalog = response.json()["items"]
        selected = next(row for row in catalog if row["agent_name"] == "report-analyst")
        assert selected["is_usable"]
        denied = next(row for row in catalog if row["agent_name"] == "finance-advisor")
        blocked = await client.post(
            "/manager/tasks",
            json={"definition_id": denied["id"], "resource_view_type": "system"},
        )
        assert blocked.status_code == 403
        response = await client.post(
            "/manager/tasks",
            json={
                "definition_id": selected["id"],
                "resource_view_type": "system",
                "name": "模型与交付验收",
            },
        )
        response.raise_for_status()
        task = response.json()
        print("Real expert task:", task["session_id"], flush=True)
        summary["report"] = await run_reply(
            client,
            task,
            "请调用 CreateDemoReport，标题“企业 AgentKit 联调报告”，findings为[“PG与Nacos已连接”,“Kafka消费组已启用”,“产物可在右侧预览”]，交付report.md。无需额外检索，不使用Bash。最后用一句中文告知文件名。",
        )
        response = await client.get(
            f"/manager/tasks/{task['session_id']}/files", params={"area": "artifacts"}
        )
        response.raise_for_status()
        assert any(row["name"] == "report.md" for row in response.json()["items"])
        artifact = await client.get(
            f"/manager/tasks/{task['session_id']}/file",
            params={"area": "artifacts", "path": "report.md"},
        )
        artifact.raise_for_status()
        assert "Kafka" in artifact.text and "AgentKit" in artifact.text
        summary["report"].update(
            task=task, artifacts=response.json()["items"], is_preview_verified=True
        )
        assistant = (await client.get("/manager/assistant")).json()
        if check_hitl:
            from egis_agentkit.config import NacosClient, NacosConfigProvider

            from egis_agentkit_app.bootstrap import nacos_bootstrap

            async with NacosClient(nacos_bootstrap()) as nacos:
                provider = NacosConfigProvider(nacos)
                await provider.refresh()
                workspace_root = Path(provider.snapshot.runtime.workspace_root)
            response = await client.post(
                "/manager/tasks",
                json={
                    "definition_id": assistant["id"],
                    "resource_view_type": "private",
                    "name": "人工确认验收",
                },
            )
            response.raise_for_status()
            hitl_task = response.json()
            target = (
                workspace_root
                / "user/demo.user/work"
                / hitl_task["session_id"]
                / "check.txt"
            )
            summary["hitl"] = await run_reply(
                client,
                hitl_task,
                f"请只使用 Write 工具，在 {target} 写入 agentkit-hitl-ok。不要用Bash。完成后回复完成。",
                allow_write=target,
            )
            assert summary["hitl"]["confirmations"] >= 1
            assert len(summary["hitl"]["reply_ids"]) == 1
            result = await client.get(
                f"/manager/tasks/{hitl_task['session_id']}/file",
                params={"area": "work", "path": "check.txt"},
            )
            result.raise_for_status()
            assert "agentkit-hitl-ok" in result.text
            summary["hitl"]["task"] = hitl_task
        if check_stop:
            response = await client.post(
                "/manager/tasks",
                json={
                    "definition_id": assistant["id"],
                    "resource_view_type": "private",
                    "name": "原生停止验收",
                },
            )
            response.raise_for_status()
            stop_task = response.json()
            summary["stop"] = await run_reply(
                client,
                stop_task,
                "请详细说明企业智能体架构的各个部分。",
                interrupt=True,
            )
            assert summary["stop"]["end_reasons"][-1].upper() == "INTERRUPTED"
            summary["stop"]["task"] = stop_task
    destination = APP / "docs/真实聊天验收.json"
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        "Live acceptance passed:",
        ", ".join(summary),
        "Evidence:",
        destination,
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-hitl", action="store_true")
    parser.add_argument("--check-stop", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.check_hitl, args.check_stop))
