-- Schema-Version 3: Claude-Code-Sessions. Eine Session gilt als gestartet, sobald der erste Hook mit ihrer
-- session_id eintrifft (SessionStart kommt über den HTTP-Hook nicht an), und als beendet mit SessionEnd.

CREATE TABLE session (
    session_id    TEXT PRIMARY KEY,
    cwd           TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    ended_at      TEXT,
    end_reason    TEXT
);

CREATE INDEX session_last_seen ON session (last_seen_at);
