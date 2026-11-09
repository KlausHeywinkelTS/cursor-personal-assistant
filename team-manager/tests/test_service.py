import pytest

from team_manager.errors import (
    AgentBusy,
    AgentUnknown,
    ErrorCode,
    InvalidTransition,
    NotTaskOwner,
    ServiceError,
    TaskNotFound,
)


def delegate(svc, agent="karla", *, tool_use_id="toolu_1", session="s1", title="Titel", project="C:/proj"):
    return svc.reserve_for_delegation(agent, title, "Beschreibung", project, session, tool_use_id)


def start(svc, agent="karla", *, claude_id="a1", session="s1", tool_use_id="toolu_1", **kw):
    task = delegate(svc, agent, tool_use_id=tool_use_id, session=session, **kw)
    svc.confirm_start(session, agent, claude_id)
    return svc.get_task(task["id"])


def event_types(svc, task_id):
    return [e["event_type"] for e in svc.get_task(task_id)["events"]]


# --------------------------------------------------------------------------- Agenten


def test_agents_come_from_profiles_and_start_available(svc):
    agents = {a["name"]: a for a in svc.list_agents()}
    assert set(agents) == {"karla", "yasmin", "lotta"}
    assert agents["karla"]["availability"] == "available"
    assert agents["karla"]["competencies"] == ["analyse"]


def test_removed_profile_disables_agent(svc):
    from tests.conftest import TEST_PROFILES

    svc.sync_agents(TEST_PROFILES[:2])
    assert svc.team_agent_names() == ["karla", "yasmin"]
    with pytest.raises(AgentUnknown):
        svc.start_task("lotta", "x")


def test_unknown_agent(svc):
    with pytest.raises(AgentUnknown):
        svc.start_task("nobody", "x")


# --------------------------------------------------------------------------- Test 1/2: Reservierung


def test_start_task_registers_and_marks_agent_busy(svc):
    task = svc.start_task("karla", "Analyse", "Details", "C:/proj")
    assert task["status"] == "REGISTERED"
    karla = next(a for a in svc.list_agents() if a["name"] == "karla")
    assert karla["availability"] == "busy"
    assert karla["current_task"]["id"] == task["id"]


def test_second_task_for_busy_agent_is_rejected_and_first_is_unchanged(svc):
    first = svc.start_task("karla", "Erster")
    with pytest.raises(AgentBusy) as exc:
        svc.start_task("karla", "Zweiter")
    assert exc.value.code == ErrorCode.AGENT_BUSY
    assert exc.value.details["task_id"] == first["id"]
    assert "Erster" in exc.value.message
    unchanged = svc.get_task(first["id"])
    assert unchanged["status"] == "REGISTERED" and unchanged["title"] == "Erster"
    assert "START_REJECTED" in event_types(svc, first["id"])


def test_delegation_to_busy_agent_is_rejected(svc):
    start(svc)
    with pytest.raises(AgentBusy):
        delegate(svc, tool_use_id="toolu_2", session="s2")


def test_other_agents_are_not_blocked(svc):
    start(svc, "karla")
    task = start(svc, "yasmin", claude_id="a2", tool_use_id="toolu_2", session="s2")
    assert task["status"] == "IN_PROGRESS"


def test_delegation_is_idempotent_per_tool_use_id(svc):
    a = delegate(svc)
    b = delegate(svc)
    assert a["id"] == b["id"]


def test_delegation_adopts_preregistered_task(svc):
    pre = svc.start_task("karla", "Vorab", "", "C:/proj")
    adopted = delegate(svc, project="c:/proj")
    assert adopted["id"] == pre["id"]
    assert adopted["tool_use_id"] == "toolu_1"
    assert "TASK_ADOPTED" in event_types(svc, pre["id"])


def test_delegation_does_not_adopt_foreign_project(svc):
    svc.start_task("karla", "Vorab", "", "C:/andere")
    with pytest.raises(AgentBusy):
        delegate(svc, project="C:/proj")


def test_empty_title_rejected(svc):
    with pytest.raises(ServiceError):
        svc.start_task("karla", "   ")


# --------------------------------------------------------------------------- Test 1/4: Start, Abschluss, Review


def test_unconfirmed_start_is_not_an_accepted_task(svc):
    task = delegate(svc)
    assert task["status"] == "REGISTERED"
    assert task["claude_agent_id"] is None
    assert task["started_at"] is None


def test_confirmed_start_sets_in_progress(svc):
    task = start(svc)
    assert task["status"] == "IN_PROGRESS"
    assert task["claude_agent_id"] == "a1"
    assert task["started_at"]


def test_full_flow_to_done_frees_agent_after_review(svc, notifier):
    task = start(svc)
    done = svc.agent_complete("a1", task["id"], "Fertig", "docs/ergebnis.md")
    assert done["status"] == "REVIEW_REQUIRED"
    assert done["summary"] == "Fertig" and done["result_reference"] == "docs/ergebnis.md"
    assert not done["completion_incomplete"]
    # Review blockiert den Agenten nicht mehr
    assert next(a for a in svc.list_agents() if a["name"] == "karla")["availability"] == "available"
    second = start(svc, claude_id="a9", tool_use_id="toolu_9", session="s2")
    assert second["status"] == "IN_PROGRESS"
    # nur der Benutzer setzt DONE
    final = svc.user_action(task["id"], "done")
    assert final["status"] == "DONE"
    assert ("Karla: Review erforderlich", "Titel") in notifier.sent


def test_agent_cannot_mark_done(svc):
    task = start(svc)
    svc.agent_complete("a1", task["id"], "Fertig", None)
    with pytest.raises(InvalidTransition):
        svc.agent_update("a1", task["id"], "DONE", "ich war's selbst")
    assert svc.get_task(task["id"])["status"] == "REVIEW_REQUIRED"
    assert "TRANSITION_REJECTED" in event_types(svc, task["id"])


def test_user_cannot_mark_done_before_review(svc):
    task = start(svc)
    with pytest.raises(InvalidTransition):
        svc.user_action(task["id"], "done")
    assert svc.get_task(task["id"])["status"] == "IN_PROGRESS"
    assert "TRANSITION_REJECTED" in event_types(svc, task["id"])


def test_complete_requires_summary(svc):
    task = start(svc)
    with pytest.raises(ServiceError):
        svc.agent_complete("a1", task["id"], "  ", None)


def test_progress_message_is_logged_and_status_kept(svc):
    task = start(svc)
    updated = svc.agent_update("a1", task["id"], None, "Halbzeit")
    assert updated["status"] == "IN_PROGRESS"
    assert any(e["event_type"] == "PROGRESS" and e["message"] == "Halbzeit" for e in svc.get_task(task["id"])["events"])


def test_update_cannot_complete_or_block(svc):
    task = start(svc)
    for status in ("REVIEW_REQUIRED", "BLOCKED"):
        with pytest.raises(ServiceError) as exc:
            svc.agent_update("a1", task["id"], status, "")
        assert exc.value.code == ErrorCode.INVALID_INPUT
    assert svc.get_task(task["id"])["status"] == "IN_PROGRESS"


# --------------------------------------------------------------------------- vergessene Abschlussmeldung


def test_stop_without_complete_marks_review_required_but_incomplete(svc, notifier):
    task = start(svc)
    svc.record_handback("a1", "Das ist meine letzte Antwort")
    result = svc.subagent_stopped("a1", "C:/transcripts/a1.jsonl")
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["completion_incomplete"] is True
    assert result["summary"] == "Das ist meine letzte Antwort"
    assert result["result_reference"] == "C:/transcripts/a1.jsonl"
    assert notifier.sent[-1][0] == "Karla: Review erforderlich"


def test_stop_without_handback_has_placeholder_summary(svc):
    task = start(svc)
    result = svc.subagent_stopped("a1", None)
    assert result["completion_incomplete"] is True
    assert "keine Abschlussmeldung" in result["summary"]


def test_stop_after_complete_keeps_complete_state(svc):
    task = start(svc)
    svc.agent_complete("a1", task["id"], "Fertig", None)
    result = svc.subagent_stopped("a1", "C:/t.jsonl")
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["completion_incomplete"] is False
    assert result["summary"] == "Fertig"
    assert result["result_reference"] == "C:/t.jsonl"


def test_stop_of_unknown_subagent_is_ignored(svc):
    assert svc.subagent_stopped("unbekannt", None) is None


# --------------------------------------------------------------------------- Blocker


def test_blocker_flow(svc, notifier):
    task = start(svc)
    blocked = svc.agent_blocker("a1", task["id"], "Brauche Zugangsdaten")
    assert blocked["status"] == "BLOCKED"
    assert notifier.sent[-1] == ("Karla ist blockiert", "Titel: Brauche Zugangsdaten")
    # blockiert, aber der Agent bleibt beschäftigt
    assert next(a for a in svc.list_agents() if a["name"] == "karla")["availability"] == "busy"
    resumed = svc.user_action(task["id"], "unblock")
    assert resumed["status"] == "IN_PROGRESS"


def test_unblock_after_agent_stopped_is_rejected(svc):
    task = start(svc)
    svc.agent_blocker("a1", task["id"], "Entscheidung nötig")
    svc.subagent_stopped("a1", None)
    assert svc.get_task(task["id"])["status"] == "BLOCKED"
    with pytest.raises(InvalidTransition):
        svc.user_action(task["id"], "unblock")
    assert svc.user_action(task["id"], "cancel")["status"] == "CANCELLED"


def test_blocker_reason_required(svc):
    task = start(svc)
    with pytest.raises(ServiceError):
        svc.agent_blocker("a1", task["id"], "")


# --------------------------------------------------------------------------- Ownership / veraltete Session


def test_foreign_agent_cannot_change_task(svc):
    task = start(svc)
    other = start(svc, "yasmin", claude_id="a2", tool_use_id="toolu_2", session="s2")
    with pytest.raises(NotTaskOwner):
        svc.agent_complete("a2", task["id"], "Das gehört nicht mir", None)
    assert svc.get_task(task["id"])["status"] == "IN_PROGRESS"
    assert "OWNERSHIP_REJECTED" in event_types(svc, task["id"])
    assert other["status"] == "IN_PROGRESS"


def test_stale_session_cannot_touch_newer_task_of_same_agent(svc):
    old = start(svc, claude_id="a_old", tool_use_id="toolu_old", session="s_old")
    svc.agent_complete("a_old", old["id"], "Alt fertig", None)
    new = start(svc, claude_id="a_new", tool_use_id="toolu_new", session="s_new")
    with pytest.raises(NotTaskOwner):
        svc.agent_update("a_old", new["id"], None, "ich funke dazwischen")
    with pytest.raises(NotTaskOwner):
        svc.agent_complete("a_old", new["id"], "Fremd abgeschlossen", None)
    assert svc.get_task(new["id"])["status"] == "IN_PROGRESS"


def test_call_without_identity_is_rejected(svc):
    task = start(svc)
    with pytest.raises(NotTaskOwner):
        svc.agent_update(None, task["id"], None, "anonym")


def test_unknown_task(svc):
    with pytest.raises(TaskNotFound):
        svc.get_task(999)
    with pytest.raises(TaskNotFound):
        svc.agent_update("a1", 999, None, "")


def test_agent_cannot_update_its_finished_task(svc):
    task = start(svc)
    svc.agent_complete("a1", task["id"], "Fertig", None)
    with pytest.raises(InvalidTransition):
        svc.agent_update("a1", task["id"], None, "noch ein Nachtrag")


def test_subagent_start_from_other_session_does_not_take_registration(svc):
    delegate(svc, session="s1")
    result = svc.confirm_start("s_fremd", "karla", "a_fremd")
    assert "untracked" in result
    assert svc.list_tasks("active")[0]["status"] == "REGISTERED"


def test_unreserved_start_creates_visible_task(svc):
    result = svc.confirm_start("s1", "karla", "a1")
    assert result["task"]["status"] == "IN_PROGRESS"
    assert "UNRESERVED_START" in event_types(svc, result["task"]["id"])


def test_non_team_subagent_start_is_ignored(svc):
    assert svc.confirm_start("s1", "Explore", "x") == {}


# --------------------------------------------------------------------------- Fehlerfälle / Test 6


def test_failed_launch_marks_task_failed_and_frees_agent(svc, notifier):
    task = delegate(svc)
    svc.start_failed("toolu_1", "Agent konnte nicht gestartet werden")
    assert svc.get_task(task["id"])["status"] == "FAILED"
    assert next(a for a in svc.list_agents() if a["name"] == "karla")["availability"] == "available"
    assert notifier.sent[-1][0] == "Karla: Auftrag fehlgeschlagen"


def test_registered_without_start_times_out_to_failed(svc, clock):
    task = delegate(svc)
    clock.advance(119)
    assert svc.run_watchdog() == []
    clock.advance(2)
    assert svc.run_watchdog() == [task["id"]]
    failed = svc.get_task(task["id"])
    assert failed["status"] == "FAILED" and "nicht bestätigt" in failed["failure_reason"]


def test_interrupted_work_is_never_shown_as_success(svc, clock):
    """Test 6: Fenster geschlossen, kein SubagentStop, kein complete_task."""
    task = start(svc)
    svc.touch_activity("a1")
    assert svc.session_ended("s1") == 1
    flagged = svc.get_task(task["id"])
    assert flagged["status"] == "IN_PROGRESS" and flagged["orphan_suspected"] is True
    clock.advance(121)
    svc.run_watchdog()
    final = svc.get_task(task["id"])
    assert final["status"] == "FAILED"
    assert final["status"] not in ("REVIEW_REQUIRED", "DONE")
    assert next(a for a in svc.list_agents() if a["name"] == "karla")["availability"] == "available"


def test_activity_after_session_end_prevents_failure_and_clears_flag(svc, clock):
    task = start(svc)
    svc.session_ended("s1")
    clock.advance(60)
    svc.touch_activity("a1")
    clock.advance(100)
    svc.run_watchdog()
    alive = svc.get_task(task["id"])
    assert alive["status"] == "IN_PROGRESS" and alive["orphan_suspected"] is False


def test_inactivity_marks_orphan_but_keeps_status(svc, clock):
    task = start(svc)
    clock.advance(901)
    assert svc.run_watchdog() == [task["id"]]
    orphan = svc.get_task(task["id"])
    assert orphan["status"] == "IN_PROGRESS" and orphan["orphan_suspected"] is True
    assert svc.run_watchdog() == []  # nur einmal melden
    svc.touch_activity("a1")
    assert svc.get_task(task["id"])["orphan_suspected"] is False


def test_blocked_task_is_not_flagged_as_orphan(svc, clock):
    task = start(svc)
    svc.agent_blocker("a1", task["id"], "wartet")
    clock.advance(5000)
    assert svc.run_watchdog() == []
    assert svc.get_task(task["id"])["status"] == "BLOCKED"


def test_user_can_cancel_orphan_to_free_agent(svc, clock):
    task = start(svc)
    clock.advance(901)
    svc.run_watchdog()
    assert svc.user_action(task["id"], "cancel")["status"] == "CANCELLED"
    assert next(a for a in svc.list_agents() if a["name"] == "karla")["availability"] == "available"


# --------------------------------------------------------------------------- Ereignisprotokoll, Filter


def test_event_log_documents_the_whole_lifecycle(svc):
    task = start(svc)
    svc.agent_update("a1", task["id"], None, "unterwegs")
    svc.agent_complete("a1", task["id"], "Fertig", None)
    svc.user_action(task["id"], "done")
    types = event_types(svc, task["id"])
    assert types[0] == "TASK_REGISTERED"
    for expected in ("STATUS_IN_PROGRESS", "PROGRESS", "STATUS_REVIEW_REQUIRED", "STATUS_DONE"):
        assert expected in types


def test_task_filters(svc):
    a = start(svc, "karla")
    b = start(svc, "yasmin", claude_id="a2", tool_use_id="t2", session="s2")
    c = start(svc, "lotta", claude_id="a3", tool_use_id="t3", session="s3")
    svc.agent_complete("a2", b["id"], "x", None)
    svc.agent_blocker("a3", c["id"], "y")
    ids = lambda f: {t["id"] for t in svc.list_tasks(f)}  # noqa: E731
    assert ids("all") == {a["id"], b["id"], c["id"]}
    assert ids("active") == {a["id"]}
    assert ids("review") == {b["id"]}
    assert ids("blocked") == {c["id"]}
    assert ids("done") == set() and ids("failed") == set()
    svc.user_action(b["id"], "done")
    assert ids("done") == {b["id"]}
    with pytest.raises(ServiceError):
        svc.list_tasks("quatsch")


def test_snapshot_attention_counts(svc):
    a = start(svc, "karla")
    svc.agent_complete("a1", a["id"], "x", None)
    snap = svc.snapshot()
    assert snap["attention"] == {"review": 1, "blocked": 0, "orphans": 0}


# --------------------------------------------------------------------------- Test 5: Neustart


def test_state_survives_service_restart(svc, db, settings, clock):
    from team_manager.service import TaskService

    a = start(svc, "karla")
    svc.agent_complete("a1", a["id"], "Fertig", "ref")
    b = start(svc, "yasmin", claude_id="a2", tool_use_id="t2", session="s2")
    svc.agent_blocker("a2", b["id"], "warte")
    before = (svc.list_tasks("all"), [svc.get_task(t["id"]) for t in svc.list_tasks("all")])

    from team_manager.db import Database

    reopened = Database(db.path)
    assert reopened.migrate() == []
    from tests.conftest import TEST_PROFILES

    restarted = TaskService(reopened, settings, clock=clock)
    restarted.sync_agents(TEST_PROFILES)
    after = (restarted.list_tasks("all"), [restarted.get_task(t["id"]) for t in restarted.list_tasks("all")])
    assert before == after
    assert next(x for x in restarted.list_agents() if x["name"] == "yasmin")["availability"] == "busy"
