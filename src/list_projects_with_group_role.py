"""List Jira projects where a group is assigned to at least one project role.

By default the group is "jira-users". Credentials come from ATLASSIAN_USER and
ATLASSIAN_TOKEN via the shared Jira skill helper.

Usage:
    py src/list_projects_with_group_role.py
    py src/list_projects_with_group_role.py --group jira-users
    py src/list_projects_with_group_role.py --include-archived -o cache/jira-users-projects.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests


DEFAULT_GROUP = "jira-users"
PROJECT_PAGE_SIZE = 100
DEFAULT_WORKERS = 8
RETRY_ATTEMPTS = 5


def _candidate_jira_helper_dirs() -> list[Path]:
    """Return likely locations for the shared Jira skill helper script."""
    candidates: list[Path] = []
    script_dir = Path(__file__).resolve().parent
    candidates.append(script_dir)

    for env_name in ("CURSOR_JIRA_SKILL_SRC", "JIRA_SKILL_SRC"):
        configured = os.getenv(env_name)
        if configured:
            candidates.append(Path(configured).expanduser())

    home = Path.home()
    candidates.extend(
        [
            home / ".cursor" / "skills" / "jira" / "src",
            home / "Dev" / "props-cursor-plugins" / "skills" / "jira" / "src",
        ]
    )

    plugin_cache = home / ".cursor" / "plugins" / "cache"
    if plugin_cache.exists():
        candidates.extend(plugin_cache.glob("**/skills/jira/src"))

    return candidates


def _find_jira_helper_file() -> Path:
    for candidate in _candidate_jira_helper_dirs():
        helper_file = candidate / "read_jira_issue.py"
        if helper_file.is_file():
            return helper_file

    searched = "\n".join(f"- {path}" for path in _candidate_jira_helper_dirs())
    raise ModuleNotFoundError(
        "Could not find read_jira_issue.py. Install the jira user skill or set "
        f"CURSOR_JIRA_SKILL_SRC to its src directory.\nSearched:\n{searched}"
    )


def _load_jira_helpers() -> tuple[Any, str]:
    helper_file = _find_jira_helper_file()
    spec = importlib.util.spec_from_file_location("cursor_jira_read_issue", helper_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Jira helper module from {helper_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, "_get_jira_auth"), getattr(module, "JIRA_BASE_URL")


_get_jira_auth, JIRA_BASE_URL = _load_jira_helpers()


@dataclass(frozen=True)
class ResolvedGroup:
    name: str
    group_id: str | None


@dataclass(frozen=True)
class ProjectMatch:
    key: str
    name: str
    project_id: str
    style: str
    simplified: bool
    archived: bool
    roles: tuple[str, ...]


@dataclass(frozen=True)
class ProjectError:
    key: str
    error: str


def jira_get(path: str, params: Any | None = None) -> Any:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    last_error: Exception | None = None

    for attempt in range(RETRY_ATTEMPTS):
        response = requests.get(
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
        return response.json()

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Jira request failed after retries: GET {path}")


def resolve_group(group_name: str) -> ResolvedGroup:
    data = jira_get(
        "/rest/api/3/groups/picker",
        params={"query": group_name, "maxResults": 50},
    )
    groups = data.get("groups") or []
    exact = [
        group
        for group in groups
        if str(group.get("name") or "").casefold() == group_name.casefold()
    ]
    if not exact:
        names = ", ".join(str(group.get("name") or "?") for group in groups[:10]) or "keine"
        raise RuntimeError(
            f"Gruppe '{group_name}' nicht gefunden. Nächste Treffer: {names}"
        )

    chosen = exact[0]
    group_id = chosen.get("groupId")
    return ResolvedGroup(name=str(chosen.get("name") or group_name), group_id=group_id)


def actor_matches_group(actor: dict[str, Any], group: ResolvedGroup) -> bool:
    actor_type = str(actor.get("type") or "")
    actor_group = actor.get("actorGroup") or {}
    if actor_type and actor_type != "atlassian-group-role-actor" and not actor_group:
        return False

    group_id = actor_group.get("groupId")
    if group.group_id and group_id and str(group_id) == group.group_id:
        return True

    target = group.name.casefold()
    names = [
        actor.get("name"),
        actor.get("displayName"),
        actor_group.get("name"),
        actor_group.get("displayName"),
    ]
    return any(str(name).casefold() == target for name in names if name)


def matching_role_names(role_details: list[dict[str, Any]], group: ResolvedGroup) -> tuple[str, ...]:
    matched: list[str] = []
    for role in role_details:
        actors = role.get("actors") or []
        if any(actor_matches_group(actor, group) for actor in actors):
            role_name = str(role.get("name") or role.get("id") or "Unbenannte Rolle")
            matched.append(role_name)
    return tuple(dict.fromkeys(matched))


def _fetch_projects_by_status(status: str) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    start_at = 0

    while True:
        data = jira_get(
            "/rest/api/3/project/search",
            params=[
                ("startAt", start_at),
                ("maxResults", PROJECT_PAGE_SIZE),
                ("status", status),
            ],
        )
        values = data.get("values") or []
        for project in values:
            project = dict(project)
            project["archived"] = status == "archived"
            projects.append(project)

        if data.get("isLast", True) or not values:
            break
        start_at += len(values)

    return projects


def fetch_all_projects(*, include_archived: bool) -> list[dict[str, Any]]:
    projects = _fetch_projects_by_status("live")
    if include_archived:
        projects.extend(_fetch_projects_by_status("archived"))
    return projects


SKIP_ROLE_NAMES = frozenset({"atlassian-addons-project-access"})


def fetch_role_details_with_actors(project_key: str) -> list[dict[str, Any]]:
    """Load each project role including actors.

    `/roledetails` only returns role metadata in this Jira Cloud tenant, without
    `actors`. Assignments are on `/project/{key}/role/{id}`.
    """
    roles_map = jira_get(f"/rest/api/3/project/{project_key}/role")
    if not isinstance(roles_map, dict):
        raise RuntimeError(f"Unerwartete Antwort für Rollenliste von {project_key}")

    details: list[dict[str, Any]] = []
    for role_name, url in roles_map.items():
        if role_name in SKIP_ROLE_NAMES:
            continue
        role_id = str(url).rstrip("/").split("/")[-1]
        detail = jira_get(f"/rest/api/3/project/{project_key}/role/{role_id}")
        if not isinstance(detail, dict):
            raise RuntimeError(f"Unerwartete Antwort für Rolle {role_name} in {project_key}")
        details.append(detail)
    return details


def fetch_matching_roles(project_key: str, group: ResolvedGroup) -> tuple[str, ...]:
    details = fetch_role_details_with_actors(project_key)
    return matching_role_names(details, group)


def _project_error_message(project_key: str, exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        body = (exc.response.text or "").strip().replace("\n", " ")
        if len(body) > 200:
            body = body[:197] + "..."
        return f"HTTP {status}" + (f": {body}" if body else "")
    return str(exc) or f"Unbekannter Fehler bei {project_key}"


def scan_projects(
    projects: list[dict[str, Any]],
    group: ResolvedGroup,
    *,
    workers: int,
) -> tuple[list[ProjectMatch], list[ProjectError]]:
    matches: list[ProjectMatch] = []
    errors: list[ProjectError] = []
    total = len(projects)
    done = 0

    def inspect(project: dict[str, Any]) -> tuple[ProjectMatch | None, ProjectError | None]:
        key = str(project.get("key") or "")
        try:
            roles = fetch_matching_roles(key, group)
        except Exception as exc:
            return None, ProjectError(key=key or "?", error=_project_error_message(key, exc))
        if not roles:
            return None, None
        return (
            ProjectMatch(
                key=key,
                name=str(project.get("name") or key),
                project_id=str(project.get("id") or ""),
                style=str(project.get("style") or ("simplified" if project.get("simplified") else "classic")),
                simplified=bool(project.get("simplified")),
                archived=bool(project.get("archived")),
                roles=roles,
            ),
            None,
        )

    print(f"Prüfe Rollen in {total} Projekt(en) ...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(inspect, project) for project in projects]
        for future in as_completed(futures):
            match, error = future.result()
            if match is not None:
                matches.append(match)
            if error is not None:
                errors.append(error)
            done += 1
            if done % 25 == 0 or done == total:
                print(f"  {done}/{total}", file=sys.stderr)

    matches.sort(key=lambda item: item.key)
    errors.sort(key=lambda item: item.key)
    return matches, errors


def format_report(
    group: ResolvedGroup,
    scanned: int,
    matches: list[ProjectMatch],
    errors: list[ProjectError],
) -> str:
    lines: list[str] = [
        f"Gruppe: {group.name}"
        + (f" (groupId: {group.group_id})" if group.group_id else ""),
        f"Projekte mit Zuweisung in mindestens einer Rolle: {len(matches)} / {scanned}",
        "",
    ]

    if matches:
        display_names = [
            f"{item.name} [archiviert]" if item.archived else item.name for item in matches
        ]
        key_width = max(len("Key"), *(len(item.key) for item in matches))
        name_width = max(len("Name"), *(len(name) for name in display_names))
        style_width = max(len("Typ"), *(len(item.style) for item in matches))
        header = (
            f"{'Key'.ljust(key_width)}  "
            f"{'Name'.ljust(name_width)}  "
            f"{'Typ'.ljust(style_width)}  "
            "Rollen"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for item, display_name in zip(matches, display_names):
            lines.append(
                f"{item.key.ljust(key_width)}  "
                f"{display_name.ljust(name_width)}  "
                f"{item.style.ljust(style_width)}  "
                f"{', '.join(item.roles)}"
            )
    else:
        lines.append("Keine Projekte gefunden, in denen die Gruppe einer Rolle zugewiesen ist.")

    if errors:
        lines.extend(["", f"Fehler / fehlende Rechte: {len(errors)}", ""])
        for error in errors:
            lines.append(f"  {error.key}: {error.error}")

    lines.append("")
    return "\n".join(lines)


def matches_to_json(
    group: ResolvedGroup,
    scanned: int,
    matches: list[ProjectMatch],
    errors: list[ProjectError],
) -> dict[str, Any]:
    return {
        "group": asdict(group),
        "scanned": scanned,
        "matches": [
            {
                **{key: value for key, value in asdict(item).items() if key != "roles"},
                "roles": list(item.roles),
            }
            for item in matches
        ],
        "errors": [asdict(error) for error in errors],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List all Jira projects where the given group is assigned to at least one project role."
        )
    )
    parser.add_argument(
        "--group",
        default=DEFAULT_GROUP,
        help=f"Group name to look for (default: {DEFAULT_GROUP})",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also scan archived projects (default: live projects only).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel role lookups (default: {DEFAULT_WORKERS}).",
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

    projects = fetch_all_projects(include_archived=args.include_archived)
    print(f"{len(projects)} Projekt(e) geladen.", file=sys.stderr)

    matches, errors = scan_projects(projects, group, workers=args.workers)
    report = format_report(group, len(projects), matches, errors)
    print(report, end="")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = matches_to_json(group, len(projects), matches, errors)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"JSON geschrieben: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
