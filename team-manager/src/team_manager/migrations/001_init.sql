-- Schema-Version 1: Agenten, Aufträge, append-only Ereignisprotokoll.

CREATE TABLE agent (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    competencies  TEXT NOT NULL DEFAULT '[]',   -- JSON-Liste, kommt aus dem Agentenprofil
    profile_path  TEXT,
    enabled       INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at    TEXT NOT NULL
);

CREATE TABLE task (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id              INTEGER NOT NULL REFERENCES agent (id),
    title                 TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    project_path          TEXT,
    status                TEXT NOT NULL CHECK (status IN (
        'REGISTERED', 'IN_PROGRESS', 'BLOCKED', 'REVIEW_REQUIRED', 'DONE', 'FAILED', 'CANCELLED')),
    created_at            TEXT NOT NULL,
    started_at            TEXT,
    updated_at            TEXT NOT NULL,
    completed_at          TEXT,
    summary               TEXT,
    result_reference      TEXT,
    session_id            TEXT,
    -- Erweiterungen gegenüber dem Briefing (siehe docs/feasibility.md):
    tool_use_id           TEXT,                 -- Agent-Aufruf der Hauptsession, bindet Reservierung und Start
    claude_agent_id       TEXT,                 -- agent_id des laufenden Claude-Code-Subagenten
    last_activity_at      TEXT,
    failure_reason        TEXT,
    completion_incomplete INTEGER NOT NULL DEFAULT 0 CHECK (completion_incomplete IN (0, 1)),
    orphan_suspected      INTEGER NOT NULL DEFAULT 0 CHECK (orphan_suspected IN (0, 1)),
    agent_stopped_at      TEXT,                 -- SubagentStop gesehen
    session_ended_at      TEXT                  -- SessionEnd der zugehörigen Session gesehen
);

-- Die Datenbank selbst verhindert zwei aktive Aufträge pro Agent.
CREATE UNIQUE INDEX one_active_task
    ON task (agent_id)
    WHERE status IN ('REGISTERED', 'IN_PROGRESS', 'BLOCKED');

CREATE UNIQUE INDEX task_tool_use ON task (tool_use_id) WHERE tool_use_id IS NOT NULL;
CREATE UNIQUE INDEX task_claude_agent ON task (claude_agent_id) WHERE claude_agent_id IS NOT NULL;
CREATE INDEX task_status ON task (status);
CREATE INDEX task_session ON task (session_id);

CREATE TABLE task_event (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL REFERENCES task (id),
    event_type TEXT NOT NULL,
    message    TEXT NOT NULL DEFAULT '',
    actor      TEXT,
    timestamp  TEXT NOT NULL
);

CREATE INDEX task_event_task ON task_event (task_id, id);

CREATE TRIGGER task_event_no_update BEFORE UPDATE ON task_event
BEGIN
    SELECT RAISE(ABORT, 'task_event is append-only');
END;

CREATE TRIGGER task_event_no_delete BEFORE DELETE ON task_event
BEGIN
    SELECT RAISE(ABORT, 'task_event is append-only');
END;
