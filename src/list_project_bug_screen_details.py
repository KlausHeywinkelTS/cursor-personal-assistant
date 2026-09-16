"""Resolve Bug screens for selected Jira spaces via Issue Type Screen Scheme chain.

Chain per project:
  Project -> Issue Type Screen Scheme -> Bug Screen Scheme -> Screen(s)

Writes one line per project to a text file and reports missing mappings,
screen schemes, or screens.

Usage:
    py src/list_project_bug_screen_details.py
    py src/list_project_bug_screen_details.py --output tmp/jira-bug-screen-list.txt
    py src/list_project_bug_screen_details.py --projects REVIN INV
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_PROJECTS = [
    "REVIN",
    "INV",
    "QUE",
    "CC",
    "RM",
    "LSRT",
    "TPSCON",
    "PL",
    "TW",
    "SW",
    "TR",
    "TRSTDEXP",
    "SEO",
    "GUARANTEE",
    "CA",
    "TCM",
    "MYTSDOWN",
]
DEFAULT_OUTPUT = "tmp/jira-bug-screen-list.txt"
BUG_ALIASES = {"bug", "fehler"}
SCREEN_OPS = ("default", "create", "edit", "view")


def _candidate_jira_helper_dirs() -> list[Path]:
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


def _load_jira_helpers() -> tuple[Any, Any]:
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
class ProjectInfo:
    key: str
    project_id: str
    name: str


@dataclass(frozen=True)
class ScreenInfo:
    screen_id: str
    name: str


@dataclass(frozen=True)
class ScreenSchemeInfo:
    scheme_id: str
    name: str
    screens: dict[str, str]


@dataclass(frozen=True)
class ResolvedScreen:
    operation: str
    screen_id: str
    screen_name: str


@dataclass
class ProjectBugScreenDetails:
    project_key: str
    project_name: str
    issue_type_screen_scheme_id: str = ""
    issue_type_screen_scheme_name: str = ""
    bug_issue_type_id: str = ""
    bug_screen_scheme_id: str = ""
    bug_screen_scheme_name: str = ""
    screens: list[ResolvedScreen] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.warnings and bool(self.screens)


def jira_get(path: str, params: Any | None = None) -> Any:
    user, token = _get_jira_auth()
    response = requests.get(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json"},
        auth=(user, token),
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _http_error_message(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else "?"
    detail = ""
    if exc.response is not None:
        detail = (exc.response.text or "").strip().replace("\n", " ")
        if len(detail) > 200:
            detail = detail[:197] + "..."
    if status == 403:
        return (
            "HTTP 403: Administer Jira permission required"
            + (f" ({detail})" if detail else "")
        )
    return f"HTTP {status}" + (f": {detail}" if detail else "")


def fetch_paginated(path: str, extra_params: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    start_at = 0
    max_results = 50

    while True:
        params = list(extra_params)
        params.extend([("startAt", start_at), ("maxResults", max_results)])
        data = jira_get(path, params=params)
        page = data.get("values") or []
        values.extend(page)

        if data.get("isLast", True) or not page:
            break
        start_at += len(page)
        if start_at >= data.get("total", start_at):
            break

    return values


def fetch_project(project_key: str) -> ProjectInfo:
    data = jira_get(f"/rest/api/3/project/{project_key}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected project response for {project_key}")
    return ProjectInfo(
        key=str(data.get("key") or project_key),
        project_id=str(data.get("id") or ""),
        name=str(data.get("name") or project_key),
    )


def fetch_bug_issue_type_id(project_id: str) -> str | None:
    data = jira_get("/rest/api/3/issuetype/project", params={"projectId": project_id})
    items: list[dict[str, Any]]
    if isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        items = [item for item in (data.get("values") or []) if isinstance(item, dict)]
    else:
        items = []

    for item in items:
        name = str(item.get("name") or "").casefold()
        if name in BUG_ALIASES:
            issue_type_id = item.get("id")
            if issue_type_id is not None:
                return str(issue_type_id)
    return None


def fetch_project_issue_type_screen_scheme(project_id: str) -> tuple[str, str] | None:
    rows = fetch_paginated(
        "/rest/api/3/issuetypescreenscheme/project",
        [("projectId", project_id)],
    )
    if not rows:
        return None
    row = rows[0]
    itss = row.get("issueTypeScreenScheme") or {}
    scheme_id = itss.get("issueTypeScreenSchemeId") or itss.get("id")
    scheme_name = str(itss.get("name") or "")
    if scheme_id is None:
        return None
    return str(scheme_id), scheme_name


def fetch_itss_mappings(issue_type_screen_scheme_id: str) -> list[dict[str, Any]]:
    return fetch_paginated(
        "/rest/api/3/issuetypescreenscheme/mapping",
        [("issueTypeScreenSchemeId", issue_type_screen_scheme_id)],
    )


def fetch_screen_schemes(scheme_ids: set[str]) -> dict[str, ScreenSchemeInfo]:
    if not scheme_ids:
        return {}

    schemes: dict[str, ScreenSchemeInfo] = {}
    extra = [("id", scheme_id) for scheme_id in sorted(scheme_ids)]
    for item in fetch_paginated("/rest/api/3/screenscheme", extra):
        scheme_id = item.get("id")
        if scheme_id is None:
            continue
        raw_screens = item.get("screens") or {}
        screens = {
            op: str(screen_id)
            for op in SCREEN_OPS
            if (screen_id := raw_screens.get(op)) is not None
        }
        schemes[str(scheme_id)] = ScreenSchemeInfo(
            scheme_id=str(scheme_id),
            name=str(item.get("name") or f"Screen scheme {scheme_id}"),
            screens=screens,
        )
    return schemes


def fetch_screens(screen_ids: set[str]) -> dict[str, ScreenInfo]:
    if not screen_ids:
        return {}

    screens: dict[str, ScreenInfo] = {}
    extra = [("id", screen_id) for screen_id in sorted(screen_ids)]
    for item in fetch_paginated("/rest/api/3/screens", extra):
        screen_id = item.get("id")
        if screen_id is None:
            continue
        screens[str(screen_id)] = ScreenInfo(
            screen_id=str(screen_id),
            name=str(item.get("name") or f"Screen {screen_id}"),
        )
    return screens


def resolve_project(
    project: ProjectInfo,
    screen_schemes: dict[str, ScreenSchemeInfo],
    screens: dict[str, ScreenInfo],
) -> ProjectBugScreenDetails:
    details = ProjectBugScreenDetails(
        project_key=project.key,
        project_name=project.name,
    )

    itss = fetch_project_issue_type_screen_scheme(project.project_id)
    if itss is None:
        details.error = "Kein Issue Type Screen Scheme zugeordnet"
        return details

    details.issue_type_screen_scheme_id, details.issue_type_screen_scheme_name = itss

    bug_type_id = fetch_bug_issue_type_id(project.project_id)
    if bug_type_id is None:
        details.error = "Issue Type Bug nicht im Projekt vorhanden"
        return details
    details.bug_issue_type_id = bug_type_id

    mappings = fetch_itss_mappings(details.issue_type_screen_scheme_id)
    bug_scheme_id: str | None = None
    for mapping in mappings:
        issue_type_id = str(mapping.get("issueTypeId") or "")
        screen_scheme_id = mapping.get("screenSchemeId")
        if issue_type_id == bug_type_id and screen_scheme_id is not None:
            bug_scheme_id = str(screen_scheme_id)
            break

    if bug_scheme_id is None:
        details.warnings.append(
            "Kein explizites Bug-Screen-Scheme im Issue Type Screen Scheme"
        )
        return details

    details.bug_screen_scheme_id = bug_scheme_id
    if bug_scheme_id not in screen_schemes:
        screen_schemes.update(fetch_screen_schemes({bug_scheme_id}))

    bug_scheme = screen_schemes.get(bug_scheme_id)
    if bug_scheme is None:
        details.warnings.append(
            f"Bug-Screen-Scheme id={bug_scheme_id} nicht per API auflösbar"
        )
        return details

    details.bug_screen_scheme_name = bug_scheme.name
    if not bug_scheme.screens:
        details.warnings.append(
            f"Bug-Screen-Scheme '{bug_scheme.name}' (id={bug_scheme.scheme_id}) hat keine Screens"
        )
        return details

    needed_screen_ids = set(bug_scheme.screens.values()) - set(screens)
    if needed_screen_ids:
        screens.update(fetch_screens(needed_screen_ids))

    for operation in SCREEN_OPS:
        screen_id = bug_scheme.screens.get(operation)
        if screen_id is None:
            continue
        screen = screens.get(screen_id)
        if screen is None:
            details.warnings.append(
                f"Screen id={screen_id} ({operation}) nicht per API auflösbar"
            )
            continue
        details.screens.append(
            ResolvedScreen(
                operation=operation,
                screen_id=screen.screen_id,
                screen_name=screen.name,
            )
        )

    if not details.screens:
        details.warnings.append("Keine Bug-Screens auflösbar")

    return details


def collect_details(projects: list[str]) -> list[ProjectBugScreenDetails]:
    results: list[ProjectBugScreenDetails] = []
    screen_schemes: dict[str, ScreenSchemeInfo] = {}
    screens: dict[str, ScreenInfo] = {}

    for key in projects:
        try:
            project = fetch_project(key)
        except requests.HTTPError as exc:
            results.append(
                ProjectBugScreenDetails(
                    project_key=key,
                    project_name=key,
                    error=_http_error_message(exc),
                )
            )
            continue
        except Exception as exc:
            results.append(
                ProjectBugScreenDetails(
                    project_key=key,
                    project_name=key,
                    error=str(exc),
                )
            )
            continue

        try:
            results.append(resolve_project(project, screen_schemes, screens))
        except requests.HTTPError as exc:
            results.append(
                ProjectBugScreenDetails(
                    project_key=project.key,
                    project_name=project.name,
                    error=_http_error_message(exc),
                )
            )
        except Exception as exc:
            results.append(
                ProjectBugScreenDetails(
                    project_key=project.key,
                    project_name=project.name,
                    error=str(exc),
                )
            )

    return results


def _primary_screen(details: ProjectBugScreenDetails) -> ResolvedScreen | None:
    by_op = {screen.operation: screen for screen in details.screens}
    for operation in ("create", "default", "edit", "view"):
        if operation in by_op:
            return by_op[operation]
    return details.screens[0] if details.screens else None


def format_detail_line(details: ProjectBugScreenDetails) -> str:
    if details.error:
        return f"{details.project_key}: ERROR {details.error}"

    if details.warnings:
        warning_text = "; ".join(details.warnings)
        return f"{details.project_key}: WARNING {warning_text}"

    screen_parts = [
        f"{screen.operation}={screen.screen_name} (id={screen.screen_id})"
        for screen in details.screens
    ]
    return (
        f"{details.project_key}: "
        f"ITSS={details.issue_type_screen_scheme_name} (id={details.issue_type_screen_scheme_id}) | "
        f"screen_scheme={details.bug_screen_scheme_name} (id={details.bug_screen_scheme_id}) | "
        + " | ".join(screen_parts)
    )


def format_compact_line(details: ProjectBugScreenDetails) -> str:
    if details.error:
        return f"{details.project_key}: ERROR {details.error}"
    if details.warnings:
        return f"{details.project_key}: WARNING {'; '.join(details.warnings)}"

    primary = _primary_screen(details)
    if primary is None:
        return f"{details.project_key}: WARNING Kein Bug-Screen gefunden"

    unique_screens = {
        (screen.screen_id, screen.screen_name) for screen in details.screens
    }
    if len(unique_screens) == 1:
        return (
            f"{details.project_key}: {primary.screen_name} (id={primary.screen_id})"
        )

    names = ", ".join(
        f"{screen.operation}={screen.screen_name} (id={screen.screen_id})"
        for screen in details.screens
    )
    return f"{details.project_key}: {names}"


def build_output_lines(results: list[ProjectBugScreenDetails]) -> list[str]:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Bug screens per space (generated {generated})",
        "# Chain: Project -> Issue Type Screen Scheme -> Bug Screen Scheme -> Screen(s)",
        "",
    ]

    warnings: list[str] = []
    for details in results:
        if details.error:
            warnings.append(f"{details.project_key}: {details.error}")
        for warning in details.warnings:
            warnings.append(f"{details.project_key}: {warning}")

    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(warnings)
        lines.append("")

    lines.extend(["## Bug screens", ""])
    for details in results:
        lines.append(format_compact_line(details))

    lines.extend(["", "## Full chain", ""])
    for details in results:
        lines.append(format_detail_line(details))

    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve Bug screens for Jira spaces via Issue Type Screen Scheme chain "
            "and write them to a text file."
        )
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=DEFAULT_PROJECTS,
        help=f"Project keys to check (default: {' '.join(DEFAULT_PROJECTS)})",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"Text output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    projects = [project.upper() for project in args.projects]

    print(f"Resolving Bug screens for {len(projects)} space(s) ...")
    results = collect_details(projects)
    lines = build_output_lines(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    output_path.write_text(text, encoding="utf-8", newline="\n")

    ok_count = sum(1 for item in results if item.ok)
    warn_count = sum(1 for item in results if item.warnings and item.error is None)
    error_count = sum(1 for item in results if item.error)

    print(f"Resolved: {ok_count} ok, {warn_count} with warnings, {error_count} errors")
    print()
    for details in results:
        print(f"  {format_compact_line(details)}")
    print(f"\nWritten: {output_path}")

    if warn_count or error_count:
        print()
        print("Warnings / errors:")
        for details in results:
            if details.error:
                print(f"  {details.project_key}: {details.error}")
            for warning in details.warnings:
                print(f"  {details.project_key}: {warning}")
        sys.exit(1)


if __name__ == "__main__":
    main()
