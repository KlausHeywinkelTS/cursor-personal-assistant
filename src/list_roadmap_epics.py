"""List Jira Epics by roadmap status changes since a given date.

Fetches Epics from projects CC, RM, INV, QUE, LRST that are marked
"relevant for roadmap" and groups them by status changes since the given date.

Usage:
    py src/list_roadmap_epics.py --since 2026-04-01
    py src/list_roadmap_epics.py --since 2026-04-01 --output tmp/custom.md
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_SRC = (
    r"C:\Users\Kl6713\.cursor\plugins\cache\props-cursor-skills"
    r"\props-cursor-skills\80d7d7c856311608a487d9d0bb0a227393bb3f6c"
    r"\skills\jira\src"
)
sys.path.insert(0, PLUGIN_SRC)
from read_jira_issue import _jira_search, JIRA_BASE_URL  # noqa: E402

PROJECTS = ["CC", "RM", "INV", "QUE", "LRST"]

# "Relevant for P&E Roadmap" custom field (customfield_10112)
ROADMAP_FIELD_JQL = 'cf[10112] = "Yes"'

BUCKETS: list[tuple[str, list[str]]] = [
    ("Now", ["Now"]),
    ("Next", ["Next"]),
    ("Later", ["Later"]),
    ("Blocked", ["Blocked"]),
    ("After Release / Done", ["After Release", "Done"]),
]


def fetch_epics_for_bucket(
    bucket_statuses: list[str],
    since_date: str,
) -> list[dict]:
    """Fetch Epics that had their status changed to any of bucket_statuses after since_date."""
    projects_jql = ", ".join(PROJECTS)
    status_changes = " OR ".join(
        f'status changed to "{s}" after "{since_date}"' for s in bucket_statuses
    )
    status_clause = f"({status_changes})"

    jql_parts = [
        "issuetype = Epic",
        f"project in ({projects_jql})",
        status_clause,
        ROADMAP_FIELD_JQL,
    ]

    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

    print(f"  JQL: {jql}")
    raw_issues = _jira_search(
        jql=jql,
        fields=["summary", "status", "assignee", "priority"],
        max_results=500,
    )

    epics: list[dict] = []
    for raw in raw_issues:
        key = raw.get("key", "")
        f = raw.get("fields", {})
        epics.append({
            "key": key,
            "url": f"{JIRA_BASE_URL}/browse/{key}",
            "summary": f.get("summary") or "",
            "status": ((f.get("status") or {}).get("name")) or "",
            "assignee": ((f.get("assignee") or {}).get("displayName")) or "–",
            "priority": ((f.get("priority") or {}).get("name")) or "–",
        })
    return epics


def _escape_pipe(text: str) -> str:
    return text.replace("|", r"\|")


def build_markdown(since_date: str, sections: list[tuple[str, list[dict]]]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# Roadmap Epics – Statusänderungen seit {since_date}")
    lines.append("")
    lines.append(f"_Generiert: {generated_at}_")
    lines.append("")

    for bucket_label, epics in sections:
        count = len(epics)
        lines.append(f"## {bucket_label} ({count} Epic{'s' if count != 1 else ''})")
        lines.append("")

        if not epics:
            lines.append("_Keine Epics in diesem Zeitraum._")
            lines.append("")
            continue

        lines.append("| Key | Summary | Aktueller Status | Assignee | Priorität |")
        lines.append("|-----|---------|-----------------|----------|-----------|")
        for epic in epics:
            key_link = f"[{epic['key']}]({epic['url']})"
            summary = _escape_pipe(epic["summary"])
            status = _escape_pipe(epic["status"])
            assignee = _escape_pipe(epic["assignee"])
            priority = _escape_pipe(epic["priority"])
            lines.append(f"| {key_link} | {summary} | {status} | {assignee} | {priority} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="List Jira roadmap Epics grouped by status changes since a given date"
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Start date in YYYY-MM-DD format (status changes after this date are included)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output markdown file path (default: tmp/roadmap-epics-SINCE_DATE.md)",
    )
    args = parser.parse_args()

    since_date = args.since
    output_path = args.output or f"tmp/roadmap-epics-{since_date}.md"

    sections: list[tuple[str, list[dict]]] = []
    for bucket_label, bucket_statuses in BUCKETS:
        print(f"\nFetching bucket '{bucket_label}' ...")
        epics = fetch_epics_for_bucket(bucket_statuses, since_date)
        print(f"  → {len(epics)} Epic(s) found")
        sections.append((bucket_label, epics))

    md = build_markdown(since_date, sections)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(md, encoding="utf-8", newline="\n")

    print(f"\nMarkdown written to: {output_file}")


if __name__ == "__main__":
    main()
