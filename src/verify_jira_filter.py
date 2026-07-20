"""Execute a saved Jira filter once to confirm its JQL works.

Usage:
    py src/verify_jira_filter.py --filter-id 11845
"""

from __future__ import annotations

import argparse
import os
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
        raise RuntimeError(f"Jira API returned {response.status_code}: {response.text}")
    return response


def verify_filter(filter_id: str) -> None:
    filter_data = _request("GET", f"/rest/api/3/filter/{filter_id}").json()
    jql = str(filter_data.get("jql") or "").strip()
    if not jql:
        raise ValueError(f"Filter {filter_id} has no JQL.")

    result = _request(
        "POST",
        "/rest/api/3/search/jql",
        payload={"jql": jql, "maxResults": 1, "fields": ["key"]},
    ).json()
    issues = result.get("issues") or []
    print(
        f'Filter "{filter_data.get("name", filter_id)}" ({filter_id}) executed successfully '
        f"and returned {len(issues)} issue(s) in the sample."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute a Jira saved filter once.")
    parser.add_argument("--filter-id", required=True)
    verify_filter(parser.parse_args().filter_id)


if __name__ == "__main__":
    main()
