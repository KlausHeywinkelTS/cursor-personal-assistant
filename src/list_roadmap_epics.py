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
from read_jira_issue import _jira_get, _jira_search, JIRA_BASE_URL  # noqa: E402

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


def fetch_status_info(
    key: str,
    bucket_statuses: list[str],
    since_date: str,
) -> tuple[str, str | None]:
    """Return (prev_status, status_at_since) for an Epic.

    prev_status:     status before the last transition INTO a bucket status after since_date.
    status_at_since: status the Epic had at the beginning of since_date (reconstructed from
                     changelog). None if the history is insufficient to determine it.
    """
    since_dt = datetime.fromisoformat(since_date).replace(tzinfo=timezone.utc)

    # Collect all status transitions from the full changelog
    transitions: list[tuple[datetime, str, str]] = []  # (created, from, to)
    start_at = 0
    page_size = 100
    while True:
        data = _jira_get(
            f"/rest/api/3/issue/{key}/changelog",
            params={"startAt": start_at, "maxResults": page_size},
        )
        values = data.get("values") or []
        for entry in values:
            created_str = entry.get("created", "")
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            for item in entry.get("items") or []:
                if item.get("field") == "status":
                    transitions.append((
                        created,
                        item.get("fromString") or "–",
                        item.get("toString") or "–",
                    ))
        total = data.get("total", 0)
        start_at += len(values)
        if start_at >= total or not values:
            break

    transitions.sort(key=lambda x: x[0])

    # status_at_since: last known status at or before since_dt
    status_at_since: str | None = None
    for created, _, to_str in transitions:
        if created <= since_dt:
            status_at_since = to_str
    if status_at_since is None and transitions:
        # All transitions happened after since_date → original status is fromString of the first
        status_at_since = transitions[0][1]

    # prev_status: fromString of the last transition INTO a bucket status after since_dt
    best_created: datetime | None = None
    prev_status = "–"
    for created, from_str, to_str in transitions:
        if created > since_dt and to_str in bucket_statuses:
            if best_created is None or created > best_created:
                best_created = created
                prev_status = from_str

    return prev_status, status_at_since


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
        current_status = ((f.get("status") or {}).get("name")) or ""
        # Only include if the epic still has a bucket status at report time
        if current_status not in bucket_statuses:
            continue
        prev_status, status_at_since = fetch_status_info(key, bucket_statuses, since_date)
        # Skip if no net change: current status equals status at start of query period
        if status_at_since is not None and current_status == status_at_since:
            print(f"  Skipping {key}: status unchanged ({current_status}) since {since_date}")
            continue
        epics.append({
            "key": key,
            "url": f"{JIRA_BASE_URL}/browse/{key}",
            "summary": f.get("summary") or "",
            "status": current_status,
            "prev_status": prev_status,
            "assignee": ((f.get("assignee") or {}).get("displayName")) or "–",
            "priority": ((f.get("priority") or {}).get("name")) or "–",
        })
    return epics


def _escape_pipe(text: str) -> str:
    return text.replace("|", r"\|")


EMAIL_BUCKET_LABELS: dict[str, str] = {
    "Now": "Now",
    "Next": "Next",
    "Later": "New in Backlog",
    "Blocked": "Newly Blocked",
    "After Release / Done": "Done / After Release",
}


def build_email_block(sections: list[tuple[str, list[dict]]]) -> str:
    """Build a narrative status-update block suitable for copy-pasting into an e-mail."""
    lines: list[str] = []
    lines.append("---")
    lines.append("")
    lines.append("## Status-Update (E-Mail)")
    lines.append("")

    # Special group: Unblocked (prev_status was Blocked, now in any other bucket)
    unblocked = [
        (bucket_label, epic)
        for bucket_label, epics in sections
        for epic in epics
        if epic["prev_status"] == "Blocked" and bucket_label != "Blocked"
    ]
    if unblocked:
        lines.append("**Unblocked:**")
        for bucket_label, epic in unblocked:
            display_label = "in progress" if bucket_label == "Now" else bucket_label
            lines.append(
                f'- "{epic["summary"]}" ({epic["key"]}) – unblocked, moved to {display_label}'
            )
        lines.append("")

    for bucket_label, epics in sections:
        # In "Newly Blocked", show all. In others, skip epics that came from Blocked (shown above).
        if bucket_label == "Blocked":
            relevant = epics
        else:
            relevant = [e for e in epics if e["prev_status"] != "Blocked"]
        if not relevant:
            continue

        email_label = EMAIL_BUCKET_LABELS.get(bucket_label, bucket_label)
        lines.append(f"**{email_label}:**")
        for epic in relevant:
            prev = epic["prev_status"]
            if prev in ("–", "New"):
                suffix = "newly created epic"
            elif prev == "Now":
                suffix = "was previously in progress"
            else:
                suffix = f"was previously in {prev}"
            lines.append(f'- "{epic["summary"]}" ({epic["key"]}) – {suffix}')
        lines.append("")

    return "\n".join(lines)


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

        lines.append("| Key | Summary | Vorheriger Status | Assignee | Priorität |")
        lines.append("|-----|---------|-------------------|----------|-----------|")
        for epic in epics:
            key_link = f"[{epic['key']}]({epic['url']})"
            summary = _escape_pipe(epic["summary"])
            prev_status = _escape_pipe(epic["prev_status"])
            assignee = _escape_pipe(epic["assignee"])
            priority = _escape_pipe(epic["priority"])
            lines.append(f"| {key_link} | {summary} | {prev_status} | {assignee} | {priority} |")
        lines.append("")

    lines.append(build_email_block(sections))

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
