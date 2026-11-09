"""HTTP-Schicht: Sicherheit (Host, Token, Origin/CSRF) und Cockpit-API."""

import json

import pytest
from fastapi.testclient import TestClient

from team_manager.app import create_app
from team_manager.notify import RecordingNotifier

AUTH = {"Authorization": "Bearer test-token"}
ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def client(app_settings):
    app = create_app(app_settings, notifier=RecordingNotifier())
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        c.app_ = app
        yield c


def hook(client, payload, headers=AUTH):
    return client.post("/hooks", json=payload, headers=headers)


def review_task(client):
    svc = client.app_.state.service
    task = svc.start_task("karla", "Auftrag", "", "C:/p")
    hook(client, {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s", "cwd": "C:/p",
                  "tool_use_id": "t1", "tool_input": {"subagent_type": "karla", "description": "x", "prompt": "y"}})
    hook(client, {"hook_event_name": "SubagentStart", "session_id": "s", "agent_id": "a1", "agent_type": "karla"})
    svc.agent_complete("a1", task["id"], "Fertig", None)
    return task["id"]


# --------------------------------------------------------------------------- Basis


def test_health_and_agents_from_profiles(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["agents"] == ["karla", "lotta", "yasmin"]


def test_index_is_served(client):
    res = client.get("/")
    assert res.status_code == 200 and "Team-Cockpit" in res.text
    assert client.get("/static/app.js").status_code == 200


def test_index_contains_stable_section_ids(client):
    html = client.get("/").text
    for needle in ("Team-Cockpit", 'id="agents"', 'id="attention-section"', 'id="tasks"'):
        assert needle in html


def test_team_cache_for_gate_hook_is_written(client, app_settings):
    assert json.loads(app_settings.team_agents_cache.read_text())["names"] == ["karla", "lotta", "yasmin"]


# --------------------------------------------------------------------------- Host, Token


@pytest.mark.parametrize("host", ["evil.example.com", "127.0.0.1:9999", "localhost", "127.0.0.1"])
def test_foreign_host_header_is_rejected(client, host):
    res = client.get("/api/state", headers={"Host": host})
    assert res.status_code == 403 and res.json()["error"]["code"] == "FORBIDDEN"


def test_localhost_alias_is_allowed(client):
    assert client.get("/api/state", headers={"Host": "localhost:8765"}).status_code == 200


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer falsch"}, {"Authorization": "Basic test-token"}, {"Authorization": "test-token"}]
)
def test_hooks_require_valid_token(client, headers):
    res = hook(client, {"hook_event_name": "SessionEnd"}, headers=headers)
    assert res.status_code == 401 and res.json()["error"]["code"] == "UNAUTHORIZED"


def test_mcp_requires_token(client):
    assert client.post("/mcp", json={}).status_code == 401


def test_hooks_accept_valid_token(client):
    assert hook(client, {"hook_event_name": "SessionEnd"}).json() == {}


# --------------------------------------------------------------------------- Cockpit-Schreibaktionen


def test_done_via_cockpit_with_origin_and_csrf(client):
    task_id = review_task(client)
    csrf = client.get("/api/csrf").json()["csrf_token"]
    res = client.post(f"/api/tasks/{task_id}/actions/done", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert res.status_code == 200 and res.json()["status"] == "DONE"


def test_write_without_origin_or_token_is_rejected(client):
    task_id = review_task(client)
    res = client.post(f"/api/tasks/{task_id}/actions/done")
    assert res.status_code == 403
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize("origin", ["https://evil.example.com", "http://127.0.0.1:1234", "null"])
def test_write_from_foreign_origin_is_rejected(client, origin):
    task_id = review_task(client)
    csrf = client.get("/api/csrf").json()["csrf_token"]
    res = client.post(f"/api/tasks/{task_id}/actions/done", headers={"Origin": origin, "X-CSRF-Token": csrf})
    assert res.status_code == 403
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "REVIEW_REQUIRED"


def test_write_with_wrong_csrf_is_rejected(client):
    task_id = review_task(client)
    res = client.post(f"/api/tasks/{task_id}/actions/done", headers={"Origin": ORIGIN, "X-CSRF-Token": "geraten"})
    assert res.status_code == 401


def test_no_cors_headers_are_ever_sent(client):
    res = client.get("/api/state", headers={"Origin": "https://evil.example.com"})
    assert not any(k.lower().startswith("access-control-") for k in res.headers)


def write_headers(client):
    return {"Origin": ORIGIN, "X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}


def test_agent_token_does_not_authorize_cockpit_writes(client):
    """Das Token liegt in der Umgebung der Sessions. Ein Agent darf damit keinen Review bestätigen."""
    task_id = review_task(client)
    res = client.post(f"/api/tasks/{task_id}/actions/done", headers=AUTH)
    assert res.status_code == 403
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "REVIEW_REQUIRED"


def test_invalid_transition_returns_409_with_code(client):
    svc = client.app_.state.service
    task = svc.start_task("lotta", "Noch nicht fertig")
    res = client.post(f"/api/tasks/{task['id']}/actions/done", headers=write_headers(client))
    assert res.status_code == 409 and res.json()["error"]["code"] == "INVALID_TRANSITION"


def test_unknown_action_and_unknown_task(client):
    task_id = review_task(client)
    assert client.post(f"/api/tasks/{task_id}/actions/zerstoeren", headers=write_headers(client)).status_code == 400
    res = client.post("/api/tasks/9999/actions/done", headers=write_headers(client))
    assert res.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_state_filters_and_detail(client):
    task_id = review_task(client)
    state = client.get("/api/state").json()
    assert state["attention"]["review"] == 1
    assert [t["id"] for t in client.get("/api/tasks", params={"filter": "review"}).json()] == [task_id]
    assert client.get("/api/tasks", params={"filter": "quatsch"}).status_code == 400
    detail = client.get(f"/api/tasks/{task_id}").json()
    assert detail["summary"] == "Fertig" and detail["events"]


def test_blocker_reason_is_part_of_state(client):
    svc = client.app_.state.service
    task = svc.start_task("yasmin", "Wartet")
    svc.confirm_start("s", "yasmin", "ay")
    svc.agent_blocker("ay", task["id"], "Brauche Freigabe")
    tasks = {t["id"]: t for t in client.get("/api/state").json()["tasks"]}
    assert tasks[task["id"]]["blocker_reason"] == "Brauche Freigabe"
