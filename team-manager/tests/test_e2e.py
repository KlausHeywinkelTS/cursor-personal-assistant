"""Ende-zu-Ende: echter HTTP-Server, echter MCP-Client (mit _meta), Hooks per HTTP.

Belegt die Kernannahme aus dem Spike: der MCP-Aufruf trägt claudecode/toolUseId, der PreToolUse-Hook
kennt dazu die agent_id, daraus entsteht die Zuordnung.
"""

import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from team_manager import agent_gate
from team_manager.app import create_app
from team_manager.notify import RecordingNotifier

TOKEN = "test-token"
SESSION = "sess-1"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Live:
    def __init__(self, settings):
        self.port = free_port()
        settings.port = self.port
        self.settings = settings
        self.notifier = RecordingNotifier()
        self.app = create_app(settings, notifier=self.notifier)
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.http = httpx.Client(base_url=self.url, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)

    def start(self):
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("Server nicht gestartet")

    def stop(self):
        self.http.close()
        self.server.should_exit = True
        self.thread.join(10)

    @property
    def svc(self):
        return self.app.state.service

    def hook(self, payload: dict) -> dict:
        res = self.http.post("/hooks", json=payload)
        assert res.status_code == 200, res.text
        return res.json()

    # Hook-Payloads in der im Spike gemessenen Form
    def delegate(self, agent="karla", tool_use_id="toolu_D1", session=SESSION):
        return self.hook({
            "hook_event_name": "PreToolUse", "session_id": session, "cwd": "C:/proj", "tool_name": "Agent",
            "tool_use_id": tool_use_id, "tool_input": {"subagent_type": agent, "description": "Auftrag", "prompt": "Mach es."},
        })

    def subagent_start(self, agent_id="a1", agent_type="karla", session=SESSION):
        return self.hook({"hook_event_name": "SubagentStart", "session_id": session, "agent_id": agent_id, "agent_type": agent_type})

    def before_mcp(self, tool, tool_use_id, agent_id, agent_type="karla"):
        return self.hook({
            "hook_event_name": "PreToolUse", "session_id": SESSION, "agent_id": agent_id,
            "agent_type": agent_type if agent_id else None, "tool_name": f"mcp__team__{tool}",
            "tool_input": {}, "tool_use_id": tool_use_id, "mcp_server": {"name": "team", "source": "user"},
        })

    def mcp(self, steps):
        """steps: Liste (tool, args, tool_use_id). Gibt (isError, text) je Schritt zurück."""

        async def run():
            results = []
            async with streamablehttp_client(f"{self.url}/mcp", headers={"Authorization": f"Bearer {TOKEN}"}) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    for tool, args, tuid in steps:
                        meta = {"claudecode/toolUseId": tuid} if tuid else None
                        res = await session.call_tool(tool, args, meta=meta)
                        results.append((res.isError, res.content[0].text if res.content else ""))
            return results

        return asyncio.run(run())

    def list_tools(self) -> list[str]:
        async def run():
            async with streamablehttp_client(f"{self.url}/mcp", headers={"Authorization": f"Bearer {TOKEN}"}) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return [t.name for t in (await session.list_tools()).tools]

        return asyncio.run(run())


@pytest.fixture
def live(app_settings):
    server = Live(app_settings)
    server.start()
    yield server
    server.stop()


def started_karla(live):
    live.delegate()
    live.subagent_start()
    return live.svc.list_tasks("active")[0]["id"]


# --------------------------------------------------------------------------- MCP


def test_mcp_exposes_exactly_the_briefed_tools_and_no_delegation(live):
    assert sorted(live.list_tools()) == sorted(
        ["list_agents", "start_task", "get_task", "update_task", "complete_task", "report_blocker"]
    )


def test_full_flow_with_real_mcp_client(live):
    task_id = started_karla(live)
    live.before_mcp("update_task", "toolu_U1", "a1")
    live.before_mcp("complete_task", "toolu_C1", "a1")
    [(err1, _), (err2, text2)] = live.mcp([
        ("update_task", {"task_id": task_id, "message": "Halbzeit"}, "toolu_U1"),
        ("complete_task", {"task_id": task_id, "summary": "Alles erledigt", "result_reference": "docs/x.md"}, "toolu_C1"),
    ])
    assert not err1 and not err2, text2
    task = live.svc.get_task(task_id)
    assert task["status"] == "REVIEW_REQUIRED" and task["summary"] == "Alles erledigt" and task["result_reference"] == "docs/x.md"
    assert any(e["event_type"] == "PROGRESS" and e["message"] == "Halbzeit" for e in task["events"])
    assert ("Karla: Review erforderlich", "Auftrag") in live.notifier.sent


def test_call_without_hook_identity_is_rejected(live):
    task_id = started_karla(live)
    [(is_error, text)] = live.mcp([("complete_task", {"task_id": task_id, "summary": "dreist"}, "toolu_UNBEKANNT")])
    assert is_error and "NOT_TASK_OWNER" in text
    assert live.svc.get_task(task_id)["status"] == "IN_PROGRESS"


def test_call_without_tool_use_id_is_rejected(live):
    task_id = started_karla(live)
    [(is_error, text)] = live.mcp([("update_task", {"task_id": task_id, "message": "x"}, None)])
    assert is_error and "NOT_TASK_OWNER" in text


def test_foreign_agent_cannot_touch_task(live):
    karla_task = started_karla(live)
    live.delegate("yasmin", tool_use_id="toolu_D2", session="sess-2")
    live.subagent_start("a2", "yasmin", session="sess-2")
    live.before_mcp("complete_task", "toolu_X", "a2", "yasmin")
    [(is_error, text)] = live.mcp([("complete_task", {"task_id": karla_task, "summary": "geklaut"}, "toolu_X")])
    assert is_error and "NOT_TASK_OWNER" in text
    assert live.svc.get_task(karla_task)["status"] == "IN_PROGRESS"


def test_main_session_can_register_and_second_registration_is_rejected(live):
    live.before_mcp("start_task", "toolu_S1", None)
    live.before_mcp("start_task", "toolu_S2", None)
    results = live.mcp([
        ("start_task", {"agent": "karla", "title": "Vorab", "description": "d", "project_path": "C:/proj"}, "toolu_S1"),
        ("start_task", {"agent": "karla", "title": "Doppelt"}, "toolu_S2"),
    ])
    assert not results[0][0] and json.loads(results[0][1])["status"] == "REGISTERED"
    assert results[1][0] and "AGENT_BUSY" in results[1][1] and "Vorab" in results[1][1]
    assert live.svc.list_tasks("active")[0]["title"] == "Vorab"
    assert next(a for a in live.svc.list_agents() if a["name"] == "karla")["availability"] == "busy"


def test_subagent_cannot_assign_work_to_other_agents(live):
    started_karla(live)
    reply = live.before_mcp("start_task", "toolu_Z", "a1")
    assert reply["hookSpecificOutput"]["permissionDecision"] == "deny"


# --------------------------------------------------------------------------- Test 2/6 über HTTP


def test_second_window_is_denied_and_first_task_unchanged(live):
    started_karla(live)
    reply = live.delegate(tool_use_id="toolu_D9", session="sess-fenster-2")
    assert reply["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "NICHT selbst" in reply["hookSpecificOutput"]["permissionDecisionReason"]
    [task] = live.svc.list_tasks("active")
    assert task["status"] == "IN_PROGRESS" and task["session_id"] == SESSION


def test_parallel_agents_in_two_windows(live):
    live.delegate("karla", "t1", "w1")
    live.delegate("yasmin", "t2", "w2")
    live.subagent_start("a1", "karla", "w1")
    live.subagent_start("a2", "yasmin", "w2")
    assert sorted(t["status"] for t in live.svc.list_tasks("active")) == ["IN_PROGRESS", "IN_PROGRESS"]


# --------------------------------------------------------------------------- Gate-Skript (command-Hook)


def agent_payload(subagent):
    return json.dumps({
        "hook_event_name": "PreToolUse", "session_id": "g1", "cwd": "C:/proj", "tool_name": "Agent", "tool_use_id": "toolu_G",
        "tool_input": {"subagent_type": subagent, "description": "Gate", "prompt": "p"},
    })


@pytest.fixture
def gate_env(live, monkeypatch):
    monkeypatch.setenv("TEAM_MANAGER_HOME", str(live.settings.home))
    monkeypatch.setenv("TEAM_MANAGER_PORT", str(live.port))
    monkeypatch.setenv("TEAM_MANAGER_TOKEN", TOKEN)
    return live


def test_gate_passes_foreign_subagents_without_contacting_service(gate_env, monkeypatch):
    monkeypatch.setenv("TEAM_MANAGER_PORT", "1")  # würde scheitern, wenn kontaktiert
    assert agent_gate.run(agent_payload("Explore")) == ""


def test_gate_ignores_other_tools(gate_env):
    assert agent_gate.run(json.dumps({"tool_name": "Bash", "tool_input": {}})) == ""


def test_gate_registers_free_team_agent(gate_env):
    assert agent_gate.run(agent_payload("karla")) == ""
    assert gate_env.svc.list_tasks("active")[0]["status"] == "REGISTERED"


def test_gate_relays_service_denial_when_agent_busy(gate_env):
    started_karla(gate_env)
    out = json.loads(agent_gate.run(agent_payload("karla")))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "beschäftigt" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_gate_fails_closed_for_team_agent_when_service_is_down(gate_env, monkeypatch):
    monkeypatch.setenv("TEAM_MANAGER_PORT", str(free_port()))  # dort lauscht niemand
    out = json.loads(agent_gate.run(agent_payload("karla")))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "nicht erreichbar" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_gate_fails_open_for_foreign_subagent_when_service_is_down(gate_env, monkeypatch):
    monkeypatch.setenv("TEAM_MANAGER_PORT", str(free_port()))
    assert agent_gate.run(agent_payload("general-purpose")) == ""


def test_gate_without_cache_does_not_block(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_MANAGER_HOME", str(tmp_path / "leer"))
    assert agent_gate.run(agent_payload("karla")) == ""


def test_gate_main_keeps_umlauts_despite_windows_locale_streams(monkeypatch):
    """Hook-Streams sind UTF-8, die Textstreams unter Windows aber cp1252 (sonst wird aus "ä" ein "Ã¤")."""
    import io
    import sys

    text = '{"title": "Aufwand-Einschätzung für Größe → ✓"}'
    stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="cp1252")
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(agent_gate, "run", lambda raw: raw)
    agent_gate.main()
    assert stdout.buffer.getvalue().decode("utf-8") == text


def test_gate_main_takes_port_from_argument(monkeypatch):
    """Der Installer übergibt den Port als --port; er hat Vorrang vor der Umgebungsvariable."""
    import io
    import os
    import sys

    monkeypatch.setenv("TEAM_MANAGER_PORT", "1")
    monkeypatch.setattr(sys, "argv", ["agent_gate", "--port", "48999"])
    monkeypatch.setattr(agent_gate, "run", lambda raw: "")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))
    agent_gate.main()
    assert os.environ["TEAM_MANAGER_PORT"] == "48999"
