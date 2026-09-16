"""List Jira Field Schemes used by selected spaces (projects).

Uses the Field Schemes API (`/rest/api/3/config/fieldschemes`), which replaced
legacy field configuration schemes. Writes unique scheme names to a text file,
one scheme per line.

Usage:
    py src/list_project_field_schemes.py
    py src/list_project_field_schemes.py --output tmp/jira-field-schemes.txt
    py src/list_project_field_schemes.py --projects REVIN INV --format mapping
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
DEFAULT_OUTPUT = "tmp/jira-field-schemes.txt"


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
class FieldScheme:
    scheme_id: str
    name: str
    is_default: bool
    fields_count: int | None


@dataclass(frozen=True)
class SchemeAssignment:
    project_key: str
    project_name: str
    scheme_name: str
    scheme_id: str | None
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
            "HTTP 403: Administer Jira permission required to read Field Schemes"
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


def parse_field_scheme(raw: dict[str, Any]) -> FieldScheme:
    scheme_id = raw.get("id")
    if scheme_id is None:
        raise RuntimeError("Field scheme response is missing id")
    return FieldScheme(
        scheme_id=str(scheme_id),
        name=str(raw.get("name") or f"Unnamed scheme {scheme_id}"),
        is_default=bool(raw.get("isDefault")),
        fields_count=raw.get("fieldsCount") if isinstance(raw.get("fieldsCount"), int) else None,
    )


def fetch_field_schemes(project_ids: list[str]) -> dict[str, FieldScheme]:
    extra = [("projectId", project_id) for project_id in project_ids]
    schemes = [parse_field_scheme(item) for item in fetch_paginated("/rest/api/3/config/fieldschemes", extra)]
    return {scheme.scheme_id: scheme for scheme in schemes}


def fetch_project_scheme_ids(project_ids: list[str]) -> dict[str, str]:
    extra = [("projectId", project_id) for project_id in project_ids]
    assigned: dict[str, str] = {}
    for item in fetch_paginated("/rest/api/3/config/fieldschemes/projects", extra):
        project_id = item.get("projectId")
        scheme_id = item.get("schemeId")
        if project_id is None or scheme_id is None:
            continue
        assigned[str(project_id)] = str(scheme_id)
    return assigned


def fetch_field_scheme(scheme_id: str) -> FieldScheme:
    data = jira_get(f"/rest/api/3/config/fieldschemes/{scheme_id}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected field scheme response for {scheme_id}")
    return parse_field_scheme(data)


def collect_assignments(projects: list[str]) -> list[SchemeAssignment]:
    loaded: list[ProjectInfo] = []
    assignments: list[SchemeAssignment] = []

    for key in projects:
        try:
            loaded.append(fetch_project(key))
        except requests.HTTPError as exc:
            assignments.append(
                SchemeAssignment(
                    project_key=key,
                    project_name=key,
                    scheme_name="",
                    scheme_id=None,
                    error=_http_error_message(exc),
                )
            )
        except Exception as exc:
            assignments.append(
                SchemeAssignment(
                    project_key=key,
                    project_name=key,
                    scheme_name="",
                    scheme_id=None,
                    error=str(exc),
                )
            )

    project_ids = [project.project_id for project in loaded if project.project_id]
    try:
        schemes = fetch_field_schemes(project_ids)
        assigned_ids = fetch_project_scheme_ids(project_ids)
    except requests.HTTPError as exc:
        error = _http_error_message(exc)
        for project in loaded:
            assignments.append(
                SchemeAssignment(
                    project_key=project.key,
                    project_name=project.name,
                    scheme_name="",
                    scheme_id=None,
                    error=error,
                )
            )
        return assignments

    for project in loaded:
        scheme_id = assigned_ids.get(project.project_id)
        if not scheme_id:
            assignments.append(
                SchemeAssignment(
                    project_key=project.key,
                    project_name=project.name,
                    scheme_name="",
                    scheme_id=None,
                    error="Kein Field Scheme zugeordnet",
                )
            )
            continue

        scheme = schemes.get(scheme_id)
        if scheme is None:
            try:
                scheme = fetch_field_scheme(scheme_id)
                schemes[scheme_id] = scheme
            except Exception as exc:
                message = _http_error_message(exc) if isinstance(exc, requests.HTTPError) else str(exc)
                assignments.append(
                    SchemeAssignment(
                        project_key=project.key,
                        project_name=project.name,
                        scheme_name="",
                        scheme_id=scheme_id,
                        error=message,
                    )
                )
                continue

        assignments.append(
            SchemeAssignment(
                project_key=project.key,
                project_name=project.name,
                scheme_name=scheme.name,
                scheme_id=scheme.scheme_id,
            )
        )

    return assignments


def unique_scheme_names(assignments: list[SchemeAssignment]) -> list[str]:
    names = [item.scheme_name for item in assignments if item.scheme_name and item.error is None]
    return sorted(dict.fromkeys(names), key=str.casefold)


def format_mapping_lines(assignments: list[SchemeAssignment]) -> list[str]:
    lines: list[str] = []
    for item in assignments:
        if item.error:
            lines.append(f"{item.project_key}: ERROR {item.error}")
            continue
        scheme_id = f" (id={item.scheme_id})" if item.scheme_id else ""
        lines.append(f"{item.project_key}: {item.scheme_name}{scheme_id}")
    return lines


def output_lines(assignments: list[SchemeAssignment], fmt: str) -> list[str]:
    if fmt == "mapping":
        return format_mapping_lines(assignments)
    return unique_scheme_names(assignments)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List Field Schemes used by selected Jira spaces/projects "
            "and write them to a text file, one scheme per line."
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
        choices=("unique", "mapping"),
        default="unique",
        help=(
            "unique: distinct scheme names, one per line (default). "
            "mapping: one 'PROJECT: scheme' line per project."
        ),
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

    print(f"Loading {len(projects)} space(s) and Field Schemes ...")
    assignments = collect_assignments(projects)
    lines = output_lines(assignments, args.format)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if text:
        text += "\n"
    output_path.write_text(text, encoding="utf-8", newline="\n")

    print("Space mapping:")
    for line in format_mapping_lines(assignments):
        print(f"  {line}")
    print(f"Written ({args.format}): {output_path}")

    errors = [item for item in assignments if item.error]
    if errors:
        print(f"Completed with {len(errors)} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
