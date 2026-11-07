"""Verify real TeamSay -> Kafka wakeup -> expert -> leader round trip."""

import asyncio
import json
import os
from pathlib import Path

import httpx
from agentscope.app.message_bus import MessageBusKeys
from dotenv import load_dotenv
from egis_agentkit.extensions.message_bus import EgisMessageBus
from egis_agentkit.storage import AgentKitStorage
from sqlalchemy.ext.asyncio import create_async_engine

APP = Path(__file__).resolve().parents[1]


async def main():
    load_dotenv(APP / ".env")
    engine = create_async_engine(
        os.environ["AGENTKIT_DATABASE_URL"], hide_parameters=True
    )
    storage = AgentKitStorage(os.environ["AGENTKIT_DATABASE_URL"], engine)
    # Replay reads use only PG; this acceptance reader never enters a Kafka
    # group or competes with the application's Dispatcher for a trigger.
    replay = EgisMessageBus(deployment_mode="cluster", engine=engine)
    try:
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:38092", timeout=180
        ) as client:
            health = await client.get("/health/ready")
            health.raise_for_status()
            assert health.json()["deployment_mode"] == "cluster"
            response = await client.post(
                "/auth/login",
                json={
                    "user_id": "demo.user",
                    "password": os.environ["AGENTKIT_DEMO_PASSWORD"],
                },
            )
            response.raise_for_status()
            client.headers["Authorization"] = (
                "Bearer " + response.json()["access_token"]
            )
            response = await client.get("/manager/teams")
            response.raise_for_status()
            source = next(
                item
                for item in response.json()["items"]
                if item["team_name"] == "report-team"
            )
            response = await client.post(
                "/manager/tasks",
                json={
                    "definition_id": source["id"],
                    "resource_view_type": "system",
                    "name": "专家团往返验收",
                },
            )
            response.raise_for_status()
            task = response.json()
            async with storage:
                session = await storage.read_session_unscoped(
                    "demo.user", task["agent_id"], task["session_id"]
                )
                team = await storage.get_team("demo.user", session.team_id)
            response = await client.post(
                "/chat/",
                json={
                    "session_id": task["session_id"],
                    "agent_id": task["agent_id"],
                    "input": {
                        "name": "user",
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "做一次通信验收：请用 TeamSay 仅给 report-analyst 发消息，让它只用 TeamSay 回复你 team-member-ok，不做报告、不调用其他工具。你先结束本轮等待它。收到回复后只输出 team-complete，不再发消息，不创建或邀请成员。",
                            }
                        ],
                    },
                },
            )
            response.raise_for_status()
            print("Real Team task:", task["session_id"], flush=True)
            async with asyncio.timeout(180):
                while True:
                    leader = [
                        payload
                        for _, payload in await replay.log_read(
                            MessageBusKeys.session_events(task["session_id"]),
                            max_count=1000,
                        )
                    ]
                    workers = {}
                    for member in team.data.members:
                        workers[member.session_id] = [
                            payload
                            for _, payload in await replay.log_read(
                                MessageBusKeys.session_events(member.session_id),
                                max_count=1000,
                            )
                        ]
                    ends = [
                        event
                        for event in leader
                        if event.get("type", "").upper() == "REPLY_END"
                    ]
                    worker_ends = [
                        event
                        for events in workers.values()
                        for event in events
                        if event.get("type", "").upper() == "REPLY_END"
                    ]
                    if any(
                        str(event.get("finished_reason", "")).upper() == "ERROR"
                        for event in ends + worker_ends
                    ):
                        raise AssertionError("Native Team run reported an error")
                    if ends and worker_ends:
                        # Native checkpointing may trim streamed text from the
                        # replay log. Persisted Msg is the history authority.
                        response = await client.get(
                            f"/sessions/{task['session_id']}/messages",
                            params={"agent_id": task["agent_id"]},
                        )
                        response.raise_for_status()
                        leader_history = response.json()
                        leader_replies = [
                            msg
                            for msg in leader_history["messages"]
                            if msg.get("role") == "assistant"
                        ]
                        leader_text = "\n".join(
                            block.get("text", "")
                            for msg in leader_replies
                            for block in msg.get("content", [])
                            if block.get("type") == "text"
                        )
                        worker_history = {}
                        for member in team.data.members:
                            response = await client.get(
                                f"/sessions/{member.session_id}/messages",
                                params={"agent_id": member.agent_id},
                            )
                            response.raise_for_status()
                            worker_history[member.session_id] = response.json()
                        if (
                            len(leader_replies) >= 2
                            and "team-complete" in leader_text
                            and "team-member-ok" in json.dumps(worker_history)
                            and "TeamSay" in json.dumps(worker_history)
                        ):
                            break
                    await asyncio.sleep(0.25)
            summary = {
                "task": task,
                "leader_reply_count": len(leader_replies),
                "worker_reply_count": sum(
                    msg.get("role") == "assistant"
                    for body in worker_history.values()
                    for msg in body["messages"]
                ),
                "leader_event_types": sorted({e["type"] for e in leader}),
                "worker_event_types": sorted(
                    {e["type"] for events in workers.values() for e in events}
                ),
                "is_real_model": True,
                "is_kafka_wakeup": True,
            }
            (APP / "docs/真实专家团验收.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2)
            )
            print("Real Team round trip passed", flush=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
