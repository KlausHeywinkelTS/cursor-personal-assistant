"""Klaus (Manager) beauftragt andere Teammitglieder. Der Team-Manager muss jeden Unterauftrag mitbekommen."""

import pytest

from team_manager.errors import InvalidTransition
from team_manager.profiles import AgentProfile, load_profiles
from tests.conftest import TEST_PROFILES
from tests.test_hooks import SESSION, agent_call, decision, hooks, sub_start, sub_stop  # noqa: F401  (Fixture hooks, bridge)
from tests.test_hooks import bridge  # noqa: F401

KLAUS = AgentProfile("klaus", "Klaus", "Manager", ["koordination"], can_delegate=True)


@pytest.fixture(autouse=True)
def team_with_manager(svc):
    svc.sync_agents([*TEST_PROFILES, KLAUS])


def klaus_running(hooks, agent_id="k1"):
    hooks.handle(agent_call("klaus", tool_use_id="toolu_K"))
    hooks.handle(sub_start(agent_id, "klaus"))


def delegate(hooks, subagent="karla", *, by="k1", tool_use_id="toolu_D1"):
    payload = agent_call(subagent, tool_use_id=tool_use_id)
    payload["agent_id"], payload["agent_type"] = by, "klaus"
    return hooks.handle(payload)


def task_of(svc, name):
    return next(t for t in svc.list_tasks("all") if t["agent_name"] == name)


def test_delegation_by_manager_is_registered_as_child_task(hooks, svc):
    klaus_running(hooks)
    assert delegate(hooks) == {}
    klaus, karla = task_of(svc, "klaus"), task_of(svc, "karla")
    assert karla["parent_task_id"] == klaus["id"] and karla["status"] == "REGISTERED"
    assert klaus["parent_task_id"] is None
    kinds = [e["event_type"] for e in svc.get_task(klaus["id"])["events"]]
    assert "DELEGATED" in kinds


def test_child_task_is_confirmed_by_subagent_start_like_any_other(hooks, svc):
    klaus_running(hooks)
    delegate(hooks)
    reply = hooks.handle(sub_start("a2", "karla"))
    karla = task_of(svc, "karla")
    assert karla["status"] == "IN_PROGRESS" and karla["parent_task_id"] == task_of(svc, "klaus")["id"]
    text = reply["hookSpecificOutput"]["additionalContext"]
    assert "Beauftrage keine anderen Agenten" in text


def test_manager_is_told_he_may_delegate(hooks):
    hooks.handle(agent_call("klaus", tool_use_id="toolu_K"))
    text = hooks.handle(sub_start("k1", "klaus"))["hookSpecificOutput"]["additionalContext"]
    assert "Agent-Tool" in text and "Unteraufträge" in text and "Beauftrage keine anderen Agenten" not in text


def test_detail_shows_parent_and_children(hooks, svc):
    klaus_running(hooks)
    delegate(hooks)
    klaus, karla = task_of(svc, "klaus"), task_of(svc, "karla")
    assert svc.get_task(karla["id"])["parent"]["id"] == klaus["id"]
    assert [c["id"] for c in svc.get_task(klaus["id"])["children"]] == [karla["id"]]


def test_delegation_to_busy_agent_is_denied_with_blocker_hint(hooks, svc):
    klaus_running(hooks)
    hooks.handle(agent_call("karla", tool_use_id="toolu_U"))  # Benutzer hat Karla bereits beauftragt
    reply = delegate(hooks)
    assert decision(reply) == "deny"
    assert "report_blocker" in reply["hookSpecificOutput"]["permissionDecisionReason"]
    assert [t["agent_name"] for t in svc.list_tasks("active")].count("karla") == 1


def test_manager_cannot_delegate_to_himself(hooks, svc):
    klaus_running(hooks)
    assert decision(delegate(hooks, "klaus")) == "deny"
    assert [t["agent_name"] for t in svc.list_tasks("active")] == ["klaus"]
    kinds = [e["event_type"] for e in svc.get_task(task_of(svc, "klaus")["id"])["events"]]
    assert "DELEGATION_REJECTED" in kinds


def test_ordinary_team_agent_must_not_delegate(hooks, svc):
    hooks.handle(agent_call("karla", tool_use_id="toolu_K1"))
    hooks.handle(sub_start("a1", "karla"))
    payload = agent_call("yasmin", tool_use_id="toolu_Y")
    payload["agent_id"], payload["agent_type"] = "a1", "karla"
    reply = hooks.handle(payload)
    assert decision(reply) == "deny" and "darf keine anderen Agenten beauftragen" in reply["hookSpecificOutput"]["permissionDecisionReason"]
    assert [t["agent_name"] for t in svc.list_tasks("active")] == ["karla"]


def test_unregistered_foreign_subagent_keeps_old_behaviour(hooks, svc):
    payload = agent_call("karla")
    payload["agent_id"], payload["agent_type"] = "fremd", "general-purpose"
    assert hooks.handle(payload) == {}
    assert svc.list_tasks("active")[0]["parent_task_id"] is None


def test_manager_cannot_complete_while_children_run(hooks, svc):
    klaus_running(hooks)
    delegate(hooks)
    hooks.handle(sub_start("a2", "karla"))
    klaus = task_of(svc, "klaus")
    with pytest.raises(InvalidTransition) as exc:
        svc.agent_complete("k1", klaus["id"], "fertig", None)
    assert "Karla" in str(exc.value)
    assert svc.get_task(klaus["id"])["status"] == "IN_PROGRESS"

    karla = task_of(svc, "karla")
    svc.agent_complete("a2", karla["id"], "Ergebnis", None)  # REVIEW_REQUIRED gibt den Unterauftrag frei
    assert svc.agent_complete("k1", klaus["id"], "Alles zusammengeführt", None)["status"] == "REVIEW_REQUIRED"


def test_manager_stop_with_running_child_does_not_touch_child(hooks, svc):
    klaus_running(hooks)
    delegate(hooks)
    hooks.handle(sub_start("a2", "karla"))
    hooks.handle(sub_stop("k1", "klaus"))
    assert task_of(svc, "klaus")["status"] == "REVIEW_REQUIRED"
    assert task_of(svc, "karla")["status"] == "IN_PROGRESS"


# --------------------------------------------------------------------------- Review gebündelt über den Manager


def klaus_with_two_children(hooks, svc):
    """Klaus hat Karla und Lotta beauftragt, beide liefern ab, Klaus meldet sein Ergebnis."""
    klaus_running(hooks)
    delegate(hooks, "karla", tool_use_id="toolu_D1")
    hooks.handle(sub_start("a2", "karla"))
    delegate(hooks, "lotta", tool_use_id="toolu_D2")
    hooks.handle(sub_start("a3", "lotta"))
    svc.agent_complete("a2", task_of(svc, "karla")["id"], "Karlas Ergebnis", None)
    svc.agent_complete("a3", task_of(svc, "lotta")["id"], "Lottas Ergebnis", None)
    svc.agent_complete("k1", task_of(svc, "klaus")["id"], "Alles zusammengeführt", None)
    return task_of(svc, "klaus"), task_of(svc, "karla"), task_of(svc, "lotta")


def test_delivered_child_needs_no_own_feedback(hooks, svc, notifier):
    klaus, karla, lotta = klaus_with_two_children(hooks, svc)
    assert karla["status"] == lotta["status"] == "REVIEW_REQUIRED"
    assert karla["review_covered"] and lotta["review_covered"] and not klaus["review_covered"]
    assert svc.snapshot()["attention"]["review"] == 1  # nur Klaus
    assert {a["name"]: a["open_reviews"] for a in svc.list_agents()} == {"karla": 0, "yasmin": 0, "lotta": 0, "klaus": 1}
    titles = [title for title, _ in notifier.sent]
    assert titles == ["Klaus: Review erforderlich"]  # keine Pings für die Unteraufträge


def test_marking_manager_done_accepts_delivered_children(hooks, svc):
    klaus, karla, lotta = klaus_with_two_children(hooks, svc)
    assert svc.user_action(klaus["id"], "done")["status"] == "DONE"
    assert task_of(svc, "karla")["status"] == task_of(svc, "lotta")["status"] == "DONE"
    assert svc.snapshot()["attention"]["review"] == 0
    assert "CHILDREN_ACCEPTED" in [e["event_type"] for e in svc.get_task(klaus["id"])["events"]]
    child_events = svc.get_task(karla["id"])["events"]
    assert any(e["event_type"] == "STATUS_DONE" and e["actor"] == "user" for e in child_events)


def test_directly_assigned_task_still_needs_own_feedback(hooks, svc):
    hooks.handle(agent_call("karla", tool_use_id="toolu_U"))
    hooks.handle(sub_start("a1", "karla"))
    karla = task_of(svc, "karla")
    svc.agent_complete("a1", karla["id"], "Fertig", None)
    karla = task_of(svc, "karla")
    assert karla["parent_task_id"] is None and not karla["review_covered"]
    assert svc.snapshot()["attention"]["review"] == 1


def test_incomplete_child_stays_with_user_and_is_not_accepted_by_cascade(hooks, svc, notifier):
    klaus_running(hooks)
    delegate(hooks)
    hooks.handle(sub_start("a2", "karla"))
    hooks.handle(sub_stop("a2", "karla"))  # Karla endet ohne complete_task
    karla = task_of(svc, "karla")
    assert karla["status"] == "REVIEW_REQUIRED" and karla["completion_incomplete"] and not karla["review_covered"]
    assert any(title == "Karla: Review erforderlich" for title, _ in notifier.sent)
    svc.agent_complete("k1", task_of(svc, "klaus")["id"], "fertig", None)
    assert svc.snapshot()["attention"]["review"] == 2  # Klaus und die unvollständige Karla
    svc.user_action(task_of(svc, "klaus")["id"], "done")
    assert task_of(svc, "karla")["status"] == "REVIEW_REQUIRED"


def test_child_review_becomes_visible_again_when_manager_fails(hooks, svc):
    klaus, karla, _ = klaus_with_two_children(hooks, svc)
    svc.user_action(klaus["id"], "fail")
    assert not task_of(svc, "karla")["review_covered"]
    assert svc.snapshot()["attention"]["review"] == 2  # Karla und Lotta warten jetzt einzeln auf dich


def test_manager_task_detail_lists_child_results(hooks, svc):
    klaus, karla, _ = klaus_with_two_children(hooks, svc)
    child = next(c for c in svc.get_task(klaus["id"])["children"] if c["id"] == karla["id"])
    assert child["summary"] == "Karlas Ergebnis" and child["completion_incomplete"] is False


def test_mention_of_manager_delegates_to_klaus(hooks):
    reply = hooks.handle({"hook_event_name": "UserPromptSubmit", "prompt": "@agent-klaus plane das"})
    assert 'subagent_type "klaus"' in reply["hookSpecificOutput"]["additionalContext"]


def test_can_delegate_is_read_from_profile(tmp_path):
    (tmp_path / "m.md").write_text("---\nname: m\nteam_member: true\ncan_delegate: true\n---\n", encoding="utf-8")
    (tmp_path / "n.md").write_text("---\nname: n\nteam_member: true\n---\n", encoding="utf-8")
    assert {p.name: p.can_delegate for p in load_profiles(tmp_path)} == {"m": True, "n": False}


def test_shipped_klaus_profile_is_a_delegating_team_member():
    from pathlib import Path

    profiles = {p.name: p for p in load_profiles(Path(__file__).parent.parent / "agents")}
    assert profiles["klaus"].can_delegate is True
    assert not any(p.can_delegate for n, p in profiles.items() if n != "klaus")
