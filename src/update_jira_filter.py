"""Validate and update the JQL of a Jira saved filter.

Usage:
    py src/update_jira_filter.py --filter-id 11845 --jql-file cache/filter-11845.jql
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import requests


JIRA_BASE_URL = "https://trustedshops.atlassian.net"


def _auth() -> tuple[str, str]:
    user = os.getenv("ATLASSIAN_USER")
    token = os.getenv("ATLASSIAN_TOKEN")
    if not user or not token:
        raise RuntimeError("Missing ATLASSIAN_USER or ATLASSIAN_TOKEN.")
    return user, token


def _request(method: str, path: str, *, payload: dict[str, Any] | None = None) -> requests.Response:
    response = requests.request(
        method,
        f"{JIRA_BASE_URL}{path}",
        auth=_auth(),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Jira API returned {response.status_code}: {response.text}"
        )
    response.raise_for_status()
    return response


def validate_jql(jql: str) -> None:
    response = _request(
        "POST",
        "/rest/api/3/jql/parse?validation=strict",
        payload={"queries": [jql]},
    )
    result = response.json()
    query_result = (result.get("queries") or [{}])[0]
    errors = query_result.get("errors") or query_result.get("errorMessages") or []
    if errors:
        raise ValueError(f"JQL is invalid: {'; '.join(str(error) for error in errors)}")


def update_filter(filter_id: str, jql: str) -> dict[str, Any]:
    current = _request("GET", f"/rest/api/3/filter/{filter_id}").json()
    payload = {"name": current["name"], "jql": jql}
    if current.get("description") is not None:
        payload["description"] = current["description"]

    response = _request("PUT", f"/rest/api/3/filter/{filter_id}", payload=payload)
    if not response.content:
        return {"id": filter_id}
    return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and update a Jira filter's JQL.")
    parser.add_argument("--filter-id", required=True)
    parser.add_argument("--jql-file", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jql = args.jql_file.read_text(encoding="utf-8").strip()
    if not jql:
        raise ValueError("JQL file is empty.")

    validate_jql(jql)
    print("JQL syntax is valid.")
    updated = update_filter(args.filter_id, jql)
    print(f"Updated filter {updated.get('name', args.filter_id)} ({args.filter_id}).")


if __name__ == "__main__":
    main()
