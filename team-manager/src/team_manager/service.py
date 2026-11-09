"""Anwendungsfälle des Team-Managers. Einzige Stelle, die Aufträge schreibt.

Alle Zustandswechsel laufen durch _transition(): Übergang prüfen, Ereignis protokollieren,
Zeitstempel pflegen. Ein unzulässiger Übergang wird abgelehnt und als TRANSITION_REJECTED
protokolliert (die Ablehnung wird committed, erst danach wird die Ausnahme geworfen).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings
from .db import Database
from .errors import (
    AgentBusy,
    AgentUnknown,
    Forbidden,
    InvalidTransition,
    NotTaskOwner,
    ServiceError,
    TaskNotFound,
)
from .events_bus import EventBus
from .lifecycle import ACTIVE_STATUSES, check_transition
from .notify import Notifier, NullNotifier
from .profiles import AgentProfile

log = logging.getLogger("team_manager.service")

_TASK_SELECT = (
    "SELECT t.*, a.name AS agent_name, a.display_name AS agent_display_name, a.can_delegate AS agent_can_delegate, "
    "p.status AS parent_status "
    "FROM task t JOIN agent a ON a.id = t.agent_id LEFT JOIN task p ON p.id = t.parent_task_id"
)
_ACTIVE_SQL = "(" + ", ".join(f"'{s}'" for s in ACTIVE_STATUSES) + ")"

# Ein abgelieferter Unterauftrag braucht kein eigenes Feedback, solange sein Elternauftrag noch abgenommen wird.
# Endet der Elternauftrag als FAILED/CANCELLED, wird die Abdeckung hinfällig und der Review wieder sichtbar.
_COVERING_PARENT_STATUSES = (*ACTIVE_STATUSES, "REVIEW_REQUIRED")
_COVERING_SQL = "(" + ", ".join(f"'{s}'" for s in _COVERING_PARENT_STATUSES) + ")"

FILTERS: dict[str, tuple[str, ...] | None] = {
    "all": None,
    "active": ("REGISTERED", "IN_PROGRESS"),
    "review": ("REVIEW_REQUIRED",),
    "blocked": ("BLOCKED",),
    "done": ("DONE",),
    "failed": ("FAILED", "CANCELLED"),
}
USER_ACTIONS = {"done": "DONE", "cancel": "CANCELLED", "fail": "FAILED", "unblock": "IN_PROGRESS"}
_MAX_TITLE, _MAX_TEXT = 200, 20_000
# So selten wird last_seen_at einer laufenden Session fortgeschrieben (Hooks kommen bei jedem Tool-Aufruf).
_SESSION_TOUCH_S = 30
# Länge des gespeicherten ersten Prompts einer Session (Anzeige im Cockpit, kein Volltext).
_MAX_SESSION_PROMPT = 300
# Die IDE-Erweiterung stellt dem Prompt Kontextblöcke voran (geöffnete Datei, Auswahl, Systemhinweise).
# Sie gehören nicht zum Auftrag und würden bei der Kürzung den eigentlichen Text verdrängen.
_PROMPT_CONTEXT_BLOCK = re.compile(r"<(ide_[a-z_]+|system-reminder)>.*?</\1>", re.DOTALL | re.IGNORECASE)


class _Op:
    """Sammelt, was nach dem Commit passieren soll (Fehler werfen, Bus, Benachrichtigung)."""

    def __init__(self) -> None:
        self.error: ServiceError | None = None
        self.changed = False
        self.notifications: list[tuple[str, str]] = []


def _norm_path(path: str | None) -> str | None:
    return os.path.normcase(os.path.normpath(path)) if path else None


def _session_job(prompt: str | None) -> str | None:
    """Der Auftrag einer Session: der Prompt ohne IDE-Kontextblöcke, Leerraum zusammengezogen und gekürzt."""
    text = " ".join(_PROMPT_CONTEXT_BLOCK.sub(" ", prompt or "").split())
    return text[:_MAX_SESSION_PROMPT] or None


def _clip(text: str | None, limit: int) -> str:
    return (text or "").strip()[:limit]


def _covered_by_parent(task: dict, *, incomplete: bool | None = None) -> bool:
    """True, wenn der Review dieses Unterauftrags über den Elternauftrag läuft (kein eigenes Benutzerfeedback).

    Unvollständige Abschlüsse (Agent hat complete_task vergessen) bleiben beim Benutzer: das ist ein
    Qualitätssignal, das die Zusammenfassung des Managers nicht überdecken soll.
    """
    if incomplete is None:
        incomplete = bool(task.get("completion_incomplete"))
    return task.get("parent_task_id") is not None and not incomplete and task.get("parent_status") in _COVERING_PARENT_STATUSES


def _task_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    task = dict(row)
    task["completion_incomplete"] = bool(task["completion_incomplete"])
    task["orphan_suspected"] = bool(task["orphan_suspected"])
    task["agent_can_delegate"] = bool(task["agent_can_delegate"])
    task["review_covered"] = task["status"] == "REVIEW_REQUIRED" and _covered_by_parent(task)
    return task


class TaskService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        *,
        notifier: Notifier | None = None,
        bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.notifier = notifier or NullNotifier()
        self.bus = bus or EventBus()
        self._clock = clock or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------ Hilfen

    def _ts(self) -> str:
        return self._clock().isoformat(timespec="milliseconds")

    def _write(self, fn: Callable[[sqlite3.Connection, _Op], Any]) -> Any:
        op = _Op()
        with self.db.write() as conn:
            result = fn(conn, op)
        if op.changed:
            self.bus.publish({"type": "changed"})
        for title, message in op.notifications:
            try:
                self.notifier.notify(title, message)
            except Exception:
                log.exception("notifier_failed")
        if op.error is not None:
            raise op.error
        return result

    def _event(self, conn: sqlite3.Connection, task_id: int, event_type: str, message: str = "", actor: str | None = None) -> None:
        conn.execute(
            "INSERT INTO task_event (task_id, event_type, message, actor, timestamp) VALUES (?, ?, ?, ?, ?)",
            (task_id, event_type, message, actor, self._ts()),
        )

    def _agent_row(self, conn: sqlite3.Connection, name: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM agent WHERE name = ?", ((name or "").strip().lower(),)).fetchone()
        if row is None or not row["enabled"]:
            raise AgentUnknown(f"Agent '{name}' ist nicht bekannt oder deaktiviert.")
        return row

    def _task_row(self, conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
        row = conn.execute(_TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"Auftrag {task_id} existiert nicht.")
        return row

    def _active_row(self, conn: sqlite3.Connection, agent_id: int) -> sqlite3.Row | None:
        return conn.execute(
            _TASK_SELECT + f" WHERE t.agent_id = ? AND t.status IN {_ACTIVE_SQL}", (agent_id,)
        ).fetchone()

    def _busy_error(self, active: sqlite3.Row) -> AgentBusy:
        return AgentBusy(
            f"{active['agent_display_name']} ist beschäftigt mit Auftrag #{active['id']} "
            f"„{active['title']}“ ({active['status']}).",
            details={
                "task_id": active["id"],
                "title": active["title"],
                "status": active["status"],
                "since": active["started_at"] or active["created_at"],
                "orphan_suspected": bool(active["orphan_suspected"]),
                "project_path": active["project_path"],
            },
        )

    def _transition(
        self,
        conn: sqlite3.Connection,
        op: _Op,
        task: sqlite3.Row,
        to: str,
        actor: str,
        *,
        message: str = "",
        fields: dict[str, Any] | None = None,
    ) -> bool:
        """Führt einen validierten Statuswechsel aus. False, wenn abgelehnt (dann steht op.error)."""
        try:
            check_transition(task["status"], to, actor)
        except InvalidTransition as exc:
            self._event(
                conn, task["id"], "TRANSITION_REJECTED",
                f"{task['status']} -> {to} durch {actor} abgelehnt", actor,
            )
            log.warning(
                "transition_rejected",
                extra={"task_id": task["id"], "from": task["status"], "to": to, "actor": actor},
            )
            op.error = exc
            op.changed = True
            return False
        now = self._ts()
        values: dict[str, Any] = {"status": to, "updated_at": now, **(fields or {})}
        if to in ("REVIEW_REQUIRED", "DONE", "FAILED", "CANCELLED") and not task["completed_at"]:
            values["completed_at"] = now
        if to == "IN_PROGRESS" and not task["started_at"]:
            values["started_at"] = now
        sets = ", ".join(f"{col} = ?" for col in values)
        conn.execute(f"UPDATE task SET {sets} WHERE id = ?", (*values.values(), task["id"]))
        self._event(conn, task["id"], f"STATUS_{to}", message, actor)
        log.info(
            "transition",
            extra={"task_id": task["id"], "agent": task["agent_name"], "from": task["status"], "to": to, "actor": actor},
        )
        op.changed = True
        if to in ("REVIEW_REQUIRED", "BLOCKED", "FAILED"):
            # Ein Unterauftrag, dessen Review über den Elternauftrag läuft, soll den Benutzer nicht anpingen.
            quiet = to == "REVIEW_REQUIRED" and _covered_by_parent(
                dict(task), incomplete=bool(values.get("completion_incomplete", task["completion_incomplete"]))
            )
            if not quiet:
                op.notifications.append(self._notification(task, to, message, values))
        return True

    @staticmethod
    def _notification(task: sqlite3.Row, to: str, message: str, values: dict) -> tuple[str, str]:
        who = task["agent_display_name"]
        title = task["title"]
        if to == "REVIEW_REQUIRED":
            return f"{who}: Review erforderlich", title
        if to == "BLOCKED":
            return f"{who} ist blockiert", f"{title}: {message}".strip(": ")
        reason = values.get("failure_reason") or message
        return f"{who}: Auftrag fehlgeschlagen", f"{title}. {reason}".strip()

    # ------------------------------------------------------------------ Agenten

    def sync_agents(self, profiles: list[AgentProfile]) -> None:
        """Gleicht die Tabelle agent mit den Profilen ab. Nicht mehr vorhandene Agenten werden deaktiviert."""

        def run(conn: sqlite3.Connection, op: _Op) -> None:
            names = []
            for p in profiles:
                names.append(p.name)
                conn.execute(
                    "INSERT INTO agent (name, display_name, description, competencies, profile_path, can_delegate, enabled, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?) "
                    "ON CONFLICT(name) DO UPDATE SET display_name=excluded.display_name, "
                    "description=excluded.description, competencies=excluded.competencies, "
                    "profile_path=excluded.profile_path, can_delegate=excluded.can_delegate, enabled=1",
                    (
                        p.name, p.display_name, p.description, json.dumps(p.competencies, ensure_ascii=False), p.path,
                        int(p.can_delegate), self._ts(),
                    ),
                )
            marks = ",".join("?" for _ in names) or "''"
            conn.execute(f"UPDATE agent SET enabled = 0 WHERE name NOT IN ({marks})", names)
            op.changed = True

        self._write(run)

    def team_agent_names(self) -> list[str]:
        with self.db.read() as conn:
            return [r["name"] for r in conn.execute("SELECT name FROM agent WHERE enabled = 1 ORDER BY name")]

    def list_agents(self) -> list[dict]:
        with self.db.read() as conn:
            agents = conn.execute("SELECT * FROM agent WHERE enabled = 1 ORDER BY name").fetchall()
            result = []
            for a in agents:
                active = self._active_row(conn, a["id"])
                reviews = conn.execute(
                    "SELECT COUNT(*) AS n FROM task t LEFT JOIN task p ON p.id = t.parent_task_id "
                    "WHERE t.agent_id = ? AND t.status = 'REVIEW_REQUIRED' "
                    f"AND NOT (t.parent_task_id IS NOT NULL AND t.completion_incomplete = 0 AND COALESCE(p.status, '') IN {_COVERING_SQL})",
                    (a["id"],),
                ).fetchone()["n"]
                current = _task_dict(active)
                result.append(
                    {
                        "name": a["name"],
                        "display_name": a["display_name"],
                        "description": a["description"],
                        "competencies": json.loads(a["competencies"]),
                        "can_delegate": bool(a["can_delegate"]),
                        "availability": "busy" if active else "available",
                        "current_task": current,
                        "open_reviews": reviews,
                    }
                )
            return result

    # ------------------------------------------------------------------ Aufträge anlegen

    def _validate_text(self, title: str, description: str) -> tuple[str, str]:
        title = _clip(title, _MAX_TITLE)
        if not title:
            raise ServiceError("Der Titel darf nicht leer sein.")
        return title, _clip(description, _MAX_TEXT)

    def _insert_task(
        self, conn: sqlite3.Connection, agent: sqlite3.Row, *, title: str, description: str, project_path: str | None,
        status: str, session_id: str | None = None, tool_use_id: str | None = None, claude_agent_id: str | None = None,
        parent_task_id: int | None = None,
    ) -> int:
        now = self._ts()
        try:
            cur = conn.execute(
                "INSERT INTO task (agent_id, title, description, project_path, status, created_at, started_at, updated_at, "
                "session_id, tool_use_id, claude_agent_id, last_activity_at, parent_task_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    agent["id"], title, description, project_path, status, now,
                    now if status == "IN_PROGRESS" else None, now, session_id, tool_use_id, claude_agent_id, now,
                    parent_task_id,
                ),
            )
        except sqlite3.IntegrityError:
            # Letzte Verteidigungslinie: der partielle Unique-Index hat zugeschlagen.
            active = self._active_row(conn, agent["id"])
            if active is None:
                raise
            raise self._busy_error(active) from None
        return int(cur.lastrowid)

    def _reject_busy(self, conn: sqlite3.Connection, op: _Op, active: sqlite3.Row, actor: str, what: str) -> None:
        self._event(conn, active["id"], "START_REJECTED", f"{what} abgelehnt: Agent beschäftigt", actor)
        op.changed = True
        op.error = self._busy_error(active)

    def start_task(self, agent: str, title: str, description: str = "", project_path: str | None = None) -> dict:
        """MCP team.start_task: reserviert den Agenten und legt einen REGISTERED-Auftrag an."""
        title, description = self._validate_text(title, description)

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            agent_row = self._agent_row(conn, agent)
            active = self._active_row(conn, agent_row["id"])
            if active:
                self._reject_busy(conn, op, active, "agent", f"Auftrag „{title}“")
                return None
            task_id = self._insert_task(
                conn, agent_row, title=title, description=description, project_path=project_path, status="REGISTERED"
            )
            self._event(conn, task_id, "TASK_REGISTERED", "Über start_task registriert", "agent")
            op.changed = True
            return _task_dict(self._task_row(conn, task_id))

        return self._write(run)

    def reserve_for_delegation(
        self, agent: str, title: str, description: str, project_path: str | None, session_id: str | None, tool_use_id: str | None,
        delegator_agent_id: str | None = None,
    ) -> dict:
        """PreToolUse(Agent): reserviert atomar. Übernimmt einen per start_task vorregistrierten Auftrag.

        delegator_agent_id ist die agent_id des Subagenten, der das Agent-Tool aufruft (None: Hauptsession).
        Ist der Aufrufer ein Teammitglied, muss sein Profil `can_delegate` setzen. Der neue Auftrag wird
        dann als Unterauftrag an dessen Auftrag gehängt.
        """
        title, description = self._validate_text(title or f"Auftrag an {agent}", description)

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            if tool_use_id:
                existing = conn.execute(_TASK_SELECT + " WHERE t.tool_use_id = ?", (tool_use_id,)).fetchone()
                if existing:  # Hook-Wiederholung
                    return _task_dict(existing)
            agent_row = self._agent_row(conn, agent)
            parent = None
            if delegator_agent_id:  # fremde, nicht registrierte Subagenten bleiben wie bisher ohne Elternauftrag
                parent = conn.execute(_TASK_SELECT + " WHERE t.claude_agent_id = ?", (delegator_agent_id,)).fetchone()
            if parent is not None:
                denial = None
                if not parent["agent_can_delegate"]:
                    denial = f"{parent['agent_display_name']} darf keine anderen Agenten beauftragen."
                elif parent["agent_name"] == agent_row["name"]:
                    denial = "Ein Agent darf sich nicht selbst beauftragen."
                if denial:
                    self._event(conn, parent["id"], "DELEGATION_REJECTED", f"Delegation an {agent_row['display_name']} abgelehnt: {denial}", "hook")
                    op.changed = True
                    op.error = Forbidden(denial, details={"task_id": parent["id"]})
                    return None
            parent_id = parent["id"] if parent is not None else None

            def note_delegation(child_id: int) -> None:
                if parent_id is not None:
                    self._event(
                        conn, parent_id, "DELEGATED",
                        f"An {agent_row['display_name']} delegiert: Auftrag #{child_id} „{title}“", "hook",
                    )

            active = self._active_row(conn, agent_row["id"])
            if active:
                adoptable = (
                    active["status"] == "REGISTERED"
                    and active["tool_use_id"] is None
                    and (active["project_path"] is None or _norm_path(active["project_path"]) == _norm_path(project_path))
                )
                if not adoptable:
                    self._reject_busy(conn, op, active, "hook", f"Delegation „{title}“")
                    return None
                conn.execute(
                    "UPDATE task SET tool_use_id = ?, session_id = ?, project_path = COALESCE(project_path, ?), "
                    "description = CASE WHEN description = '' THEN ? ELSE description END, "
                    "parent_task_id = COALESCE(parent_task_id, ?), last_activity_at = ?, updated_at = ? WHERE id = ?",
                    (tool_use_id, session_id, project_path, description, parent_id, self._ts(), self._ts(), active["id"]),
                )
                self._event(conn, active["id"], "TASK_ADOPTED", "Vorregistrierter Auftrag der Delegation zugeordnet", "hook")
                note_delegation(active["id"])
                op.changed = True
                return _task_dict(self._task_row(conn, active["id"]))
            task_id = self._insert_task(
                conn, agent_row, title=title, description=description, project_path=project_path,
                status="REGISTERED", session_id=session_id, tool_use_id=tool_use_id, parent_task_id=parent_id,
            )
            origin = f"Delegation von {parent['agent_display_name']} (Auftrag #{parent_id})" if parent_id else "Delegation"
            self._event(conn, task_id, "TASK_REGISTERED", f"Durch {origin} reserviert, Start noch unbestätigt", "hook")
            note_delegation(task_id)
            op.changed = True
            return _task_dict(self._task_row(conn, task_id))

        return self._write(run)

    # ------------------------------------------------------------------ Hook-Ereignisse

    def confirm_start(self, session_id: str | None, agent_type: str, claude_agent_id: str) -> dict:
        """SubagentStart: erst jetzt gilt der Start als bestätigt. Liefert {'task': ..} oder {'untracked': Grund}."""

        def run(conn: sqlite3.Connection, op: _Op) -> dict:
            known = conn.execute(_TASK_SELECT + " WHERE t.claude_agent_id = ?", (claude_agent_id,)).fetchone()
            if known:  # Hook-Wiederholung
                return {"task": _task_dict(known)}
            agent_row = conn.execute("SELECT * FROM agent WHERE name = ? AND enabled = 1", (agent_type.lower(),)).fetchone()
            if agent_row is None:
                return {}
            registered = conn.execute(
                _TASK_SELECT + " WHERE t.agent_id = ? AND t.status = 'REGISTERED' AND t.claude_agent_id IS NULL "
                "ORDER BY t.id DESC LIMIT 1",
                (agent_row["id"],),
            ).fetchone()
            if registered and registered["session_id"] and session_id and registered["session_id"] != session_id:
                registered = None  # Reservierung einer anderen Session
            if registered:
                ok = self._transition(
                    conn, op, registered, "IN_PROGRESS", "hook",
                    message="Start bestätigt (SubagentStart)",
                    fields={"claude_agent_id": claude_agent_id, "last_activity_at": self._ts(),
                            "session_id": registered["session_id"] or session_id},
                )
                return {"task": _task_dict(self._task_row(conn, registered["id"]))} if ok else {}
            active = self._active_row(conn, agent_row["id"])
            if active:
                self._event(conn, active["id"], "UNTRACKED_START",
                            f"Subagent {claude_agent_id} ohne Reservierung gestartet, Agent beschäftigt", "hook")
                op.changed = True
                return {"untracked": self._busy_error(active).message}
            task_id = self._insert_task(
                conn, agent_row, title=f"Ohne Reservierung gestartet ({agent_row['display_name']})", description="",
                project_path=None, status="IN_PROGRESS", session_id=session_id, claude_agent_id=claude_agent_id,
            )
            self._event(conn, task_id, "UNRESERVED_START", "SubagentStart ohne vorherige Reservierung", "hook")
            op.changed = True
            return {"task": _task_dict(self._task_row(conn, task_id))}

        return self._write(run)

    def touch_activity(self, claude_agent_id: str) -> None:
        """Aktivitätsnachweis eines Subagenten. Hebt einen Verwaist-Verdacht wieder auf."""
        with self.db.write() as conn:
            conn.execute(
                f"UPDATE task SET last_activity_at = ?, orphan_suspected = 0 "
                f"WHERE claude_agent_id = ? AND status IN {_ACTIVE_SQL}",
                (self._ts(), claude_agent_id),
            )

    def record_handback(self, claude_agent_id: str, message: str) -> None:
        """SubagentHandback: die letzte Antwort des Subagenten, Grundlage der Zusammenfassung bei fehlender Abschlussmeldung."""
        with self.db.write() as conn:
            row = conn.execute("SELECT id FROM task WHERE claude_agent_id = ?", (claude_agent_id,)).fetchone()
            if row:
                self._event(conn, row["id"], "HANDBACK", _clip(message, _MAX_TEXT), "hook")

    def subagent_stopped(self, claude_agent_id: str, transcript_path: str | None) -> dict | None:
        """SubagentStop: Abschluss erkannt. Ohne Abschlussmeldung des Agenten -> REVIEW_REQUIRED, aber unvollständig."""

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            task = conn.execute(_TASK_SELECT + " WHERE t.claude_agent_id = ?", (claude_agent_id,)).fetchone()
            if task is None:
                return None
            conn.execute("UPDATE task SET agent_stopped_at = ? WHERE id = ?", (self._ts(), task["id"]))
            handback = conn.execute(
                "SELECT message FROM task_event WHERE task_id = ? AND event_type = 'HANDBACK' ORDER BY id DESC LIMIT 1",
                (task["id"],),
            ).fetchone()
            if task["status"] == "IN_PROGRESS":
                summary = handback["message"] if handback else "(Der Agent hat keine Abschlussmeldung abgegeben.)"
                self._transition(
                    conn, op, task, "REVIEW_REQUIRED", "hook",
                    message="Abschluss erkannt, Ergebnis unvollständig (keine complete_task-Meldung)",
                    fields={"completion_incomplete": 1, "summary": summary, "result_reference": transcript_path},
                )
            else:
                self._event(conn, task["id"], "SUBAGENT_STOPPED", f"Status bei Stop: {task['status']}", "hook")
                if task["status"] == "REVIEW_REQUIRED" and transcript_path:
                    conn.execute(
                        "UPDATE task SET result_reference = COALESCE(result_reference, ?) WHERE id = ?",
                        (transcript_path, task["id"]),
                    )
                op.changed = True
            return _task_dict(self._task_row(conn, task["id"]))

        return self._write(run)

    def start_failed(self, tool_use_id: str, error: str) -> None:
        """PostToolUseFailure(Agent): der Start ist nicht zustande gekommen."""

        def run(conn: sqlite3.Connection, op: _Op) -> None:
            task = conn.execute(_TASK_SELECT + " WHERE t.tool_use_id = ?", (tool_use_id,)).fetchone()
            if task and task["status"] == "REGISTERED":
                reason = f"Start fehlgeschlagen: {_clip(error, 300)}"
                self._transition(conn, op, task, "FAILED", "hook", message=reason, fields={"failure_reason": reason})

        self._write(run)

    def session_ended(self, session_id: str, reason: str | None = None) -> int:
        """SessionEnd: aktive Aufträge der Session werden als möglicherweise verwaist gekennzeichnet (nie als erfolgreich).

        Vermerkt außerdem das Ende der Session selbst. Eine nie gesehene Session wird nicht angelegt: ihr Start ist
        unbekannt (etwa vor einem Neustart des Dienstes), ein Eintrag ohne Start wäre irreführend.
        """

        def run(conn: sqlite3.Connection, op: _Op) -> int:
            ended = conn.execute(
                "UPDATE session SET ended_at = ?, end_reason = ? WHERE session_id = ? AND ended_at IS NULL",
                (self._ts(), reason or None, session_id),
            ).rowcount
            rows = conn.execute(
                f"SELECT id FROM task WHERE session_id = ? AND status IN {_ACTIVE_SQL} AND session_ended_at IS NULL",
                (session_id,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE task SET session_ended_at = ?, orphan_suspected = 1, updated_at = ? WHERE id = ?",
                    (self._ts(), self._ts(), row["id"]),
                )
                self._event(conn, row["id"], "SESSION_ENDED", "Claude-Code-Session beendet, Auftrag möglicherweise verwaist", "hook")
            op.changed = bool(rows) or bool(ended)
            return len(rows)

        return self._write(run)

    # ------------------------------------------------------------------ Sessions

    def session_seen(
        self, session_id: str, cwd: str | None = None, *, reopen: bool = False, prompt: str | None = None
    ) -> None:
        """Ein Hook mit dieser session_id ist eingetroffen: die Session anlegen oder ihre Aktivität vermerken.

        Mit prompt (nur UserPromptSubmit) wird der erste Prompt der Session als ihr Auftrag festgehalten.

        Der erste Hook einer unbekannten session_id gilt als Start. Eine beendete Session wird nur wieder geöffnet,
        wenn der Benutzer in ihr etwas eingibt (reopen, z. B. bei --resume). Nachzügler-Hooks nach SessionEnd
        lassen sie beendet. Ohne Änderung wird nicht geschrieben, denn PostToolUse feuert für jeden Tool-Aufruf.
        """
        sid = (session_id or "").strip()
        if not sid:
            return
        cwd = (cwd or "").strip() or None
        prompt = _session_job(prompt)
        now = self._clock()
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT cwd, first_prompt, last_seen_at, ended_at FROM session WHERE session_id = ?", (sid,)
            ).fetchone()
        if row is not None:
            if row["ended_at"] and not reopen:
                return
            fresh = now - datetime.fromisoformat(row["last_seen_at"]) < timedelta(seconds=_SESSION_TOUCH_S)
            if fresh and not row["ended_at"] and not (cwd and not row["cwd"]) and not (prompt and not row["first_prompt"]):
                return

        def run(conn: sqlite3.Connection, op: _Op) -> None:
            stamp = self._ts()
            current = conn.execute(
                "SELECT cwd, first_prompt, ended_at FROM session WHERE session_id = ?", (sid,)
            ).fetchone()
            if current is None:
                conn.execute(
                    "INSERT INTO session (session_id, cwd, first_prompt, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
                    (sid, cwd, prompt, stamp, stamp),
                )
                op.changed = True
                return
            if current["ended_at"] and not reopen:
                return
            conn.execute(
                "UPDATE session SET last_seen_at = ?, cwd = COALESCE(cwd, ?), first_prompt = COALESCE(first_prompt, ?), "
                "ended_at = NULL, end_reason = NULL WHERE session_id = ?",
                (stamp, cwd, prompt, sid),
            )
            # sonst nur last_seen_at: kein Bus-Ereignis
            op.changed = bool(current["ended_at"]) or bool(cwd and not current["cwd"]) or bool(prompt and not current["first_prompt"])

        self._write(run)

    def list_sessions(self, limit: int = 50) -> list[dict]:
        """Laufende Sessions zuerst (zuletzt aktive oben), danach die beendeten (zuletzt beendete oben).

        Jede Session trägt ihre Aufträge (auch Unteraufträge) in der Reihenfolge der Auftragsnummern.
        """
        with self.db.read() as conn:
            rows = conn.execute(
                "SELECT * FROM session "
                "ORDER BY ended_at IS NOT NULL, CASE WHEN ended_at IS NULL THEN last_seen_at ELSE ended_at END DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
            ids = [r["session_id"] for r in rows]
            by_session: dict[str, list[dict]] = {sid: [] for sid in ids}
            if ids:
                marks = ",".join("?" for _ in ids)
                for t in conn.execute(
                    "SELECT t.id, t.title, t.status, t.parent_task_id, t.session_id, "
                    "a.name AS agent_name, a.display_name AS agent_display_name "
                    f"FROM task t JOIN agent a ON a.id = t.agent_id WHERE t.session_id IN ({marks}) ORDER BY t.id",
                    ids,
                ):
                    by_session[t["session_id"]].append({k: t[k] for k in t.keys() if k != "session_id"})
        sessions = []
        for r in rows:
            tasks = by_session[r["session_id"]]
            sessions.append({
                **dict(r),
                "active": r["ended_at"] is None,
                "tasks": tasks,
                "task_count": len(tasks),
                "active_task_count": sum(1 for t in tasks if t["status"] in ACTIVE_STATUSES),
            })
        return sessions

    # ------------------------------------------------------------------ Agenten-Werkzeuge (MCP)

    def _owned_task(self, conn: sqlite3.Connection, op: _Op, task_id: int, caller_agent_id: str | None) -> sqlite3.Row | None:
        task = self._task_row(conn, task_id)
        if not caller_agent_id or task["claude_agent_id"] != caller_agent_id:
            self._event(conn, task_id, "OWNERSHIP_REJECTED", "Zugriff einer fremden oder unbekannten Session abgelehnt", "agent")
            op.changed = True
            op.error = NotTaskOwner(
                f"Auftrag {task_id} gehört nicht zu dieser Agentensitzung.", details={"task_id": task_id}
            )
            return None
        return task

    def agent_update(self, caller_agent_id: str | None, task_id: int, status: str | None, message: str) -> dict | None:
        status = (status or "").strip().upper() or None
        message = _clip(message, _MAX_TEXT)

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            task = self._owned_task(conn, op, task_id, caller_agent_id)
            if task is None:
                return None
            if status and status not in (task["status"], "IN_PROGRESS"):
                check_transition_ok = self._transition_probe(conn, op, task, status)
                if not check_transition_ok:
                    return None
                op.error = ServiceError(
                    "Verwende report_blocker für Blocker und complete_task für den Abschluss.", code=None
                )
                return None
            if status == "IN_PROGRESS" and task["status"] == "BLOCKED":
                if not self._transition(conn, op, task, "IN_PROGRESS", "agent", message=message or "Blocker aufgelöst",
                                        fields={"last_activity_at": self._ts(), "orphan_suspected": 0}):
                    return None
            elif task["status"] not in ACTIVE_STATUSES:
                self._reject(conn, op, task, "update_task bei beendetem Auftrag")
                return None
            else:
                conn.execute(
                    "UPDATE task SET last_activity_at = ?, updated_at = ?, orphan_suspected = 0 WHERE id = ?",
                    (self._ts(), self._ts(), task_id),
                )
                self._event(conn, task_id, "PROGRESS", message, "agent")
                op.changed = True
            return _task_dict(self._task_row(conn, task_id))

        return self._write(run)

    def _transition_probe(self, conn: sqlite3.Connection, op: _Op, task: sqlite3.Row, to: str) -> bool:
        """Prüft einen gewünschten Agentenübergang nur auf Zulässigkeit; bei Ablehnung wird protokolliert."""
        try:
            check_transition(task["status"], to, "agent")
        except InvalidTransition as exc:
            self._event(conn, task["id"], "TRANSITION_REJECTED", f"{task['status']} -> {to} durch agent abgelehnt", "agent")
            op.error, op.changed = exc, True
            return False
        return True

    def _reject(self, conn: sqlite3.Connection, op: _Op, task: sqlite3.Row, what: str) -> None:
        self._event(conn, task["id"], "TRANSITION_REJECTED", f"{what}: Status {task['status']}", "agent")
        op.changed = True
        op.error = InvalidTransition(
            f"Auftrag {task['id']} ist {task['status']}; {what} ist nicht mehr möglich.",
            details={"status": task["status"]},
        )

    def agent_complete(self, caller_agent_id: str | None, task_id: int, summary: str, result_reference: str | None) -> dict | None:
        summary = _clip(summary, _MAX_TEXT)
        if not summary:
            raise ServiceError("Die Zusammenfassung (summary) darf nicht leer sein.")

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            task = self._owned_task(conn, op, task_id, caller_agent_id)
            if task is None:
                return None
            open_children = conn.execute(
                f"SELECT t.id, a.display_name FROM task t JOIN agent a ON a.id = t.agent_id "
                f"WHERE t.parent_task_id = ? AND t.status IN {_ACTIVE_SQL} ORDER BY t.id",
                (task_id,),
            ).fetchall()
            if open_children:
                listing = ", ".join(f"#{c['id']} ({c['display_name']})" for c in open_children)
                self._event(conn, task_id, "TRANSITION_REJECTED", f"complete_task abgelehnt: Unteraufträge laufen noch: {listing}", "agent")
                op.changed = True
                op.error = InvalidTransition(
                    f"Unteraufträge laufen noch: {listing}. Warte auf deren Ergebnis (get_task) oder melde einen Blocker.",
                    details={"open_children": [c["id"] for c in open_children]},
                )
                return None
            ok = self._transition(
                conn, op, task, "REVIEW_REQUIRED", "agent", message=summary,
                fields={"summary": summary, "result_reference": _clip(result_reference, 2000) or None,
                        "completion_incomplete": 0, "orphan_suspected": 0},
            )
            return _task_dict(self._task_row(conn, task_id)) if ok else None

        return self._write(run)

    def agent_blocker(self, caller_agent_id: str | None, task_id: int, reason: str) -> dict | None:
        reason = _clip(reason, _MAX_TEXT)
        if not reason:
            raise ServiceError("Der Blocker-Grund (reason) darf nicht leer sein.")

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            task = self._owned_task(conn, op, task_id, caller_agent_id)
            if task is None:
                return None
            if task["status"] == "BLOCKED":  # idempotent: Grund aktualisieren
                self._event(conn, task_id, "BLOCKER_UPDATED", reason, "agent")
                op.changed = True
            elif not self._transition(conn, op, task, "BLOCKED", "agent", message=reason):
                return None
            return _task_dict(self._task_row(conn, task_id))

        return self._write(run)

    # ------------------------------------------------------------------ Benutzeraktionen

    def user_action(self, task_id: int, action: str, note: str = "") -> dict:
        target = USER_ACTIONS.get(action)
        if target is None:
            raise ServiceError(f"Unbekannte Aktion '{action}'.")
        note = _clip(note, 1000)

        def run(conn: sqlite3.Connection, op: _Op) -> dict | None:
            task = self._task_row(conn, task_id)
            if action == "unblock" and task["agent_stopped_at"]:
                self._event(conn, task_id, "TRANSITION_REJECTED", "Blocker lösen nicht möglich: Agent läuft nicht mehr", "user")
                op.changed = True
                op.error = InvalidTransition(
                    "Der Agent läuft nicht mehr. Bitte den Auftrag abbrechen und neu beauftragen.", details={"task_id": task_id}
                )
                return None
            fields: dict[str, Any] = {}
            if action == "fail":
                fields["failure_reason"] = note or "Vom Benutzer als fehlgeschlagen markiert"
            if action == "cancel" and task["status"] in ACTIVE_STATUSES:
                fields["failure_reason"] = note or "Vom Benutzer abgebrochen"
            if action == "unblock":
                fields.update(last_activity_at=self._ts(), orphan_suspected=0)
            ok = self._transition(conn, op, task, target, "user", message=note, fields=fields)
            if ok and action == "done":
                self._accept_children(conn, op, task_id)
            return _task_dict(self._task_row(conn, task_id)) if ok else None

        return self._write(run)

    def _accept_children(self, conn: sqlite3.Connection, op: _Op, parent_id: int) -> None:
        """Mit dem Elternauftrag sind auch dessen abgelieferte Unteraufträge abgenommen (ein Feedback für alles).

        Unvollständige Abschlüsse bleiben außen vor: sie waren nie über den Elternauftrag abgedeckt und
        warten weiter einzeln auf den Benutzer.
        """
        children = conn.execute(
            _TASK_SELECT + " WHERE t.parent_task_id = ? AND t.status = 'REVIEW_REQUIRED' AND t.completion_incomplete = 0 ORDER BY t.id",
            (parent_id,),
        ).fetchall()
        accepted = [c["id"] for c in children if self._transition(conn, op, c, "DONE", "user", message=f"Mit Auftrag #{parent_id} abgenommen")]
        if accepted:
            self._event(conn, parent_id, "CHILDREN_ACCEPTED", "Unteraufträge mit abgenommen: " + ", ".join(f"#{i}" for i in accepted), "user")
        for child_id in accepted:
            self._accept_children(conn, op, child_id)

    # ------------------------------------------------------------------ Watchdog

    def run_watchdog(self) -> list[int]:
        """Prüft Zeitbedingungen. Gibt die IDs der veränderten Aufträge zurück."""
        now = self._clock()
        s = self.settings

        def parse(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        def run(conn: sqlite3.Connection, op: _Op) -> list[int]:
            changed: list[int] = []
            rows = conn.execute(_TASK_SELECT + f" WHERE t.status IN {_ACTIVE_SQL}").fetchall()
            for t in rows:
                last = parse(t["last_activity_at"]) or parse(t["started_at"]) or parse(t["created_at"])
                if t["status"] == "REGISTERED" and t["claude_agent_id"] is None:
                    if now - last > timedelta(seconds=s.registered_timeout_s):
                        reason = "Start nicht bestätigt (kein SubagentStart innerhalb der Frist)"
                        if self._transition(conn, op, t, "FAILED", "watchdog", message=reason, fields={"failure_reason": reason}):
                            changed.append(t["id"])
                    continue
                if t["status"] != "IN_PROGRESS":
                    continue  # BLOCKED wartet bewusst auf den Benutzer
                ended = parse(t["session_ended_at"])
                if ended and last <= ended and now - ended > timedelta(seconds=s.session_end_grace_s):
                    reason = "Session beendet (Fenster geschlossen?), keine Aktivität mehr"
                    if self._transition(conn, op, t, "FAILED", "watchdog", message=reason, fields={"failure_reason": reason}):
                        changed.append(t["id"])
                    continue
                if not t["orphan_suspected"] and now - last > timedelta(seconds=s.orphan_timeout_s):
                    conn.execute("UPDATE task SET orphan_suspected = 1, updated_at = ? WHERE id = ?", (self._ts(), t["id"]))
                    self._event(conn, t["id"], "ORPHAN_SUSPECTED",
                                f"Keine Aktivität seit {int((now - last).total_seconds() // 60)} Minuten", "watchdog")
                    op.changed = True
                    changed.append(t["id"])
            return changed

        return self._write(run)

    # ------------------------------------------------------------------ Lesen

    @staticmethod
    def _attach_blocker_reasons(conn: sqlite3.Connection, tasks: list[dict]) -> None:
        """Hängt an blockierte Aufträge den zuletzt gemeldeten Grund (steht im Ereignisprotokoll)."""
        blocked = [t["id"] for t in tasks if t["status"] == "BLOCKED"]
        reasons: dict[int, str] = {}
        if blocked:
            marks = ",".join("?" for _ in blocked)
            rows = conn.execute(
                "SELECT task_id, message FROM task_event WHERE id IN ("
                "SELECT MAX(id) FROM task_event WHERE event_type IN ('STATUS_BLOCKED', 'BLOCKER_UPDATED') "
                f"AND task_id IN ({marks}) GROUP BY task_id)",
                blocked,
            ).fetchall()
            reasons = {r["task_id"]: r["message"] for r in rows}
        for t in tasks:
            t["blocker_reason"] = reasons.get(t["id"])

    def get_task(self, task_id: int, *, events: int = 50) -> dict:
        with self.db.read() as conn:
            task = _task_dict(self._task_row(conn, task_id))
            self._attach_blocker_reasons(conn, [task])
            parent = task["parent_task_id"] and conn.execute(
                _TASK_SELECT + " WHERE t.id = ?", (task["parent_task_id"],)
            ).fetchone()
            task["parent"] = (
                {"id": parent["id"], "title": parent["title"], "agent_display_name": parent["agent_display_name"]}
                if parent else None
            )
            task["children"] = [
                {
                    "id": c["id"], "title": c["title"], "status": c["status"], "agent_display_name": c["agent_display_name"],
                    "summary": c["summary"], "result_reference": c["result_reference"],
                    "completion_incomplete": bool(c["completion_incomplete"]),
                }
                for c in conn.execute(_TASK_SELECT + " WHERE t.parent_task_id = ? ORDER BY t.id", (task_id,))
            ]
            rows = conn.execute(
                "SELECT id, event_type, message, actor, timestamp FROM task_event WHERE task_id = ? ORDER BY id DESC LIMIT ?",
                (task_id, events),
            ).fetchall()
            task["events"] = [dict(r) for r in reversed(rows)]
            return task

    def list_tasks(self, filter_name: str = "all", limit: int = 500) -> list[dict]:
        if filter_name not in FILTERS:
            raise ServiceError(f"Unbekannter Filter '{filter_name}'.")
        statuses = FILTERS[filter_name]
        with self.db.read() as conn:
            where, params = "", []
            if statuses:
                where = " WHERE t.status IN (" + ",".join("?" for _ in statuses) + ")"
                params = list(statuses)
            rows = conn.execute(_TASK_SELECT + where + " ORDER BY t.id DESC LIMIT ?", (*params, limit)).fetchall()
            tasks = [_task_dict(r) for r in rows]
            self._attach_blocker_reasons(conn, tasks)
            return tasks

    def snapshot(self) -> dict:
        tasks = self.list_tasks("all")
        count = lambda *st: sum(1 for t in tasks if t["status"] in st)  # noqa: E731
        return {
            "server_time": self._ts(),
            "agents": self.list_agents(),
            "tasks": tasks,
            "sessions": self.list_sessions(),
            "attention": {
                # Nur Reviews, die beim Benutzer liegen. Abgelieferte Unteraufträge laufen über ihren Elternauftrag.
                "review": sum(1 for t in tasks if t["status"] == "REVIEW_REQUIRED" and not t["review_covered"]),
                "blocked": count("BLOCKED"),
                "orphans": sum(1 for t in tasks if t["orphan_suspected"] and t["status"] in ACTIVE_STATUSES),
            },
        }
