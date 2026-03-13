"""Execute or list status transitions for a Jira issue.

Usage:
    py src/transition_jira_issue.py -i PROPS-123 --list
    py src/transition_jira_issue.py -i PROPS-123 --to "In Progress"
    py src/transition_jira_issue.py -i PROPS-123 --to "Next"
"""

import argparse
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _get_jira_auth, _jira_get, JIRA_BASE_URL


def get_transitions(issue_key: str) -> list[dict]:
    data = _jira_get(f"/rest/api/3/issue/{issue_key}/transitions")
    return data.get("transitions") or []


def transition_issue(issue_key: str, target_status: str) -> None:
    transitions = get_transitions(issue_key)
    match = next(
        (t for t in transitions if t.get("name", "").lower() == target_status.lower()),
        None,
    )
    if not match:
        available = [t.get("name") for t in transitions]
        print(f"Status '{target_status}' nicht verfuegbar.")
        print(f"Verfuegbare Transitionen: {available}")
        sys.exit(1)

    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    resp = requests.post(
        url, headers=headers, auth=(user, token),
        json={"transition": {"id": match["id"]}},
    )
    resp.raise_for_status()
    print(f"Issue {issue_key} -> Status '{match['name']}' gesetzt.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Transition a Jira issue to a new status")
    parser.add_argument("-i", "--issue-key", required=True, help="Issue key (e.g. PROPS-123)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List available transitions")
    group.add_argument("--to", metavar="STATUS", help="Target status name")
    args = parser.parse_args()

    if args.list:
        transitions = get_transitions(args.issue_key)
        print(f"Verfuegbare Transitionen fuer {args.issue_key}:")
        for t in transitions:
            print(f"  - {t.get('name')} (ID: {t.get('id')})")
    else:
        transition_issue(args.issue_key, args.to)


if __name__ == "__main__":
    main()
