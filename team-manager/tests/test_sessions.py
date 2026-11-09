"""Session-Erkennung: Start = erster Hook mit unbekannter session_id, Ende = SessionEnd (Option B, kein SessionStart)."""

import pytest
from fastapi.testclient import TestClient

from team_manager.app import create_app
from team_manager.bridge import ToolUseBridge
from team_manager.hooks import HookHandler
from team_manager.notify import RecordingNotifier

SID = "11111111-aaaa-bbbb-cccc-222222222222"


@pytest.fixture
def hooks(svc):
    return HookHandler(svc, ToolUseBridge(), cockpit_url="http://127.0.0.1:8765")


def prompt(session=SID, cwd="C:/proj"):
    return {"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": cwd, "prompt": "Hallo"}


def tool(event="PostToolUse", session=SID, **extra):
    return {"hook_event_name": event, "session_id": session, "tool_name": "Read", **extra}


def end(session=SID, reason="other"):
    return {"hook_event_name": "SessionEnd", "session_id": session, "reason": reason}


# --------------------------------------------------------------------------- Start


def test_first_hook_of_unknown_session_registers_it(hooks, svc):
    hooks.handle(prompt())
    [s] = svc.list_sessions()
    assert (s["session_id"], s["cwd"], s["active"]) == (SID, "C:/proj", True)
    assert s["first_seen_at"] == s["last_seen_at"] and s["ended_at"] is None


@pytest.mark.parametrize(
    "payload",
    [prompt(), tool("PreToolUse"), tool("PostToolUse"), tool("PostToolUseFailure"),
     {"hook_event_name": "SubagentStart", "session_id": SID, "agent_id": "a1", "agent_type": "unbekannt"},
     {"hook_event_name": "SubagentStop", "session_id": SID, "agent_id": "a1", "agent_type": "unbekannt"}],
    ids=lambda p: p["hook_event_name"],
)
def test_every_session_bound_hook_registers_the_session(hooks, svc, payload):
    hooks.handle(payload)
    assert [s["session_id"] for s in svc.list_sessions()] == [SID]


def test_session_end_alone_does_not_create_a_session(hooks, svc):
    hooks.handle(end())
    assert svc.list_sessions() == []


@pytest.mark.parametrize("payload", [{"hook_event_name": "PostToolUse"}, {"hook_event_name": "UserPromptSubmit", "session_id": ""}])
def test_hook_without_session_id_is_ignored(hooks, svc, payload):
    hooks.handle(payload)
    assert svc.list_sessions() == []


def test_session_without_agent_is_listed_without_tasks(hooks, svc):
    hooks.handle(prompt())
    [s] = svc.list_sessions()
    assert (s["task_count"], s["active_task_count"]) == (0, 0)


def test_cwd_is_filled_in_later_but_never_overwritten(hooks, svc):
    hooks.handle(tool())  # PostToolUse trägt kein cwd
    assert svc.list_sessions()[0]["cwd"] is None
    hooks.handle(prompt(cwd="C:/proj"))
    hooks.handle(prompt(cwd="C:/anderswo"))
    assert svc.list_sessions()[0]["cwd"] == "C:/proj"


# --------------------------------------------------------------------------- Auftrag der Session = erster Prompt


def test_first_prompt_becomes_the_session_job(hooks, svc):
    hooks.handle({**prompt(), "prompt": "Fasse die README zusammen"})
    assert svc.list_sessions()[0]["first_prompt"] == "Fasse die README zusammen"


def test_later_prompts_do_not_replace_the_job(hooks, svc):
    hooks.handle({**prompt(), "prompt": "Erster Auftrag"})
    hooks.handle({**prompt(), "prompt": "Und noch was"})
    assert svc.list_sessions()[0]["first_prompt"] == "Erster Auftrag"


def test_job_is_filled_in_by_a_later_prompt_when_session_was_seen_without_one(hooks, svc):
    hooks.handle(tool())  # z. B. Dienst wurde mitten in der Session gestartet
    assert svc.list_sessions()[0]["first_prompt"] is None
    hooks.handle({**prompt(), "prompt": "Mein Auftrag"})
    assert svc.list_sessions()[0]["first_prompt"] == "Mein Auftrag"


def test_job_is_normalised_and_clipped(hooks, svc):
    hooks.handle({**prompt(), "prompt": "Zeile eins\n\n   Zeile zwei\t" + "x" * 1000})
    job = svc.list_sessions()[0]["first_prompt"]
    assert job.startswith("Zeile eins Zeile zwei x") and len(job) == 300


IDE_FILE = (
    "<ide_opened_file>The user opened the file c:\\Users\\x\\journal.md in the IDE. "
    "This may or may not be related to the current task.</ide_opened_file>"
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (IDE_FILE + "team-manager: Kann die GUI mehr?", "team-manager: Kann die GUI mehr?"),
        (IDE_FILE + "\n<ide_selection>Zeile 1\nZeile 2</ide_selection>\nMach das fertig", "Mach das fertig"),
        ("Vorher <system-reminder>intern\nmehrzeilig</system-reminder> nachher", "Vorher nachher"),
        ("Echter Text mit <b>HTML</b> bleibt", "Echter Text mit <b>HTML</b> bleibt"),
        (IDE_FILE, None),  # nur Kontext, kein Auftrag: das nächste Prompt füllt ihn nach
    ],
    ids=["opened-file", "file-and-selection", "system-reminder", "other-tags-stay", "context-only"],
)
def test_ide_context_blocks_are_not_part_of_the_job(hooks, svc, raw, expected):
    hooks.handle({**prompt(), "prompt": raw})
    assert svc.list_sessions()[0]["first_prompt"] == expected


def test_context_only_prompt_leaves_room_for_the_real_job(hooks, svc):
    hooks.handle({**prompt(), "prompt": IDE_FILE})
    hooks.handle({**prompt(), "prompt": IDE_FILE + "Der eigentliche Auftrag"})
    assert svc.list_sessions()[0]["first_prompt"] == "Der eigentliche Auftrag"


@pytest.mark.parametrize("text", ["", "   \n ", None])
def test_empty_prompt_sets_no_job(hooks, svc, text):
    hooks.handle({**prompt(), "prompt": text})
    assert svc.list_sessions()[0]["first_prompt"] is None


def test_only_user_prompts_set_the_job(hooks, svc):
    hooks.handle(tool("PreToolUse", prompt="Nicht der Auftrag"))
    assert svc.list_sessions()[0]["first_prompt"] is None


# --------------------------------------------------------------------------- Aktivität, Ende


def test_activity_is_throttled(hooks, svc, clock):
    hooks.handle(prompt())
    clock.advance(10)
    hooks.handle(tool())
    assert svc.list_sessions()[0]["last_seen_at"].startswith("2026-11-09T12:00:00")
    clock.advance(25)
    hooks.handle(tool())
    assert svc.list_sessions()[0]["last_seen_at"].startswith("2026-11-09T12:00:35")


def test_no_bus_event_for_pure_activity(hooks, svc, clock):
    hooks.handle(prompt())
    events = []
    svc.bus.publish = events.append  # type: ignore[method-assign]
    clock.advance(60)
    hooks.handle(tool())
    assert events == []


def test_session_end_marks_session_as_ended_with_reason(hooks, svc, clock):
    hooks.handle(prompt())
    clock.advance(300)
    hooks.handle(end(reason="prompt_input_exit"))
    [s] = svc.list_sessions()
    assert s["active"] is False and s["end_reason"] == "prompt_input_exit" and s["ended_at"].startswith("2026-11-09T12:05:00")


def test_late_hooks_do_not_reopen_an_ended_session(hooks, svc):
    hooks.handle(prompt())
    hooks.handle(end())
    hooks.handle(tool())
    hooks.handle({"hook_event_name": "SubagentStop", "session_id": SID, "agent_id": "a1", "agent_type": "x"})
    assert svc.list_sessions()[0]["active"] is False


def test_prompt_in_ended_session_reopens_it_for_resume(hooks, svc):
    hooks.handle(prompt())
    hooks.handle(end())
    hooks.handle(prompt())
    [s] = svc.list_sessions()
    assert s["active"] is True and s["end_reason"] is None


def test_session_end_twice_keeps_first_end(hooks, svc, clock):
    hooks.handle(prompt())
    hooks.handle(end(reason="clear"))
    clock.advance(60)
    hooks.handle(end(reason="other"))
    assert svc.list_sessions()[0]["end_reason"] == "clear"


# --------------------------------------------------------------------------- Zusammenspiel mit Aufträgen


def test_session_with_agent_task_counts_it(hooks, svc):
    hooks.handle({
        "hook_event_name": "PreToolUse", "session_id": SID, "cwd": "C:/proj", "tool_name": "Agent", "tool_use_id": "t1",
        "tool_input": {"subagent_type": "karla", "description": "x", "prompt": "y"},
    })
    [s] = svc.list_sessions()
    assert (s["task_count"], s["active_task_count"]) == (1, 1)


def test_session_lists_its_own_tasks_only(hooks, svc):
    def delegate(subagent, tool_use_id, session):
        hooks.handle({
            "hook_event_name": "PreToolUse", "session_id": session, "cwd": "C:/proj", "tool_name": "Agent", "tool_use_id": tool_use_id,
            "tool_input": {"subagent_type": subagent, "description": f"Auftrag {subagent}", "prompt": "y"},
        })

    delegate("karla", "t1", SID)
    delegate("yasmin", "t2", SID)
    delegate("lotta", "t3", "andere-session")
    by_id = {s["session_id"]: s for s in svc.list_sessions()}
    assert [(t["agent_name"], t["title"], t["status"]) for t in by_id[SID]["tasks"]] == [
        ("karla", "Auftrag karla", "REGISTERED"), ("yasmin", "Auftrag yasmin", "REGISTERED"),
    ]
    assert by_id[SID]["tasks"][0].keys() >= {"id", "title", "status", "agent_name", "agent_display_name", "parent_task_id"}
    assert "session_id" not in by_id[SID]["tasks"][0]
    assert [t["agent_name"] for t in by_id["andere-session"]["tasks"]] == ["lotta"]
    assert (by_id[SID]["task_count"], by_id[SID]["active_task_count"]) == (2, 2)


def test_session_end_still_flags_active_tasks(hooks, svc):
    hooks.handle({
        "hook_event_name": "PreToolUse", "session_id": SID, "cwd": "C:/proj", "tool_name": "Agent", "tool_use_id": "t1",
        "tool_input": {"subagent_type": "karla", "description": "x", "prompt": "y"},
    })
    hooks.handle({"hook_event_name": "SubagentStart", "session_id": SID, "agent_id": "a1", "agent_type": "karla"})
    hooks.handle(end())
    assert svc.list_tasks("all")[0]["orphan_suspected"] is True
    assert svc.list_sessions()[0]["active"] is False


def test_tracking_failure_does_not_break_the_hook(hooks, svc, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(svc, "session_seen", boom)
    assert hooks.handle(prompt("s2")) == {}  # kein Teammitglied erwähnt -> leere Antwort statt Ausnahme


# --------------------------------------------------------------------------- Sortierung, API


def test_running_sessions_come_first_then_ended_by_end_time(hooks, svc, clock):
    for sid in ("alt", "neu", "laeuft"):
        hooks.handle(prompt(sid))
        clock.advance(100)
    hooks.handle(end("neu"))
    clock.advance(100)
    hooks.handle(end("alt"))
    assert [(s["session_id"], s["active"]) for s in svc.list_sessions()] == [("laeuft", True), ("alt", False), ("neu", False)]


def test_limit_applies(hooks, svc):
    for n in range(5):
        hooks.handle(prompt(f"s{n}"))
    assert len(svc.list_sessions(limit=3)) == 3


def test_snapshot_and_api_contain_sessions(app_settings):
    app = create_app(app_settings, notifier=RecordingNotifier())
    auth = {"Authorization": "Bearer test-token"}
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/state").json()["sessions"] == []
        client.post("/hooks", json=prompt(), headers=auth)
        [s] = client.get("/api/sessions").json()
        assert s["session_id"] == SID and s["active"] is True
        assert client.get("/api/state").json()["sessions"][0]["session_id"] == SID
        client.post("/hooks", json=end(), headers=auth)
        assert client.get("/api/sessions").json()[0]["active"] is False
