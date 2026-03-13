"""Fetches Jira issues by JQL filter and caches them as a JSON file.

Reuses the Jira infrastructure from read_jira_issue.py.

Usage:
    py src/search_jira_issues.py --jql "project = WISH AND status NOT IN ('Done','Duplicate','Rejected','Closed')" -o cache/WISH_feedback.json
    py src/search_jira_issues.py --jql "project = WISH" -o cache/WISH_all.json --max-description-length 500
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _jira_search, _render_adf_or_text

JIRA_BASE_URL = "https://trustedshops.atlassian.net"


def fetch_and_cache(
    jql: str,
    output_path: str,
    max_description_length: int = 0,
) -> dict:
    fields = ["summary", "description", "status", "issuetype"]

    print(f"Fetching issues with JQL: {jql}")
    raw_issues = _jira_search(jql=jql, fields=fields)
    print(f"Found {len(raw_issues)} issues")

    issues = []
    for raw in raw_issues:
        key = raw.get("key", "")
        f = raw.get("fields", {})
        summary = f.get("summary", "")
        description_md = _render_adf_or_text(f.get("description"))
        if max_description_length > 0 and len(description_md) > max_description_length:
            description_md = description_md[:max_description_length] + " [...]"
        status = ((f.get("status") or {}).get("name")) or ""
        issuetype = ((f.get("issuetype") or {}).get("name")) or ""

        issues.append({
            "key": key,
            "url": f"{JIRA_BASE_URL}/browse/{key}",
            "summary": summary,
            "description": description_md,
            "status": status,
            "issuetype": issuetype,
        })

    result = {
        "jql": jql,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(issues),
        "issues": issues,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print(f"Cached {len(issues)} issues to {output_path}")
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Fetch Jira issues by JQL and cache as JSON")
    parser.add_argument("--jql", required=True, help="JQL filter string")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    parser.add_argument(
        "--max-description-length",
        type=int,
        default=0,
        help="Truncate descriptions to N characters (0 = no limit)",
    )
    args = parser.parse_args()
    fetch_and_cache(args.jql, args.output, args.max_description_length)


if __name__ == "__main__":
    main()
