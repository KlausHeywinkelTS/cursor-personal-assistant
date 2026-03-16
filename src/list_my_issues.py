"""Lists Jira issues assigned to the current user or in project KH, grouped by status.

Usage:
    py src/list_my_issues.py --mode all
    py src/list_my_issues.py --mode remind-due
    py src/list_my_issues.py --mode active
    py src/list_my_issues.py --mode next
    py src/list_my_issues.py --mode waiting
    py src/list_my_issues.py --mode backlog
    py src/list_my_issues.py --mode to-be-refined
    py src/list_my_issues.py --mode all -o cache/my_issues.json

Modes:
    all            All open issues (not Done/Rejected)
    active         In Progress / Ongoing
    next           Next / To Do / ToDo / Ready to pull
    waiting        Waiting / Blocked / On Hold
    backlog        Backlog
    remind-due     Issues with Remind date <= today
    to-be-refined  Status "To be refined"
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _jira_search

JIRA_BASE_URL = "https://trustedshops.atlassian.net"
REMIND_DATE_FIELD = "customfield_10246"


def _jql_for_mode(mode: str) -> str:
    base = "(assignee = currentUser() OR project = KH) AND issuetype != Epic"
    if mode == "all":
        return f'{base} AND status NOT IN ("Done", "Rejected") ORDER BY updated DESC'
    if mode == "active":
        return f'{base} AND status IN ("In Progress", "Ongoing") ORDER BY updated DESC'
    if mode == "next":
        return f'{base} AND status IN ("Next", "To Do", "ToDo", "Ready to pull") ORDER BY updated DESC'
    if mode == "waiting":
        return f'{base} AND status IN ("Waiting", "Blocked", "On Hold") ORDER BY updated ASC'
    if mode == "backlog":
        return f'{base} AND status = "Backlog" ORDER BY created ASC'
    if mode == "remind-due":
        today = date.today().isoformat()
        return f'{base} AND cf[10246] <= "{today}" AND status NOT IN ("Done", "Rejected") ORDER BY cf[10246] ASC'
    if mode == "to-be-refined":
        return f'{base} AND status = "To be refined" ORDER BY created ASC'
    raise ValueError(f"Unknown mode: {mode}")


def _format_date(iso_str: str | None) -> str:
    if not iso_str:
        return ""
    try:
        return iso_str[:10]
    except Exception:
        return ""


def _days_since(iso_str: str | None) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        return f"{delta.days}d"
    except Exception:
        return ""


def _extract_comment_text(body: object) -> str:
    """Extract plain text preview from ADF or string comment body."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body[:300].replace("\n", " ")
    if isinstance(body, dict) and body.get("type") == "doc":
        texts: list[str] = []
        for node in body.get("content") or []:
            if node.get("type") in ("paragraph", "heading"):
                for inline in node.get("content") or []:
                    if inline.get("type") == "text":
                        texts.append(inline.get("text", ""))
            if len("".join(texts)) > 300:
                break
        return "".join(texts)[:300].replace("\n", " ")
    return str(body)[:300]


def fetch_issues(mode: str) -> list[dict]:
    jql = _jql_for_mode(mode)
    fields = [
        "summary", "status", "priority", "created", "updated",
        "statuscategorychangedate", REMIND_DATE_FIELD, "comment", "issuetype",
    ]
    raw = _jira_search(jql=jql, fields=fields)

    issues = []
    for r in raw:
        key = r.get("key", "")
        f = r.get("fields", {})
        status = ((f.get("status") or {}).get("name")) or ""
        priority = ((f.get("priority") or {}).get("name")) or ""
        remind_date = (f.get(REMIND_DATE_FIELD) or "")[:10]

        comment_data = f.get("comment") or {}
        comments = comment_data.get("comments") or []
        last_comment = None
        if comments:
            lc = comments[-1]
            last_comment = {
                "author": ((lc.get("author") or {}).get("displayName")) or "",
                "created": _format_date(lc.get("created")),
                "created_ago": _days_since(lc.get("created")),
                "body_preview": _extract_comment_text(lc.get("body")),
            }

        issues.append({
            "key": key,
            "url": f"{JIRA_BASE_URL}/browse/{key}",
            "summary": f.get("summary") or "",
            "status": status,
            "status_since_ago": _days_since(f.get("statuscategorychangedate")),
            "priority": priority,
            "created": _format_date(f.get("created")),
            "updated": _format_date(f.get("updated")),
            "updated_ago": _days_since(f.get("updated")),
            "remind_date": remind_date,
            "last_comment": last_comment,
        })
    return issues


def print_issues(issues: list[dict], mode: str) -> None:
    if not issues:
        print(f"Keine Issues gefunden (Modus: {mode})")
        return

    print(f"\n{'='*70}")
    print(f"Issues (Modus: {mode}) — {len(issues)} gefunden")
    print(f"{'='*70}\n")

    for iss in issues:
        remind = f"  | Remind: {iss['remind_date']}" if iss["remind_date"] else ""
        status_since = f" (seit {iss['status_since_ago']})" if iss["status_since_ago"] else ""
        updated = f"  | Update: vor {iss['updated_ago']}" if iss["updated_ago"] else ""
        print(f"[{iss['key']}] {iss['summary']}")
        print(f"  Status: {iss['status']}{status_since}{updated}{remind}")
        if iss["last_comment"]:
            lc = iss["last_comment"]
            comment_ago = f" (vor {lc['created_ago']})" if lc.get("created_ago") else ""
            preview = lc["body_preview"][:150]
            print(f"  Letzter Kommentar{comment_ago} ({lc['created']}, {lc['author']}): {preview}")
        print()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="List Jira issues for current user")
    parser.add_argument(
        "--mode",
        choices=["all", "active", "next", "waiting", "backlog", "remind-due", "to-be-refined"],
        default="all",
        help="Filter mode (default: all open issues)",
    )
    parser.add_argument("-o", "--output", help="Save results as JSON to this file path")
    args = parser.parse_args()

    issues = fetch_issues(args.mode)
    print_issues(issues, args.mode)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(
                {"mode": args.mode, "count": len(issues), "issues": issues},
                fh, ensure_ascii=False, indent=2,
            )
        print(f"Gespeichert: {len(issues)} Issues -> {args.output}")


if __name__ == "__main__":
    main()
