import asyncio
import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

from team_manager import notify
from team_manager.app import create_app
from team_manager.events_bus import EventBus
from team_manager.logs import JsonFormatter
from team_manager.notify import SystemNotifier
from team_manager.service import TaskService


# --------------------------------------------------------------------------- Ereignisbus / Live-Aktualisierung


def test_changes_are_published_to_subscribers(svc):
    async def scenario():
        async with svc.bus.subscribe() as queue:
            await asyncio.to_thread(svc.start_task, "karla", "Live")
            return await asyncio.wait_for(queue.get(), timeout=2)

    assert asyncio.run(scenario()) == {"type": "changed"}


def test_rejected_start_also_signals_change_but_unchanged_reads_do_not(svc):
    svc.start_task("karla", "A")

    async def scenario():
        async with svc.bus.subscribe() as queue:
            await asyncio.to_thread(svc.list_agents)
            await asyncio.to_thread(svc.snapshot)
            with pytest.raises(Exception):
                await asyncio.to_thread(svc.start_task, "karla", "B")
            return queue.qsize()

    assert asyncio.run(scenario()) == 1  # nur die Ablehnung (Ereignis im Protokoll), keine Lesezugriffe


def test_subscriber_is_removed_and_full_queue_is_tolerated():
    bus = EventBus()

    async def scenario():
        async with bus.subscribe():
            assert bus.subscriber_count == 1
            for _ in range(50):
                bus.publish({"type": "changed"})
            await asyncio.sleep(0.05)
        return bus.subscriber_count

    assert asyncio.run(scenario()) == 0


# --------------------------------------------------------------------------- Benachrichtigungen


def test_notifier_failure_does_not_break_state_change(db, settings, clock):
    class Exploding:
        def notify(self, title, message):
            raise RuntimeError("Toast kaputt")

    svc = TaskService(db, settings, notifier=Exploding(), clock=clock)
    from tests.conftest import TEST_PROFILES

    svc.sync_agents(TEST_PROFILES)
    svc.confirm_start("s", "karla", "a1")
    task = svc.agent_complete("a1", svc.list_tasks("active")[0]["id"], "ok", None)
    assert task["status"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_system_notifier_never_puts_text_into_the_command(monkeypatch, platform):
    seen = {}

    def fake_run(cmd, env=None, **kwargs):
        seen["cmd"], seen["env"] = cmd, env

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    monkeypatch.setattr(notify.sys, "platform", platform)
    evil = '"; Remove-Item -Recurse C:\\ ; "'
    SystemNotifier()._send(evil, "Text 'mit' Anführungszeichen")
    if platform == "linux":  # notify-send bekommt Argumente ohne Shell
        assert seen["cmd"][0] == "notify-send"
    else:
        assert not any(evil in part for part in seen["cmd"])
        assert seen["env"]["TM_TITLE"] == evil


# --------------------------------------------------------------------------- Logs


def test_json_formatter_includes_extras():
    record = logging.LogRecord("team_manager.service", logging.INFO, __file__, 1, "transition", (), None)
    record.task_id, record.actor = 7, "user"
    entry = json.loads(JsonFormatter().format(record))
    assert entry["msg"] == "transition" and entry["task_id"] == 7 and entry["actor"] == "user" and entry["level"] == "INFO"


# --------------------------------------------------------------------------- Watchdog in der laufenden App


def test_watchdog_loop_fails_unconfirmed_start(app_settings):
    app_settings.watchdog_interval_s = 0.05
    app_settings.registered_timeout_s = 0
    app = create_app(app_settings)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.post(
            "/hooks",
            headers={"Authorization": "Bearer test-token"},
            json={"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s", "cwd": "C:/p", "tool_use_id": "t",
                  "tool_input": {"subagent_type": "karla", "description": "Wird nie gestartet", "prompt": "x"}},
        )
        deadline = time.time() + 5
        status = "REGISTERED"
        while time.time() < deadline and status == "REGISTERED":
            time.sleep(0.1)
            status = client.get("/api/tasks/1").json()["status"]
    assert status == "FAILED"


def test_port_in_use_detects_listener():
    import socket

    from team_manager.__main__ import port_in_use

    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen()
        assert port_in_use(srv.getsockname()[1]) is True
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    assert port_in_use(port) is False


def test_open_browser_waits_for_port_then_opens(monkeypatch):
    import socket
    import threading

    from team_manager import __main__ as entry

    opened = threading.Event()
    urls = []
    monkeypatch.setattr(entry.webbrowser, "open", lambda url: (urls.append(url), opened.set()))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    entry.open_browser_when_ready(port, timeout_s=5)
    assert not opened.wait(0.6)  # Port noch zu: nichts öffnen
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", port))
        srv.listen()
        assert opened.wait(3)
    assert urls == [f"http://127.0.0.1:{port}/"]
