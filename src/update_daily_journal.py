"""Create or update a daily journal markdown file.

The journal contains, in order:
- Appointments from today's calendar
- Wochenziele (Montag) / Erreichung Wochenziele (Freitag) (manual, preserved on updates)
- Top 3 scored Jira Tasks
- Langlaufende Tasks (automatic: tickets stuck in "In Progress" for >3 days)
- Reflektion: Mein Tag heute (manual, preserved on updates; interview template as default)

Usage:
    py src/update_daily_journal.py --date 2026-03-23
    py src/update_daily_journal.py --date 2026-03-23 --journal-dir journal
    py src/update_daily_journal.py --stub-only
        (nur leere Vorlage, kein Jira; bricht ab, wenn die Datei schon existiert)
    py src/update_daily_journal.py --stub-only-if-missing
        (wie --stub-only, aber erfolgreich, wenn die Datei schon existiert – z. B. Auto-Start)
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from get_schedule_for_today import get_schedule_for_today
from prioritize_my_jira_issues import get_ranked_issues


def _candidate_jira_helper_dirs() -> list[Path]:
    """Return likely locations for the shared Jira skill helper script."""
    candidates: list[Path] = []
    script_dir = Path(__file__).resolve().parent
    candidates.append(script_dir)

    for env_name in ("CURSOR_JIRA_SKILL_SRC", "JIRA_SKILL_SRC"):
        configured = os.getenv(env_name)
        if configured:
            candidates.append(Path(configured).expanduser())

    home = Path.home()
    candidates.extend(
        [
            home / ".claude" / "skills" / "jira" / "src",
            home / ".cursor" / "skills" / "jira" / "src",
            home / "Dev" / "props-cursor-plugins" / "skills" / "jira" / "src",
        ]
    )

    plugin_cache = home / ".cursor" / "plugins" / "cache"
    if plugin_cache.exists():
        candidates.extend(plugin_cache.glob("**/skills/jira/src"))

    return candidates


def _find_jira_helper_file() -> Path:
    for candidate in _candidate_jira_helper_dirs():
        helper_file = candidate / "read_jira_issue.py"
        if helper_file.is_file():
            return helper_file

    searched = "\n".join(f"- {path}" for path in _candidate_jira_helper_dirs())
    raise ModuleNotFoundError(
        "Could not find read_jira_issue.py. Install the jira user skill or set "
        f"CURSOR_JIRA_SKILL_SRC to its src directory.\nSearched:\n{searched}"
    )


def _load_jira_helpers() -> tuple[Any, Any]:
    helper_file = _find_jira_helper_file()
    spec = importlib.util.spec_from_file_location("cursor_jira_read_issue", helper_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Jira helper module from {helper_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, "_jira_get"), getattr(module, "_jira_search")


_jira_get, _jira_search = _load_jira_helpers()

JIRA_BASE_URL = "https://trustedshops.atlassian.net"
SCHEDULE_TIME_ZONE = ZoneInfo("Europe/Berlin")
EXCLUDED_APPOINTMENT_SUBJECTS = frozenset(
    {
        "blocked",
        "blocker",
        "meeting free morning",
    }
)

REFLECTION_TEMPLATE = (
    "- Was ich heute gemacht habe:\n"
    "\t- ...\n"
    "- So ging es mir energetisch - insbesondere zum Feierabend:\n"
    "\t- ...\n"
    "- Das war wichtiger Outcome aus Terminen:\n"
    "\t- ..."
)

DEFAULT_MANUAL_PLACEHOLDER = "<!-- Optional durch Nutzer gepflegt -->"


@dataclass
class InProgressTicket:
    key: str
    summary: str


@dataclass
class Appointment:
    start: datetime
    end: datetime
    subject: str


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_schedule_dt(value: str | None) -> datetime | None:
    """Interpret offset-free schedule timestamps as UTC and convert to Berlin time."""
    dt = _parse_iso_dt(value)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(SCHEDULE_TIME_ZONE)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return " ".join(text.split())


def _collect_appointments(day: date) -> tuple[list[Appointment], bool]:
    """Return appointments for the journal day and whether their retrieval succeeded."""
    if day != date.today():
        return [], True

    try:
        schedule = get_schedule_for_today()
    except Exception as exc:
        print(f"Warnung: Termine konnten nicht abgerufen werden: {exc}", file=sys.stderr)
        return [], False

    appointments: list[Appointment] = []
    for item in schedule:
        start = _parse_schedule_dt(_safe_text(item.get("start")))
        end = _parse_schedule_dt(_safe_text(item.get("end")))
        subject = _safe_text(item.get("subject")) or "(ohne Betreff)"
        if (
            not start
            or not end
            or start.date() != day
            or subject.casefold() in EXCLUDED_APPOINTMENT_SUBJECTS
        ):
            continue
        appointments.append(
            Appointment(
                start=start,
                end=end,
                subject=subject,
            )
        )

    appointments.sort(key=lambda appointment: (appointment.start, appointment.end, appointment.subject))
    return appointments, True


def _format_appointments_section(appointments: list[Appointment], retrieved: bool) -> str:
    lines = ["## Termine", ""]
    if not retrieved:
        lines.append("- Termine konnten nicht abgerufen werden.")
    elif not appointments:
        lines.append("- Keine Termine.")
    else:
        for appointment in appointments:
            lines.append(
                f"- {appointment.start.strftime('%H:%M')} - "
                f"{appointment.end.strftime('%H:%M')}: {appointment.subject}"
            )
    return "\n".join(lines) + "\n"


def _collect_long_running_tickets() -> list[InProgressTicket]:
    """Snapshot of own/unassigned-KH tickets stuck in "In Progress" for >3 days."""
    jql = (
        "(assignee = currentUser() OR project = KH) "
        "AND issuetype != Epic "
        'AND status = "In Progress" '
        'AND NOT status CHANGED AFTER "-3d" '
        "ORDER BY key ASC"
    )
    fields = ["summary", "issuetype"]
    issues = _jira_search(jql=jql, fields=fields, max_results=2000)

    out: list[InProgressTicket] = []
    seen: set[str] = set()
    for issue in issues:
        key = (issue.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        summary = ((issue.get("fields") or {}).get("summary") or "").strip()
        out.append(InProgressTicket(key=key, summary=summary))
    return out


def _format_long_running_tickets_section(tickets: list[InProgressTicket]) -> str:
    lines = ["## Langlaufende Tasks", ""]
    if not tickets:
        lines.append("- Keine Langläufer.")
    else:
        for ticket in tickets:
            lines.append(f"- [{ticket.key}]({JIRA_BASE_URL}/browse/{ticket.key}) - {ticket.summary}")
    return "\n".join(lines) + "\n"


def _journal_path_for_day(day: date, journal_dir: str) -> str:
    yy = day.strftime("%y")
    mm = day.strftime("%m")
    dd = day.strftime("%d")
    yyyy_mm = day.strftime("%Y-%m")
    return os.path.join(journal_dir, yyyy_mm, f"journal-{yy}-{mm}-{dd}.md")


def _weekday_manual_goal_header(day: date) -> str | None:
    """Return the manual weekly-goal header for the given day, or None."""
    if day.weekday() == 0:
        return "## Wochenziele"
    if day.weekday() == 4:
        return "## Erreichung Wochenziele"
    return None


def _extract_section_content(
    existing_text: str,
    header: str,
    next_headers: list[str],
    default: str,
) -> str:
    """Return the body between `header` and the nearest following header in `next_headers`.

    Falls back to `default` if the header is missing or its body is empty.
    """
    start = existing_text.find(header)
    if start < 0:
        return default
    start = start + len(header)

    end = -1
    for next_header in next_headers:
        candidate = existing_text.find(next_header, start)
        if candidate >= 0 and (end < 0 or candidate < end):
            end = candidate

    body = existing_text[start:].strip("\n") if end < 0 else existing_text[start:end].strip("\n")
    return body if body.strip() else default


def _format_top_scored_jira_tasks_section(tasks: list[dict[str, Any]]) -> str:
    """Format the top-ranked Jira tasks as compact Markdown list items."""
    lines = ["## Top 3 scored Jira Tasks", ""]
    if not tasks:
        lines.append("- Keine offenen Jira-Tasks im Ranking gefunden.")
        return "\n".join(lines) + "\n"

    for task in tasks[:3]:
        key = _safe_text(task.get("key")) or "(ohne Key)"
        summary = _safe_text(task.get("summary")) or "(ohne Summary)"
        lines.append(f"- {key} - {summary}")

    return "\n".join(lines) + "\n"


def update_daily_journal(day: date, journal_dir: str) -> str:
    journal_path = _journal_path_for_day(day, journal_dir)
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)

    existing_text = ""
    if os.path.exists(journal_path):
        with open(journal_path, "r", encoding="utf-8") as f:
            existing_text = f.read()

    goal_header = _weekday_manual_goal_header(day)
    reflection_content = _extract_section_content(
        existing_text,
        "## Reflektion: Mein Tag heute",
        ["## Generierter Inhalt (Jira)"],  # Legacy-Abschnitt alter Journals wird verworfen
        default=REFLECTION_TEMPLATE,
    )
    appointments, appointments_retrieved = _collect_appointments(day)
    top_scored_tasks = get_ranked_issues()[:3]
    long_running_tickets = _collect_long_running_tickets()

    header = f"# Journal {day.isoformat()}\n\n"
    appointments_section = _format_appointments_section(appointments, appointments_retrieved)

    goal_section = ""
    if goal_header is not None:
        goal_content = _extract_section_content(
            existing_text,
            goal_header,
            ["## Top 3 scored Jira Tasks"],
            default=DEFAULT_MANUAL_PLACEHOLDER,
        )
        goal_section = f"{goal_header}\n\n{goal_content.strip()}\n\n"

    top_scored_tasks_section = _format_top_scored_jira_tasks_section(top_scored_tasks)
    long_running_tickets_section = _format_long_running_tickets_section(long_running_tickets)
    reflection_section = f"## Reflektion: Mein Tag heute\n\n{reflection_content.strip()}\n\n"
    content = (
        header
        + appointments_section
        + "\n"
        + goal_section
        + top_scored_tasks_section
        + "\n"
        + long_running_tickets_section
        + "\n"
        + reflection_section
    )

    with open(journal_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"Journal aktualisiert: {journal_path}")
    print(f"Events: termine={len(appointments)}, langlaeufer={len(long_running_tickets)}")
    return journal_path


def _write_journal_stub_filesystem(
    day: date,
    journal_dir: str,
    top_scored_tasks: list[dict[str, Any]] | None = None,
) -> str:
    """Schreibt Stub-Datei. Rufer muss sicherstellen, dass der Pfad noch nicht existiert."""
    journal_path = _journal_path_for_day(day, journal_dir)
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    header = f"# Journal {day.isoformat()}\n\n"
    appointments, appointments_retrieved = _collect_appointments(day)
    appointments_section = _format_appointments_section(appointments, appointments_retrieved)
    top_scored_tasks_section = (
        _format_top_scored_jira_tasks_section(top_scored_tasks)
        if top_scored_tasks is not None
        else ""
    )
    goal_header = _weekday_manual_goal_header(day)
    goal_section = f"{goal_header}\n\n{DEFAULT_MANUAL_PLACEHOLDER}\n\n" if goal_header is not None else ""
    long_running_tickets_section = _format_long_running_tickets_section([])
    reflection_section = f"## Reflektion: Mein Tag heute\n\n{REFLECTION_TEMPLATE}\n\n"
    content = header + appointments_section + "\n" + goal_section
    if top_scored_tasks_section:
        content += top_scored_tasks_section + "\n"
    content += long_running_tickets_section + "\n" + reflection_section

    with open(journal_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"Journal-Vorlage angelegt: {journal_path}")
    return journal_path


def write_journal_stub(day: date, journal_dir: str) -> str:
    """Leere Journal-Vorlage (ohne Jira-Abruf). Überschreibt keine bestehende Datei."""
    journal_path = _journal_path_for_day(day, journal_dir)
    if os.path.exists(journal_path):
        raise SystemExit(f"Journal-Datei existiert bereits: {journal_path}")
    return _write_journal_stub_filesystem(day, journal_dir)


def write_journal_stub_if_missing(day: date, journal_dir: str) -> str:
    """Leere Vorlage nur anlegen, wenn die Datei fehlt; sonst Meldung und kein Fehler."""
    journal_path = _journal_path_for_day(day, journal_dir)
    if os.path.exists(journal_path):
        print(f"Journal-Vorlage unveraendert (existiert): {journal_path}")
        return journal_path
    return _write_journal_stub_filesystem(day, journal_dir)


def write_journal_stub_with_ranking_if_missing(day: date, journal_dir: str) -> str:
    """Lege eine Tagesvorlage mit den drei aktuell höchsten Jira-Rankings an."""
    journal_path = _journal_path_for_day(day, journal_dir)
    if os.path.exists(journal_path):
        print(f"Journal-Vorlage unveraendert (existiert): {journal_path}")
        return journal_path
    return _write_journal_stub_filesystem(
        day,
        journal_dir,
        top_scored_tasks=get_ranked_issues()[:3],
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Create or update daily journal markdown file")
    parser.add_argument(
        "--date",
        help="Journal date in YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--journal-dir",
        default="journal",
        help="Directory for journal markdown files (default: journal)",
    )
    stub_group = parser.add_mutually_exclusive_group()
    stub_group.add_argument(
        "--stub-only",
        action="store_true",
        help="Nur leere Vorlage schreiben (kein Jira); schlaegt fehl, wenn die Datei existiert",
    )
    stub_group.add_argument(
        "--stub-only-if-missing",
        action="store_true",
        help="Wie --stub-only, aber erfolgreich, wenn die Datei schon existiert (idempotent)",
    )
    stub_group.add_argument(
        "--stub-with-ranking-if-missing",
        action="store_true",
        help="Wie --stub-only-if-missing, aber mit den drei hoechsten Jira-Rankings",
    )
    args = parser.parse_args()

    day = date.today()
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError as exc:
            raise SystemExit(f"Ungueltiges Datum fuer --date: {args.date}") from exc

    if args.stub_only:
        write_journal_stub(day=day, journal_dir=args.journal_dir)
        return 0

    if args.stub_only_if_missing:
        write_journal_stub_if_missing(day=day, journal_dir=args.journal_dir)
        return 0

    if args.stub_with_ranking_if_missing:
        write_journal_stub_with_ranking_if_missing(day=day, journal_dir=args.journal_dir)
        return 0

    update_daily_journal(day=day, journal_dir=args.journal_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
