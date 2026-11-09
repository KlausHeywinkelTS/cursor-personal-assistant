"""Hook-Handler mit Payloads in der Form, wie sie im Spike gemessen wurden (docs/feasibility.md)."""

import pytest

from team_manager.bridge import ToolUseBridge
from team_manager.hooks import HookHandler

SESSION = "84ccdd90-e213-4393-b65d-efa3f789d922"


@pytest.fixture
def bridge():
    return ToolUseBridge()


@pytest.fixture
def hooks(svc, bridge):
    return HookHandler(svc, bridge, cockpit_url="http://127.0.0.1:8765")


def agent_call(subagent="karla", *, tool_use_id="toolu_A1", session=SESSION, cwd="C:/proj"):
    return {
        "hook_event_name": "PreToolUse", "session_id": session, "cwd": cwd, "tool_name": "Agent",
        "tool_input": {"description": "README zusammenfassen", "prompt": "Fasse die README zusammen.", "subagent_type": subagent},
        "tool_use_id": tool_use_id,
    }


def sub_start(agent_id="a1", agent_type="karla", session=SESSION):
    return {"hook_event_name": "SubagentStart", "session_id": session, "agent_id": agent_id, "agent_type": agent_type}


def sub_stop(agent_id="a1", agent_type="karla", session=SESSION):
    return {
        "hook_event_name": "SubagentStop", "session_id": session, "agent_id": agent_id, "agent_type": agent_type,
        "agent_transcript_path": "C:/t/agent-a1.jsonl", "stop_hook_active": False,
    }


def decision(response):
    return response.get("hookSpecificOutput", {}).get("permissionDecision")


def started(hooks, **kw):
    hooks.handle(agent_call(**{k: v for k, v in kw.items() if k in ("subagent", "tool_use_id", "session", "cwd")}))
    return hooks.handle(sub_start(kw.get("agent_id", "a1"), kw.get("subagent", "karla"), kw.get("session", SESSION)))


# --------------------------------------------------------------------------- Delegation


def test_delegation_to_free_team_agent_is_allowed_and_registered(hooks, svc):
    assert hooks.handle(agent_call()) == {}
    task = svc.list_tasks("active")[0]
    assert (task["status"], task["agent_name"], task["title"], task["project_path"]) == (
        "REGISTERED", "karla", "README zusammenfassen", "C:/proj",
    )
    assert task["description"] == "Fasse die README zusammen."


def test_delegation_to_busy_agent_is_denied_with_instruction(hooks, svc):
    started(hooks)
    reply = hooks.handle(agent_call(tool_use_id="toolu_B2", session="andere-session", cwd="C:/zweites-fenster"))
    assert decision(reply) == "deny"
    reason = reply["hookSpecificOutput"]["permissionDecisionReason"]
    assert "README zusammenfassen" in reason and "NICHT selbst" in reason and "127.0.0.1:8765" in reason
    assert len(svc.list_tasks("active")) == 1  # der aktive Auftrag bleibt unverändert


def test_non_team_subagent_passes_through_untouched(hooks, svc):
    assert hooks.handle(agent_call("Explore")) == {}
    assert svc.list_tasks("all") == []


def test_subagent_type_matching_is_case_insensitive(hooks, svc):
    hooks.handle(agent_call("Karla"))
    assert svc.list_tasks("active")[0]["agent_name"] == "karla"


# --------------------------------------------------------------------------- Start / Stop


def test_subagent_start_confirms_and_briefs_the_agent(hooks, svc):
    hooks.handle(agent_call())
    reply = hooks.handle(sub_start())
    task = svc.list_tasks("active")[0]
    assert task["status"] == "IN_PROGRESS" and task["claude_agent_id"] == "a1"
    text = reply["hookSpecificOutput"]["additionalContext"]
    assert reply["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert f"task_id={task['id']}" in text and "complete_task" in text and "report_blocker" in text


def test_subagent_start_for_busy_agent_without_reservation_tells_agent_to_stop(hooks, svc):
    started(hooks)
    reply = hooks.handle(sub_start("a_schwarz", session="s_fremd"))
    assert "nicht registriert" in reply["hookSpecificOutput"]["additionalContext"]
    assert svc.get_task(svc.list_tasks("active")[0]["id"])["claude_agent_id"] == "a1"


def test_subagent_stop_without_report_marks_incomplete_review(hooks, svc):
    started(hooks)
    hooks.handle({
        "hook_event_name": "PreToolUse", "session_id": SESSION, "agent_id": "a1", "agent_type": "karla",
        "tool_name": "SubagentHandback", "tool_input": {"message": "Hier ist mein Ergebnis."}, "tool_use_id": "toolu_H",
    })
    hooks.handle(sub_stop())
    task = svc.list_tasks("all")[0]
    assert task["status"] == "REVIEW_REQUIRED" and task["completion_incomplete"] is True
    assert task["summary"] == "Hier ist mein Ergebnis."


def test_failed_agent_launch_fails_the_task(hooks, svc):
    hooks.handle(agent_call())
    hooks.handle({"hook_event_name": "PostToolUseFailure", "tool_name": "Agent", "tool_use_id": "toolu_A1", "error": "boom"})
    assert svc.list_tasks("all")[0]["status"] == "FAILED"


def test_session_end_flags_active_task_but_never_completes_it(hooks, svc):
    started(hooks)
    hooks.handle({"hook_event_name": "SessionEnd", "session_id": SESSION, "reason": "other"})
    task = svc.list_tasks("all")[0]
    assert task["status"] == "IN_PROGRESS" and task["orphan_suspected"] is True


def test_session_end_of_unknown_session_is_ignored(hooks, svc):
    started(hooks)
    hooks.handle({"hook_event_name": "SessionEnd", "session_id": "cli-aufruf", "reason": "other"})
    assert svc.list_tasks("all")[0]["orphan_suspected"] is False


def test_activity_of_subagent_is_recorded(hooks, svc, clock):
    started(hooks)
    clock.advance(30)
    hooks.handle({"hook_event_name": "PostToolUse", "session_id": SESSION, "agent_id": "a1", "agent_type": "karla", "tool_name": "Read"})
    assert svc.list_tasks("all")[0]["last_activity_at"].startswith("2026-11-09T12:00:30")


# --------------------------------------------------------------------------- MCP-Gate


def mcp_call(tool, agent_id, tool_use_id="toolu_M1"):
    return {
        "hook_event_name": "PreToolUse", "session_id": SESSION, "agent_id": agent_id, "agent_type": "karla" if agent_id else None,
        "tool_name": f"mcp__team__{tool}", "tool_input": {"task_id": 1}, "tool_use_id": tool_use_id,
        "mcp_server": {"name": "team", "source": "user"},
    }


def test_team_tool_call_registers_identity_in_bridge(hooks, bridge):
    started(hooks)
    assert hooks.handle(mcp_call("update_task", "a1")) == {}
    assert bridge.lookup("toolu_M1") == (True, "a1")


def test_main_session_call_is_recorded_as_anonymous(hooks, bridge):
    hooks.handle(mcp_call("list_agents", None, "toolu_M2"))
    assert bridge.lookup("toolu_M2") == (True, None)


def test_subagent_must_not_assign_tasks_to_other_agents(hooks, bridge, svc):
    started(hooks)
    reply = hooks.handle(mcp_call("start_task", "a1", "toolu_M3"))
    assert decision(reply) == "deny"
    assert bridge.lookup("toolu_M3") == (False, None)


# --------------------------------------------------------------------------- @-Mentions


@pytest.mark.parametrize(
    "prompt",
    ["@agent-karla lies die README", '@"karla (agent)" lies die README', "@karla lies die README", "Bitte @Karla: lies das", "hi @agent-KARLA"],
)
def test_mention_forms_are_detected(hooks, prompt):
    reply = hooks.handle({"hook_event_name": "UserPromptSubmit", "prompt": prompt})
    text = reply["hookSpecificOutput"]["additionalContext"]
    assert 'subagent_type "karla"' in text and "nicht selbst" in text


@pytest.mark.parametrize("prompt", ["mail an karla@example.com", "@karlas Buch", "ohne mention karla", "@src/karla.py lesen", ""])
def test_non_mentions_are_ignored(hooks, prompt):
    assert hooks.handle({"hook_event_name": "UserPromptSubmit", "prompt": prompt}) == {}


def test_multiple_mentions(hooks):
    reply = hooks.handle({"hook_event_name": "UserPromptSubmit", "prompt": "@karla macht A, @yasmin macht B"})
    text = reply["hookSpecificOutput"]["additionalContext"]
    assert 'subagent_type "karla"' in text and 'subagent_type "yasmin"' in text


# --------------------------------------------------------------------------- Robustheit


@pytest.mark.parametrize("payload", [{}, {"hook_event_name": "Unbekannt"}, {"hook_event_name": "SubagentStart"}, {"hook_event_name": "PreToolUse"}])
def test_garbage_payloads_do_not_raise(hooks, payload):
    assert hooks.handle(payload) == {}


def test_internal_error_in_delegation_gate_denies(hooks, svc, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db kaputt")

    monkeypatch.setattr(svc, "reserve_for_delegation", boom)
    assert decision(hooks.handle(agent_call())) == "deny"
