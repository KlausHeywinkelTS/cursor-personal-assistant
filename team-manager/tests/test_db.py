import sqlite3

import pytest

from team_manager.db import Database, now_iso


def _agent(conn, name="karla"):
    conn.execute("INSERT INTO agent (name, created_at) VALUES (?, ?)", (name, now_iso()))
    return conn.execute("SELECT id FROM agent WHERE name=?", (name,)).fetchone()["id"]


def _task(conn, agent_id, status="IN_PROGRESS"):
    conn.execute(
        "INSERT INTO task (agent_id, title, status, created_at, updated_at) VALUES (?, 't', ?, ?, ?)",
        (agent_id, status, now_iso(), now_iso()),
    )


def test_migrate_is_idempotent(tmp_path):
    database = Database(tmp_path / "x.db")
    assert database.migrate() == [1]
    assert database.migrate() == []


def test_database_blocks_second_active_task(db):
    with db.write() as conn:
        agent = _agent(conn)
        _task(conn, agent, "REGISTERED")
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            _task(conn, agent, "IN_PROGRESS")


@pytest.mark.parametrize("finished", ["REVIEW_REQUIRED", "DONE", "FAILED", "CANCELLED"])
def test_finished_tasks_do_not_block_agent(db, finished):
    with db.write() as conn:
        agent = _agent(conn)
        _task(conn, agent, finished)
        _task(conn, agent, "IN_PROGRESS")  # darf nicht werfen


def test_status_check_constraint(db):
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            _task(conn, _agent(conn), "NONSENSE")


def test_events_are_append_only(db):
    with db.write() as conn:
        agent = _agent(conn)
        _task(conn, agent)
        conn.execute("INSERT INTO task_event (task_id, event_type, timestamp) VALUES (1, 'X', ?)", (now_iso(),))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with db.write() as conn:
            conn.execute("UPDATE task_event SET message='manipuliert'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with db.write() as conn:
            conn.execute("DELETE FROM task_event")


def test_failed_write_rolls_back(db):
    with pytest.raises(RuntimeError):
        with db.write() as conn:
            _agent(conn)
            raise RuntimeError("boom")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM agent").fetchone()["n"] == 0
