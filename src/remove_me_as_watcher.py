"""Entfernt den aktuellen Nutzer als Watcher von allen Issues eines Jira-Projekts.

Dry-Run (Standard):
    py src/remove_me_as_watcher.py

Ausführen:
    py src/remove_me_as_watcher.py --execute

Anderes Projekt:
    py src/remove_me_as_watcher.py --project ABC --execute
"""

import argparse
import sys

import requests

from jira_skill import JIRA_BASE_URL
from jira_skill import get_jira_auth as _get_jira_auth

DEFAULT_PROJECT = "SI"


def _get(path: str, params: dict | None = None) -> dict | list:
    user, token = _get_jira_auth()
    resp = requests.get(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json"},
        auth=(user, token),
        params=params or {},
    )
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    user, token = _get_jira_auth()
    resp = requests.post(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        auth=(user, token),
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def _delete(path: str, params: dict) -> None:
    user, token = _get_jira_auth()
    resp = requests.delete(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json"},
        auth=(user, token),
        params=params,
    )
    resp.raise_for_status()


def get_my_account_id() -> str:
    return _get("/rest/api/3/myself")["accountId"]


def search_issues(jql: str) -> list[dict]:
    page_size = 100
    issues: list[dict] = []
    next_page_token: str | None = None
    while True:
        payload: dict = {
            "jql": jql,
            "fields": ["key", "summary", "status", "issuetype"],
            "maxResults": page_size,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        data = _post("/rest/api/3/search/jql", payload)
        batch = data.get("issues", [])
        issues.extend(batch)
        next_page_token = data.get("nextPageToken")
        if not batch or not next_page_token:
            break
    return issues


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Entfernt mich als Watcher aus allen Issues eines Projekts")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help=f"Projekt-Key (Standard: {DEFAULT_PROJECT})")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Änderungen tatsächlich durchführen (ohne Flag: Dry-Run)",
    )
    args = parser.parse_args()

    jql = f"project = {args.project} AND watcher = currentUser() ORDER BY key ASC"
    print(f"Suche Issues mit JQL: {jql}")
    issues = search_issues(jql)

    if not issues:
        print("Keine Issues gefunden, bei denen du Watcher bist. Nichts zu tun.")
        return

    print(f"\n{len(issues)} Issue(s) gefunden:\n")
    for iss in issues:
        fields = iss.get("fields", {})
        status = (fields.get("status") or {}).get("name", "")
        itype = (fields.get("issuetype") or {}).get("name", "")
        print(f"  {iss['key']:12s}  [{status:20s}]  {itype:10s}  {fields.get('summary', '')}")

    if not args.execute:
        print(
            "\n[DRY-RUN] Kein Update durchgeführt."
            "\nFüge --execute hinzu, um dich als Watcher zu entfernen."
        )
        return

    account_id = get_my_account_id()
    print(f"\nEntferne accountId {account_id} als Watcher von {len(issues)} Issues ...\n")
    ok = 0
    errors = []
    for iss in issues:
        key = iss["key"]
        try:
            _delete(f"/rest/api/3/issue/{key}/watchers", {"accountId": account_id})
            print(f"  OK  {key}")
            ok += 1
        except requests.HTTPError as exc:
            msg = f"  FEHLER  {key}: {exc.response.status_code} {exc.response.text[:120]}"
            print(msg)
            errors.append(msg)

    print(f"\nFertig: {ok}/{len(issues)} erfolgreich entfernt.")
    if errors:
        print(f"{len(errors)} Fehler aufgetreten (siehe oben).")


if __name__ == "__main__":
    main()
