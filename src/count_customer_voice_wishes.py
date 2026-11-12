"""Zaehlt die neuen WISH-Items der Quelle "Customer Voice Uncensored" (Teams-Channel) pro Kalenderwoche.

Usage:
    py src/count_customer_voice_wishes.py
    py src/count_customer_voice_wishes.py --weeks 8

Regeln:
- Es zaehlen nur vollstaendige Kalenderwochen (Montag bis Sonntag). Die laufende Woche bleibt aussen vor.
- Gezaehlt werden alle WISH-Issues, deren Erstelldatum (created) in der Woche liegt, auch Duplicates.
- Die Quelle steht in Jira nicht als eigenes Feld, sondern im Beschreibungstext. Die Erkennung spiegelt
  source_from_body() aus pm-research-context/.claude/skills/wish-ingest/scripts/ingest_wishes.py:
  Eine Zeile "Source: <slug>" entscheidet (Slug beginnt mit "customer-voice" = Teams-Channel).
  Fehlt sie, zaehlt ein Teams-Nachrichtenlink mit der Gruppen-ID der Customer-Voice-Gruppe.

Liest Jira ausschliesslich ueber den Skill `jira` (jira_client), ~/.claude/skills/jira/src.
Credentials: ATLASSIAN_USER und ATLASSIAN_TOKEN.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

JIRA_SRC = Path.home() / ".claude" / "skills" / "jira" / "src"
PROJECT = "WISH"
SOURCE_LABEL = "Customer Voice Uncensored (Teams-Channel)"
MAX_RESULTS = 5000
DEFAULT_WEEKS = 4

# Dieselben Marker wie in wish-ingest (ingest_wishes.py), damit die Zaehlung dem Snapshot entspricht.
CUSTOMER_VOICE_GROUP_ID = "4a1913cf-829b-4e64-9628-57cbb21b89e5"
TEAMS_MESSAGE_MARK = "teams.microsoft.com/l/message"
TEAMS_GROUP_MARK = f"groupId={CUSTOMER_VOICE_GROUP_ID}"
SOURCE_LINE_RE = re.compile(
    r"^(?:>\s*)*(?:\*\*)?Source:\s*(?:\*\*)?\s*\[?([^\s·*\[\]]+)",
    re.MULTILINE,
)


def load_jira_client():
    """Import jira_client from the jira skill; a missing skill ends the run with a readable message."""
    if not JIRA_SRC.is_dir():
        sys.exit(f"Skill 'jira' nicht gefunden unter {JIRA_SRC}. Die Skills im Repo haengen voneinander ab.")
    if str(JIRA_SRC) not in sys.path:
        sys.path.append(str(JIRA_SRC))
    import jira_client  # noqa: PLC0415 - erst nach dem Pfad-Check

    return jira_client


def is_customer_voice(description_md: str) -> bool:
    """True, wenn der (in Markdown gerenderte) Beschreibungstext die Quelle Customer Voice Uncensored nennt."""
    body = description_md or ""
    match = SOURCE_LINE_RE.search(body)
    if match and match.group(1).strip():
        return match.group(1).strip().lower().startswith("customer-voice")
    return TEAMS_MESSAGE_MARK in body and TEAMS_GROUP_MARK in body


def complete_weeks(today: date, count: int) -> list[tuple[date, date]]:
    """Die letzten `count` vollstaendigen Mo-So-Wochen vor heute, aelteste zuerst."""
    this_monday = today - timedelta(days=today.weekday())
    weeks = []
    for back in range(count, 0, -1):
        start = this_monday - timedelta(weeks=back)
        weeks.append((start, start + timedelta(days=6)))
    return weeks


def fetch_wishes(jira_client, first_day: date, end_exclusive: date) -> list[dict[str, Any]]:
    jql = (
        f'project = {PROJECT} '
        f'AND created >= "{first_day:%Y-%m-%d}" AND created < "{end_exclusive:%Y-%m-%d}" '
        "ORDER BY created ASC"
    )
    issues = jira_client.search(jql, ["created", "description"], max_results=MAX_RESULTS)
    if len(issues) >= MAX_RESULTS:
        sys.exit(f"Abbruch: Die Suche hat das Limit von {MAX_RESULTS} Issues erreicht, die Zahlen waeren unvollstaendig.")
    return issues


def count_per_week(issues: list[dict[str, Any]], weeks: list[tuple[date, date]],
                   render: Callable[[Any], str]) -> dict[date, int]:
    counts = {start: 0 for start, _ in weeks}
    for issue in issues:
        fields = issue.get("fields") or {}
        try:
            created = date.fromisoformat((fields.get("created") or "")[:10])
        except ValueError:
            print(f"WARN {issue.get('key')}: kein lesbares Erstelldatum, uebersprungen", file=sys.stderr)
            continue
        for start, end in weeks:
            if start <= created <= end:
                if is_customer_voice(render(fields.get("description"))):
                    counts[start] += 1
                break
    return counts


def print_table(weeks: list[tuple[date, date]], counts: dict[date, int]) -> None:
    print(f"Quelle: {SOURCE_LABEL}, Projekt {PROJECT}, inklusive Duplicates")
    print()
    print(f"{'Kalenderwoche':<16}{'Zeitraum':<26}{'Neue Wishes':>12}")
    for start, end in weeks:
        iso = start.isocalendar()
        week = f"KW {iso.week:02d}/{iso.year}".ljust(16)
        period = f"{start:%d.%m.%Y} - {end:%d.%m.%Y}".ljust(26)
        print(f"{week}{period}{counts[start]:>12}")
    print(f"{'Summe':<42}{sum(counts.values()):>12}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weeks", type=int, default=DEFAULT_WEEKS,
                        help=f"Anzahl vollstaendiger Wochen rueckwaerts ab heute (Standard {DEFAULT_WEEKS})")
    args = parser.parse_args()
    if args.weeks < 1:
        parser.error("--weeks muss mindestens 1 sein")

    weeks = complete_weeks(date.today(), args.weeks)
    first_day, end_exclusive = weeks[0][0], weeks[-1][1] + timedelta(days=1)
    # Die laufende, unvollstaendige Woche bleibt durch die obere Grenze draussen.

    try:
        jira_client = load_jira_client()
        issues = fetch_wishes(jira_client, first_day, end_exclusive)
    except SystemExit:
        raise
    except Exception as exc:  # Credentials, Netz, HTTP: alles heisst hier "Jira nicht lesbar"
        print(f"ERROR Jira nicht lesbar: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    counts = count_per_week(issues, weeks, jira_client.render_adf_or_text)
    print_table(weeks, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
