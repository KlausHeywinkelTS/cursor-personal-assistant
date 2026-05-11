"""Bulk-Update des Reporter-Felds für Jira-Issues per JQL.

Dry-Run (Standard):
    py src/bulk_update_reporter.py --reporter-name "Adina Mereuta"

Ausführen:
    py src/bulk_update_reporter.py --reporter-name "Adina Mereuta" --execute

Eigene JQL:
    py src/bulk_update_reporter.py --jql "project = ZI AND ..." --reporter-name "..." --execute
"""

import argparse
import os
import sys

import requests

PLUGIN_SRC = (
    r"C:\Users\Kl6713\.cursor\plugins\cache\props-cursor-skills"
    r"\props-cursor-skills\80d7d7c856311608a487d9d0bb0a227393bb3f6c"
    r"\skills\jira\src"
)
sys.path.insert(0, PLUGIN_SRC)
from read_jira_issue import _get_jira_auth, JIRA_BASE_URL  # noqa: E402

DEFAULT_JQL = 'project = ZI AND issuetype = "Test" AND reporter = currentUser()'


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


def _put(path: str, payload: dict) -> None:
    user, token = _get_jira_auth()
    resp = requests.put(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        auth=(user, token),
        json=payload,
    )
    resp.raise_for_status()


def find_user_account_id(display_name: str) -> str:
    data = _get("/rest/api/3/user/search", {"query": display_name, "maxResults": 10})
    matches = [u for u in data if not u.get("accountType", "") == "app"]
    if not matches:
        print(f"Kein Benutzer gefunden für: {display_name}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"Mehrere Treffer für '{display_name}':")
        for u in matches:
            print(f"  {u['accountId']}  {u['displayName']}  ({u.get('emailAddress', '')})")
        print("Bitte --reporter-name präzisieren oder accountId direkt per --reporter-id übergeben.")
        sys.exit(1)
    return matches[0]["accountId"]


def search_issues(jql: str) -> list[dict]:
    page_size = 100
    issues: list[dict] = []
    next_page_token: str | None = None
    while True:
        payload: dict = {
            "jql": jql,
            "fields": ["key", "summary", "reporter", "status"],
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

    parser = argparse.ArgumentParser(description="Bulk-Update Reporter-Feld per JQL")
    parser.add_argument("--jql", default=DEFAULT_JQL, help="JQL-Suchstring")
    parser.add_argument("--reporter-name", required=True, help="Display-Name des neuen Reporters")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Änderungen tatsächlich durchführen (ohne Flag: Dry-Run)",
    )
    args = parser.parse_args()

    print(f"Suche Issues mit JQL: {args.jql}")
    issues = search_issues(args.jql)

    if not issues:
        print("Keine Issues gefunden. Nichts zu tun.")
        return

    print(f"\n{len(issues)} Issue(s) gefunden:\n")
    for iss in issues:
        fields = iss.get("fields", {})
        reporter = (fields.get("reporter") or {}).get("displayName", "unbekannt")
        status = (fields.get("status") or {}).get("name", "")
        print(f"  {iss['key']:12s}  [{status:20s}]  Reporter: {reporter}  –  {fields.get('summary', '')}")

    if not args.execute:
        print(
            f"\n[DRY-RUN] Kein Update durchgeführt."
            f"\nReporter würde auf '{args.reporter_name}' gesetzt werden."
            f"\nFüge --execute hinzu, um die Änderungen anzuwenden."
        )
        return

    print(f"\nErmittle accountId für '{args.reporter_name}' ...")
    account_id = find_user_account_id(args.reporter_name)
    print(f"  accountId: {account_id}")

    print(f"\nSetze Reporter auf '{args.reporter_name}' für {len(issues)} Issues ...\n")
    ok = 0
    errors = []
    for iss in issues:
        key = iss["key"]
        try:
            _put(f"/rest/api/3/issue/{key}", {"fields": {"reporter": {"accountId": account_id}}})
            print(f"  OK  {key}")
            ok += 1
        except requests.HTTPError as exc:
            msg = f"  FEHLER  {key}: {exc.response.status_code} {exc.response.text[:120]}"
            print(msg)
            errors.append(msg)

    print(f"\nFertig: {ok}/{len(issues)} erfolgreich aktualisiert.")
    if errors:
        print(f"{len(errors)} Fehler aufgetreten (siehe oben).")


if __name__ == "__main__":
    main()
