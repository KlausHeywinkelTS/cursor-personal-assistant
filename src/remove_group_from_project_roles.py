"""Remove a group from every Jira project role it is assigned to.

Discovers assignments with the same logic as list_projects_with_group_role.py
and deletes the group actor from each matching role. Dry-run is the default.

Usage:
    py src/remove_group_from_project_roles.py
    py src/remove_group_from_project_roles.py --group jira-users
    py src/remove_group_from_project_roles.py --projects APBTEST
    py src/remove_group_from_project_roles.py --execute
    py src/remove_group_from_project_roles.py --projects APBTEST --execute
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from list_projects_with_group_role import (
    DEFAULT_GROUP,
    DEFAULT_WORKERS,
    JIRA_BASE_URL,
    RETRY_ATTEMPTS,
    ProjectError,
    ResolvedGroup,
    _get_jira_auth,
    _project_error_message,
    actor_matches_group,
    fetch_all_projects,
    fetch_role_details_with_actors,
    jira_get,
    resolve_group,
)


@dataclass(frozen=True)
class RoleAssignment:
    project_key: str
    project_name: str
    role_id: str
    role_name: str


@dataclass(frozen=True)
class RemovalResult:
    assignment: RoleAssignment
    ok: bool
    error: str | None = None


def jira_delete(path: str, params: Any | None = None) -> None:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    last_error: Exception | None = None

    for attempt in range(RETRY_ATTEMPTS):
        response = requests.delete(
            url,
            headers={"Accept": "application/json"},
            auth=(user, token),
            params=params,
            timeout=30,
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_s = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(wait_s)
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            last_error = exc
            if response.status_code in {500, 502, 503, 504} and attempt < RETRY_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise
        return

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Jira request failed after retries: DELETE {path}")


def load_projects(project_keys: list[str] | None, *, include_archived: bool) -> list[dict[str, Any]]:
    if not project_keys:
        return fetch_all_projects(include_archived=include_archived)

    projects: list[dict[str, Any]] = []
    for key in project_keys:
        project = jira_get(f"/rest/api/3/project/{key}")
        if not isinstance(project, dict):
            raise RuntimeError(f"Unerwartete Antwort für Projekt {key}")
        project = dict(project)
        project["archived"] = bool(project.get("archived"))
        projects.append(project)
    return projects


def assignments_for_project(project: dict[str, Any], group: ResolvedGroup) -> list[RoleAssignment]:
    key = str(project.get("key") or "")
    name = str(project.get("name") or key)
    details = fetch_role_details_with_actors(key)
    found: list[RoleAssignment] = []
    for role in details:
        actors = role.get("actors") or []
        if not any(actor_matches_group(actor, group) for actor in actors):
            continue
        found.append(
            RoleAssignment(
                project_key=key,
                project_name=name,
                role_id=str(role.get("id") or ""),
                role_name=str(role.get("name") or role.get("id") or "Unbenannte Rolle"),
            )
        )
    return found


def find_assignments(
    projects: list[dict[str, Any]],
    group: ResolvedGroup,
    *,
    workers: int,
) -> tuple[list[RoleAssignment], list[ProjectError]]:
    assignments: list[RoleAssignment] = []
    errors: list[ProjectError] = []
    total = len(projects)
    done = 0

    print(f"Suche Gruppen-Zuweisungen in {total} Projekt(en) ...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(assignments_for_project, project, group): project for project in projects
        }
        for future in as_completed(futures):
            project = futures[future]
            key = str(project.get("key") or "?")
            try:
                assignments.extend(future.result())
            except Exception as exc:
                errors.append(ProjectError(key=key, error=_project_error_message(key, exc)))
            done += 1
            if done % 25 == 0 or done == total:
                print(f"  {done}/{total}", file=sys.stderr)

    assignments.sort(key=lambda item: (item.project_key, item.role_name.casefold()))
    errors.sort(key=lambda item: item.key)
    return assignments, errors


def delete_params(group: ResolvedGroup) -> dict[str, str]:
    if group.group_id:
        return {"groupId": group.group_id}
    return {"group": group.name}


def remove_assignment(assignment: RoleAssignment, group: ResolvedGroup) -> RemovalResult:
    try:
        jira_delete(
            f"/rest/api/3/project/{assignment.project_key}/role/{assignment.role_id}",
            params=delete_params(group),
        )
    except Exception as exc:
        return RemovalResult(
            assignment=assignment,
            ok=False,
            error=_project_error_message(assignment.project_key, exc),
        )
    return RemovalResult(assignment=assignment, ok=True)


def format_plan(
    group: ResolvedGroup,
    scanned: int,
    assignments: list[RoleAssignment],
    errors: list[ProjectError],
    *,
    execute: bool,
) -> str:
    project_count = len({item.project_key for item in assignments})
    mode = "AUSFÜHREN" if execute else "DRY-RUN"
    lines = [
        f"Gruppe: {group.name}"
        + (f" (groupId: {group.group_id})" if group.group_id else ""),
        f"Modus: {mode}",
        f"Gefundene Zuweisungen: {len(assignments)} in {project_count} Projekt(en), geprüft: {scanned}",
        "",
    ]

    if assignments:
        key_width = max(len("Key"), *(len(item.project_key) for item in assignments))
        name_width = max(len("Projekt"), *(len(item.project_name) for item in assignments))
        role_width = max(len("Rolle"), *(len(item.role_name) for item in assignments))
        header = (
            f"{'Key'.ljust(key_width)}  "
            f"{'Projekt'.ljust(name_width)}  "
            f"{'Rolle'.ljust(role_width)}  "
            "Role-ID"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for item in assignments:
            lines.append(
                f"{item.project_key.ljust(key_width)}  "
                f"{item.project_name.ljust(name_width)}  "
                f"{item.role_name.ljust(role_width)}  "
                f"{item.role_id}"
            )
    else:
        lines.append("Keine Zuweisungen gefunden. Nichts zu entfernen.")

    if errors:
        lines.extend(["", f"Fehler beim Lesen: {len(errors)}", ""])
        for error in errors:
            lines.append(f"  {error.key}: {error.error}")

    if assignments and not execute:
        lines.extend(
            [
                "",
                "Kein Write. Zum Entfernen denselben Aufruf mit --execute starten.",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def format_results(results: list[RemovalResult]) -> str:
    ok = sum(1 for item in results if item.ok)
    failed = [item for item in results if not item.ok]
    lines = [f"Entfernt: {ok}/{len(results)}", ""]
    for item in results:
        assignment = item.assignment
        if item.ok:
            lines.append(
                f"  OK     {assignment.project_key} / {assignment.role_name} ({assignment.role_id})"
            )
        else:
            lines.append(
                f"  FEHLER {assignment.project_key} / {assignment.role_name} ({assignment.role_id}): {item.error}"
            )
    if failed:
        lines.append("")
        lines.append(f"{len(failed)} Fehler, siehe oben.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove a group from every Jira project role it is assigned to. "
            "Dry-run unless --execute is set."
        )
    )
    parser.add_argument(
        "--group",
        default=DEFAULT_GROUP,
        help=f"Group name to remove (default: {DEFAULT_GROUP})",
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        help="Limit to these project keys. Default: all live projects.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also scan archived projects when --projects is not set.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel role lookups (default: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove the group. Without this flag the script only reports.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    group = resolve_group(args.group)
    print(f"Gruppe gefunden: {group.name}", file=sys.stderr)

    projects = load_projects(args.projects, include_archived=args.include_archived)
    print(f"{len(projects)} Projekt(e) geladen.", file=sys.stderr)

    assignments, errors = find_assignments(projects, group, workers=args.workers)
    print(format_plan(group, len(projects), assignments, errors, execute=args.execute), end="")

    results: list[RemovalResult] = []
    if args.execute and assignments:
        print("Entferne Gruppe aus den gefundenen Rollen ...", file=sys.stderr)
        for assignment in assignments:
            result = remove_assignment(assignment, group)
            results.append(result)
            status = "OK" if result.ok else "FEHLER"
            print(
                f"  {status} {assignment.project_key} / {assignment.role_name}",
                file=sys.stderr,
            )
        print(format_results(results), end="")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "group": asdict(group),
            "execute": bool(args.execute),
            "scanned": len(projects),
            "assignments": [asdict(item) for item in assignments],
            "read_errors": [asdict(item) for item in errors],
            "results": [
                {
                    **asdict(item.assignment),
                    "ok": item.ok,
                    "error": item.error,
                }
                for item in results
            ],
        }
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"JSON geschrieben: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
