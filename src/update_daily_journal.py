"""Create or update a daily journal markdown file.

The journal contains:
- Manual section (preserved on updates)
- Generated Jira section with day-based activity:
  - Status changes
  - Comments
  - Ticket changes
  - Newly created tickets

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
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _jira_get, _jira_search

JIRA_BASE_URL = "https://trustedshops.atlassian.net"


@dataclass
class StatusChange:
    when: datetime
    key: str
    summary: str
    from_status: str
    to_status: str


@dataclass
class CommentEvent:
    when: datetime
    key: str
    summary: str
    author: str
    body_preview: str


@dataclass
class TicketChange:
    when: datetime
    key: str
    summary: str
    fields: list[str]


@dataclass
class NewTicket:
    when: datetime
    key: str
    summary: str


@dataclass
class InProgressTicket:
    key: str
    summary: str


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_on_day(iso_value: str | None, day: date) -> bool:
    dt = _parse_iso_dt(iso_value)
    return bool(dt and dt.date() == day)


def _hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return " ".join(text.split())


def _extract_comment_preview(comment_body: Any, max_len: int = 180) -> str:
    if comment_body is None:
        return ""
    if isinstance(comment_body, str):
        text = _safe_text(comment_body)
        return text[:max_len]
    if isinstance(comment_body, dict) and comment_body.get("type") == "doc":
        chunks: list[str] = []
        for node in comment_body.get("content") or []:
            for inline in node.get("content") or []:
                if inline.get("type") == "text":
                    chunks.append(inline.get("text", ""))
            if len(" ".join(chunks)) >= max_len:
                break
        return _safe_text(" ".join(chunks))[:max_len]
    return _safe_text(comment_body)[:max_len]


def _collect_candidate_issues(day: date) -> dict[str, dict[str, str]]:
    day_str = day.isoformat()
    jql = (
        "assignee = currentUser() "
        "AND issuetype != Epic "
        f'AND updated >= "{day_str} 00:00" '
        f'AND updated <= "{day_str} 23:59" '
        "ORDER BY updated ASC"
    )
    fields = ["summary", "updated", "created", "issuetype"]
    issues = _jira_search(jql=jql, fields=fields, max_results=2000)

    out: dict[str, dict[str, str]] = {}
    for issue in issues:
        key = issue.get("key") or ""
        if not key:
            continue
        itype = (((issue.get("fields") or {}).get("issuetype") or {}).get("name") or "").strip().lower()
        if itype == "epic":
            continue
        out[key] = {
            "summary": ((issue.get("fields") or {}).get("summary") or "").strip(),
            "created": ((issue.get("fields") or {}).get("created") or "").strip(),
            "updated": ((issue.get("fields") or {}).get("updated") or "").strip(),
        }
    return out


def _collect_new_tickets(day: date, issues_by_key: dict[str, dict[str, str]]) -> list[NewTicket]:
    out: list[NewTicket] = []
    for key, meta in issues_by_key.items():
        if not _is_on_day(meta.get("created"), day):
            continue
        dt = _parse_iso_dt(meta.get("created"))
        if not dt:
            continue
        out.append(NewTicket(when=dt, key=key, summary=meta.get("summary", "")))
    out.sort(key=lambda x: (x.when, x.key))
    return out


def _collect_in_progress_tickets(day: date) -> list[InProgressTicket]:
    day_start = day.isoformat()
    day_end = date.fromordinal(day.toordinal() + 1).isoformat()
    jql = (
        "assignee = currentUser() "
        "AND issuetype != Epic "
        "AND ( "
        f'status CHANGED TO "In Progress" DURING ("{day_start} 00:00", "{day_end} 00:00") '
        "OR "
        f'status CHANGED FROM "In Progress" DURING ("{day_start} 00:00", "{day_end} 00:00") '
        "OR "
        f'(status = "In Progress" AND NOT status CHANGED AFTER "{day_start} 00:00")'
        " ) "
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


def _collect_issue_events(
    day: date,
    issues_by_key: dict[str, dict[str, str]],
) -> tuple[list[StatusChange], list[CommentEvent], list[TicketChange]]:
    status_changes: list[StatusChange] = []
    comments: list[CommentEvent] = []
    ticket_changes: list[TicketChange] = []

    for key, meta in issues_by_key.items():
        summary = meta.get("summary", "")

        # Comments
        start_at = 0
        while True:
            data = _jira_get(
                f"/rest/api/3/issue/{key}/comment",
                params={"startAt": start_at, "maxResults": 100},
            )
            page = data.get("comments") or []
            for c in page:
                created = c.get("created")
                if not _is_on_day(created, day):
                    continue
                dt = _parse_iso_dt(created)
                if not dt:
                    continue
                author = ((c.get("author") or {}).get("displayName")) or ""
                preview = _extract_comment_preview(c.get("body"))
                comments.append(
                    CommentEvent(
                        when=dt,
                        key=key,
                        summary=summary,
                        author=author,
                        body_preview=preview,
                    )
                )

            total = int(data.get("total") or 0)
            start_at += len(page)
            if not page or start_at >= total:
                break

        # Changelog for status changes and ticket changes.
        start_at = 0
        while True:
            data = _jira_get(
                f"/rest/api/3/issue/{key}/changelog",
                params={"startAt": start_at, "maxResults": 100},
            )
            histories = data.get("values") or []
            for hist in histories:
                created = hist.get("created")
                if not _is_on_day(created, day):
                    continue
                dt = _parse_iso_dt(created)
                if not dt:
                    continue

                items = hist.get("items") or []
                changed_fields: list[str] = []
                for item in items:
                    field_name = _safe_text(item.get("field"))
                    if not field_name:
                        continue
                    if field_name.lower() == "status":
                        status_changes.append(
                            StatusChange(
                                when=dt,
                                key=key,
                                summary=summary,
                                from_status=_safe_text(item.get("fromString")) or "(leer)",
                                to_status=_safe_text(item.get("toString")) or "(leer)",
                            )
                        )
                    else:
                        changed_fields.append(field_name)

                # Remove duplicate field names while preserving order.
                if changed_fields:
                    dedup_fields = list(dict.fromkeys(changed_fields))
                    ticket_changes.append(
                        TicketChange(
                            when=dt,
                            key=key,
                            summary=summary,
                            fields=dedup_fields,
                        )
                    )

            total = int(data.get("total") or 0)
            start_at += len(histories)
            if not histories or start_at >= total:
                break

    status_changes.sort(key=lambda x: (x.when, x.key))
    comments.sort(key=lambda x: (x.when, x.key))
    ticket_changes.sort(key=lambda x: (x.when, x.key))
    return status_changes, comments, ticket_changes


def _journal_path_for_day(day: date, journal_dir: str) -> str:
    yy = day.strftime("%y")
    mm = day.strftime("%m")
    dd = day.strftime("%d")
    yyyy_mm = day.strftime("%Y-%m")
    return os.path.join(journal_dir, yyyy_mm, f"journal-{yy}-{mm}-{dd}.md")


def _extract_manual_content(existing_text: str) -> str:
    manual_header = "## Manueller Inhalt"
    generated_header = "## Generierter Inhalt (Jira)"

    start = existing_text.find(manual_header)
    if start < 0:
        return "<!-- Optional durch Nutzer gepflegt -->"
    start = start + len(manual_header)

    end = existing_text.find(generated_header, start)
    if end < 0:
        body = existing_text[start:].strip("\n")
    else:
        body = existing_text[start:end].strip("\n")
    return body if body.strip() else "<!-- Optional durch Nutzer gepflegt -->"


def _format_generated_section(
    in_progress_tickets: list[InProgressTicket],
    status_changes: list[StatusChange],
    comments: list[CommentEvent],
    ticket_changes: list[TicketChange],
    new_tickets: list[NewTicket],
) -> str:
    lines: list[str] = ["## Generierter Inhalt (Jira)", ""]

    lines.append("### In Bearbeitung")
    lines.append("")
    if not in_progress_tickets:
        lines.append("- Keine Einträge.")
    else:
        for it in in_progress_tickets:
            lines.append(f"- [{it.key}]({JIRA_BASE_URL}/browse/{it.key}) - {it.summary}")
    lines.append("")

    lines.append("### Statuswechsel")
    lines.append("")
    if not status_changes:
        lines.append("- Keine Einträge.")
    else:
        for ev in status_changes:
            lines.append(
                f"- {_hhmm(ev.when)} - [{ev.key}]({JIRA_BASE_URL}/browse/{ev.key}) - "
                f"{ev.summary} - {ev.from_status} -> {ev.to_status}"
            )
    lines.append("")

    lines.append("### Kommentare")
    lines.append("")
    if not comments:
        lines.append("- Keine Einträge.")
    else:
        for ev in comments:
            snippet = f' "{ev.body_preview}"' if ev.body_preview else ""
            lines.append(
                f"- {_hhmm(ev.when)} - [{ev.key}]({JIRA_BASE_URL}/browse/{ev.key}) - "
                f'{ev.summary} - {ev.author}:{snippet}'
            )
    lines.append("")

    lines.append("### Ticket-Änderungen")
    lines.append("")
    if not ticket_changes:
        lines.append("- Keine Einträge.")
    else:
        for ev in ticket_changes:
            fields = ", ".join(ev.fields)
            lines.append(
                f"- {_hhmm(ev.when)} - [{ev.key}]({JIRA_BASE_URL}/browse/{ev.key}) - "
                f"{ev.summary} - Geändert: {fields}"
            )
    lines.append("")

    lines.append("### Neu angelegte Tickets")
    lines.append("")
    if not new_tickets:
        lines.append("- Keine Einträge.")
    else:
        for ev in new_tickets:
            lines.append(
                f"- {_hhmm(ev.when)} - [{ev.key}]({JIRA_BASE_URL}/browse/{ev.key}) - {ev.summary}"
            )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_daily_journal(day: date, journal_dir: str) -> str:
    journal_path = _journal_path_for_day(day, journal_dir)
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)

    existing_text = ""
    if os.path.exists(journal_path):
        with open(journal_path, "r", encoding="utf-8") as f:
            existing_text = f.read()

    manual_content = _extract_manual_content(existing_text)
    issues_by_key = _collect_candidate_issues(day)
    in_progress_tickets = _collect_in_progress_tickets(day)
    new_tickets = _collect_new_tickets(day, issues_by_key)
    status_changes, comments, ticket_changes = _collect_issue_events(day, issues_by_key)

    header = f"# Journal {day.isoformat()}\n\n"
    manual_section = f"## Manueller Inhalt\n\n{manual_content.strip()}\n\n"
    generated_section = _format_generated_section(
        in_progress_tickets=in_progress_tickets,
        status_changes=status_changes,
        comments=comments,
        ticket_changes=ticket_changes,
        new_tickets=new_tickets,
    )
    content = header + manual_section + generated_section

    with open(journal_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"Journal aktualisiert: {journal_path}")
    print(
        "Events: "
        f"in_bearbeitung={len(in_progress_tickets)}, "
        f"statuswechsel={len(status_changes)}, "
        f"kommentare={len(comments)}, "
        f"ticket_aenderungen={len(ticket_changes)}, "
        f"neu={len(new_tickets)}"
    )
    return journal_path


def _write_journal_stub_filesystem(day: date, journal_dir: str) -> str:
    """Schreibt Stub-Datei. Rufer muss sicherstellen, dass der Pfad noch nicht existiert."""
    journal_path = _journal_path_for_day(day, journal_dir)
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    header = f"# Journal {day.isoformat()}\n\n"
    manual_section = "## Manueller Inhalt\n\n"
    generated_section = _format_generated_section(
        in_progress_tickets=[],
        status_changes=[],
        comments=[],
        ticket_changes=[],
        new_tickets=[],
    )
    content = header + manual_section + generated_section

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

    update_daily_journal(day=day, journal_dir=args.journal_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
