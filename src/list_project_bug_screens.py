"""Check which Jira spaces use a dedicated Screen for the Bug issue type.

A project has its own Bug screen when the effective screen(s) for Bug differ from
the default screen mapping of its Issue Type Screen Scheme — i.e. Bug does not
simply inherit the scheme's default screens.

Uses Issue Type Screen Scheme + Screen Scheme APIs (classic/company-managed projects).

Usage:
    py src/list_project_bug_screens.py
    py src/list_project_bug_screens.py --output tmp/jira-bug-screens.txt
    py src/list_project_bug_screens.py --projects REVIN INV --format mapping
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
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
DEFAULT_OUTPUT = "tmp/jira-bug-screens.txt"
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
class BugScreenResult:
    project_key: str
    project_name: str
    issue_type_screen_scheme_name: str
    bug_screen_scheme_name: str
    default_screen_scheme_name: str
    has_own_bug_screen: bool
    explicit_bug_mapping: bool
    bug_screens: dict[str, str]
    default_screens: dict[str, str]
    bug_screen_names: dict[str, str]
    default_screen_names: dict[str, str]
    error: str | None = None


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


def _screen_ids_for_scheme(scheme: ScreenSchemeInfo | None) -> dict[str, str]:
    if scheme is None:
        return {}
    return dict(scheme.screens)


def _screens_differ(bug_screens: dict[str, str], default_screens: dict[str, str]) -> bool:
    if not bug_screens and not default_screens:
        return False
    all_ops = set(bug_screens) | set(default_screens)
    return any(bug_screens.get(op) != default_screens.get(op) for op in all_ops)


def _resolve_names(screen_map: dict[str, str], catalog: dict[str, ScreenInfo]) -> dict[str, str]:
    names: dict[str, str] = {}
    for op, screen_id in screen_map.items():
        info = catalog.get(screen_id)
        names[op] = info.name if info else f"Screen {screen_id}"
    return names


def analyze_project(
    project: ProjectInfo,
    screen_schemes: dict[str, ScreenSchemeInfo],
    screens: dict[str, ScreenInfo],
) -> BugScreenResult:
    itss = fetch_project_issue_type_screen_scheme(project.project_id)
    if itss is None:
        return BugScreenResult(
            project_key=project.key,
            project_name=project.name,
            issue_type_screen_scheme_name="",
            bug_screen_scheme_name="",
            default_screen_scheme_name="",
            has_own_bug_screen=False,
            explicit_bug_mapping=False,
            bug_screens={},
            default_screens={},
            bug_screen_names={},
            default_screen_names={},
            error="Kein Issue Type Screen Scheme zugeordnet",
        )

    itss_id, itss_name = itss
    bug_type_id = fetch_bug_issue_type_id(project.project_id)
    if bug_type_id is None:
        return BugScreenResult(
            project_key=project.key,
            project_name=project.name,
            issue_type_screen_scheme_name=itss_name,
            bug_screen_scheme_name="",
            default_screen_scheme_name="",
            has_own_bug_screen=False,
            explicit_bug_mapping=False,
            bug_screens={},
            default_screens={},
            bug_screen_names={},
            default_screen_names={},
            error="Issue Type Bug nicht im Projekt vorhanden",
        )

    mappings = fetch_itss_mappings(itss_id)
    default_scheme_id: str | None = None
    bug_scheme_id: str | None = None
    explicit_bug_mapping = False

    for mapping in mappings:
        issue_type_id = str(mapping.get("issueTypeId") or "")
        screen_scheme_id = mapping.get("screenSchemeId")
        if screen_scheme_id is None:
            continue
        if issue_type_id == "default":
            default_scheme_id = str(screen_scheme_id)
        elif issue_type_id == bug_type_id:
            bug_scheme_id = str(screen_scheme_id)
            explicit_bug_mapping = True

    if bug_scheme_id is None:
        bug_scheme_id = default_scheme_id

    if default_scheme_id is None or bug_scheme_id is None:
        return BugScreenResult(
            project_key=project.key,
            project_name=project.name,
            issue_type_screen_scheme_name=itss_name,
            bug_screen_scheme_name="",
            default_screen_scheme_name="",
            has_own_bug_screen=False,
            explicit_bug_mapping=explicit_bug_mapping,
            bug_screens={},
            default_screens={},
            bug_screen_names={},
            default_screen_names={},
            error="Screen-Scheme-Zuordnung unvollständig",
        )

    needed_scheme_ids = {default_scheme_id, bug_scheme_id} - set(screen_schemes)
    if needed_scheme_ids:
        screen_schemes.update(fetch_screen_schemes(needed_scheme_ids))

    default_scheme = screen_schemes.get(default_scheme_id)
    bug_scheme = screen_schemes.get(bug_scheme_id)

    default_screens = _screen_ids_for_scheme(default_scheme)
    bug_screens = _screen_ids_for_scheme(bug_scheme)

    needed_screen_ids = set(default_screens.values()) | set(bug_screens.values()) - set(screens)
    if needed_screen_ids:
        screens.update(fetch_screens(needed_screen_ids))

    has_own_bug_screen = _screens_differ(bug_screens, default_screens)

    return BugScreenResult(
        project_key=project.key,
        project_name=project.name,
        issue_type_screen_scheme_name=itss_name,
        bug_screen_scheme_name=bug_scheme.name if bug_scheme else "",
        default_screen_scheme_name=default_scheme.name if default_scheme else "",
        has_own_bug_screen=has_own_bug_screen,
        explicit_bug_mapping=explicit_bug_mapping,
        bug_screens=bug_screens,
        default_screens=default_screens,
        bug_screen_names=_resolve_names(bug_screens, screens),
        default_screen_names=_resolve_names(default_screens, screens),
    )


def collect_results(projects: list[str]) -> list[BugScreenResult]:
    results: list[BugScreenResult] = []
    screen_schemes: dict[str, ScreenSchemeInfo] = {}
    screens: dict[str, ScreenInfo] = {}

    for key in projects:
        try:
            project = fetch_project(key)
        except requests.HTTPError as exc:
            results.append(
                BugScreenResult(
                    project_key=key,
                    project_name=key,
                    issue_type_screen_scheme_name="",
                    bug_screen_scheme_name="",
                    default_screen_scheme_name="",
                    has_own_bug_screen=False,
                    explicit_bug_mapping=False,
                    bug_screens={},
                    default_screens={},
                    bug_screen_names={},
                    default_screen_names={},
                    error=_http_error_message(exc),
                )
            )
            continue
        except Exception as exc:
            results.append(
                BugScreenResult(
                    project_key=key,
                    project_name=key,
                    issue_type_screen_scheme_name="",
                    bug_screen_scheme_name="",
                    default_screen_scheme_name="",
                    has_own_bug_screen=False,
                    explicit_bug_mapping=False,
                    bug_screens={},
                    default_screens={},
                    bug_screen_names={},
                    default_screen_names={},
                    error=str(exc),
                )
            )
            continue

        try:
            results.append(analyze_project(project, screen_schemes, screens))
        except requests.HTTPError as exc:
            results.append(
                BugScreenResult(
                    project_key=project.key,
                    project_name=project.name,
                    issue_type_screen_scheme_name="",
                    bug_screen_scheme_name="",
                    default_screen_scheme_name="",
                    has_own_bug_screen=False,
                    explicit_bug_mapping=False,
                    bug_screens={},
                    default_screens={},
                    bug_screen_names={},
                    default_screen_names={},
                    error=_http_error_message(exc),
                )
            )
        except Exception as exc:
            results.append(
                BugScreenResult(
                    project_key=project.key,
                    project_name=project.name,
                    issue_type_screen_scheme_name="",
                    bug_screen_scheme_name="",
                    default_screen_scheme_name="",
                    has_own_bug_screen=False,
                    explicit_bug_mapping=False,
                    bug_screens={},
                    default_screens={},
                    bug_screen_names={},
                    default_screen_names={},
                    error=str(exc),
                )
            )

    return results


def format_mapping_line(result: BugScreenResult) -> str:
    if result.error:
        return f"{result.project_key}: ERROR {result.error}"

    status = "OWN" if result.has_own_bug_screen else "shared"
    bug_create = result.bug_screen_names.get("create") or result.bug_screen_names.get("default") or "?"
    default_create = result.default_screen_names.get("create") or result.default_screen_names.get("default") or "?"

    if result.has_own_bug_screen:
        return (
            f"{result.project_key}: {status} — Bug screen: {bug_create}"
            f" (default would be: {default_create})"
        )
    return f"{result.project_key}: {status} — uses default screen: {default_create}"


def format_summary_lines(results: list[BugScreenResult]) -> list[str]:
    own = [r.project_key for r in results if r.has_own_bug_screen and r.error is None]
    shared = [r.project_key for r in results if not r.has_own_bug_screen and r.error is None]
    errors = [r.project_key for r in results if r.error]

    lines = [
        f"Own Bug screen ({len(own)}): {', '.join(own) if own else '-'}",
        f"Shared/default Bug screen ({len(shared)}): {', '.join(shared) if shared else '-'}",
    ]
    if errors:
        lines.append(f"Errors ({len(errors)}): {', '.join(errors)}")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List Jira spaces that use a dedicated Screen for the Bug issue type "
            "(Bug screens differ from the Issue Type Screen Scheme default)."
        )
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=DEFAULT_PROJECTS,
        help=f"Project keys to check (default: {' '.join(DEFAULT_PROJECTS)})",
    )
    parser.add_argument(
        "--format",
        choices=("mapping", "summary", "own-only"),
        default="mapping",
        help="mapping: per-project line. summary: grouped result. own-only: keys with own Bug screen.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"Text output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def output_lines(results: list[BugScreenResult], fmt: str) -> list[str]:
    if fmt == "summary":
        return format_summary_lines(results)
    if fmt == "own-only":
        return [r.project_key for r in results if r.has_own_bug_screen and r.error is None]
    return [format_mapping_line(r) for r in results]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    projects = [project.upper() for project in args.projects]

    print(f"Checking Bug screens for {len(projects)} space(s) ...")
    results = collect_results(projects)
    lines = output_lines(results, args.format)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if text:
        text += "\n"
    output_path.write_text(text, encoding="utf-8", newline="\n")

    print()
    for line in format_summary_lines(results):
        print(line)
    print()
    print("Per space:")
    for result in results:
        print(f"  {format_mapping_line(result)}")
    print(f"\nWritten ({args.format}): {output_path}")

    errors = [r for r in results if r.error]
    if errors:
        print(f"Completed with {len(errors)} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
