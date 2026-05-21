"""Check Jira project workflows for blocker-like statuses.

The script first discovers all Jira statuses and derives a semantic list of
statuses that look like Blocked, Waiting, On Hold, Impediment, or similar.
It then checks whether Task, Bug, and Story workflows in selected projects
contain any of those statuses and writes a Markdown report.

Usage:
    py src/check_project_workflow_statuses.py
    py src/check_project_workflow_statuses.py --output tmp/jira-workflow-blocked-statuses.md
    py src/check_project_workflow_statuses.py --projects REVIN INV --include-keywords escalation dependency
    py src/check_project_workflow_statuses.py --exclude-statuses "Waiting for release"
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_PROJECTS = [
    "REVIN",
    "INV",
    "QUE",
    "RM",
    "CC",
    "LSRT",
    "PL",
    "TPSCON",
    "TBI",
    "TCT",
    "TCM",
    "GUARANTEE",
    "CA",
    "SEO",
]
DEFAULT_ISSUE_TYPES = ["Task", "Bug", "Story"]
DEFAULT_OUTPUT = "tmp/jira-workflow-blocked-statuses.md"

ISSUE_TYPE_ALIASES = {
    "task": {"task", "aufgabe"},
    "bug": {"bug", "fehler"},
    "story": {"story", "user story", "user-story"},
}

DEFAULT_STATUS_KEYWORDS = [
    "blocked",
    "blocker",
    "blockade",
    "blockiert",
    "waiting",
    "awaiting",
    "wartend",
    "warten",
    "on hold",
    "hold",
    "impediment",
    "paused",
    "pause",
    "stalled",
    "stuck",
    "pending",
    "dependency",
    "dependencies",
    "depending",
    "dependent",
    "dependant",
    "external",
    "abhaengig",
    "abhängig",
    "zurueckgestellt",
    "zurückgestellt",
    "deferred",
    "suspended",
]


@dataclass(frozen=True)
class StatusCandidate:
    id: str
    name: str
    category: str
    matches: tuple[str, ...]


@dataclass(frozen=True)
class IssueTypeResult:
    project: str
    issue_type: str
    workflow_statuses: tuple[str, ...]
    matched_statuses: tuple[str, ...]
    missing: bool = False


@dataclass(frozen=True)
class ProjectError:
    project: str
    error: str


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


def jira_get(path: str, params: dict[str, Any] | None = None) -> Any:
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


def normalize_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = without_accents.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def keyword_matches(status_name: str, keywords: list[str]) -> tuple[str, ...]:
    normalized_name = f" {normalize_text(status_name)} "
    matches: list[str] = []

    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            continue
        if f" {normalized_keyword} " in normalized_name:
            matches.append(keyword)

    return tuple(dict.fromkeys(matches))


def fetch_all_statuses() -> list[dict[str, Any]]:
    """Fetch all Jira statuses, preferring the paginated search endpoint."""
    try:
        statuses: list[dict[str, Any]] = []
        start_at = 0
        max_results = 200

        while True:
            data = jira_get(
                "/rest/api/3/statuses/search",
                {"startAt": start_at, "maxResults": max_results},
            )
            values = data.get("values") or []
            statuses.extend(values)

            if data.get("isLast", False) or not values:
                break
            start_at += len(values)
            if start_at >= data.get("total", start_at):
                break

        return statuses
    except requests.HTTPError:
        data = jira_get("/rest/api/3/status")
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response from /rest/api/3/status")
        return data


def classify_status_candidates(
    statuses: list[dict[str, Any]],
    include_keywords: list[str],
    exclude_statuses: list[str],
) -> list[StatusCandidate]:
    keywords = DEFAULT_STATUS_KEYWORDS + include_keywords
    excluded = {normalize_text(status) for status in exclude_statuses}
    candidates: list[StatusCandidate] = []
    seen_ids: set[str] = set()

    for status in statuses:
        name = str(status.get("name") or "")
        if not name or normalize_text(name) in excluded:
            continue

        matches = keyword_matches(name, keywords)
        if not matches:
            continue

        status_id = str(status.get("id") or name)
        if status_id in seen_ids:
            continue
        seen_ids.add(status_id)

        raw_category = status.get("statusCategory") or {}
        category_name = raw_category.get("name") if isinstance(raw_category, dict) else raw_category
        candidates.append(
            StatusCandidate(
                id=status_id,
                name=name,
                category=str(category_name or "n/a"),
                matches=matches,
            )
        )

    candidates.sort(key=lambda candidate: normalize_text(candidate.name))
    return candidates


def canonical_issue_type(name: str) -> str | None:
    normalized = normalize_text(name)
    for canonical, aliases in ISSUE_TYPE_ALIASES.items():
        if normalized in {normalize_text(alias) for alias in aliases}:
            return canonical
    return None


def fetch_project_issue_type_statuses(project: str) -> list[dict[str, Any]]:
    data = jira_get(f"/rest/api/3/project/{project}/statuses")
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected status response for project {project}")
    return data


def evaluate_projects(
    projects: list[str],
    issue_types: list[str],
    candidate_statuses: list[StatusCandidate],
) -> tuple[list[IssueTypeResult], list[ProjectError]]:
    candidate_names = {normalize_text(candidate.name) for candidate in candidate_statuses}
    wanted_issue_types = {normalize_text(issue_type): issue_type for issue_type in issue_types}
    results: list[IssueTypeResult] = []
    errors: list[ProjectError] = []

    for project in projects:
        try:
            issue_type_statuses = fetch_project_issue_type_statuses(project)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            detail = exc.response.text[:200] if exc.response is not None else str(exc)
            errors.append(ProjectError(project=project, error=f"HTTP {status_code}: {detail}"))
            continue
        except Exception as exc:
            errors.append(ProjectError(project=project, error=str(exc)))
            continue

        by_canonical_type: dict[str, dict[str, Any]] = {}
        for item in issue_type_statuses:
            issue_type_name = str(item.get("name") or "")
            canonical = canonical_issue_type(issue_type_name)
            if canonical:
                by_canonical_type[canonical] = item

        for normalized_wanted, display_issue_type in wanted_issue_types.items():
            item = by_canonical_type.get(normalized_wanted)
            if item is None:
                results.append(
                    IssueTypeResult(
                        project=project,
                        issue_type=display_issue_type,
                        workflow_statuses=(),
                        matched_statuses=(),
                        missing=True,
                    )
                )
                continue

            statuses = tuple(str(status.get("name") or "") for status in item.get("statuses") or [])
            matched = tuple(
                status_name for status_name in statuses if normalize_text(status_name) in candidate_names
            )
            results.append(
                IssueTypeResult(
                    project=project,
                    issue_type=display_issue_type,
                    workflow_statuses=statuses,
                    matched_statuses=matched,
                )
            )

    return results, errors


def markdown_escape(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def format_list(values: tuple[str, ...] | list[str]) -> str:
    if not values:
        return "-"
    return ", ".join(markdown_escape(value) for value in values)


def build_markdown(
    projects: list[str],
    issue_types: list[str],
    candidates: list[StatusCandidate],
    results: list[IssueTypeResult],
    errors: list[ProjectError],
) -> str:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines: list[str] = [
        "# Jira Workflow Blocker Status Check",
        "",
        f"Erstellt: {timestamp}",
        "",
        f"Projekte: {', '.join(projects)}",
        "",
        f"Issue Types: {', '.join(issue_types)}",
        "",
        "## Abgeleitete Status-Kandidaten",
        "",
    ]

    if candidates:
        lines.extend(
            [
                "| Status | Status Category | Match-Grund |",
                "| --- | --- | --- |",
            ]
        )
        for candidate in candidates:
            lines.append(
                "| "
                f"{markdown_escape(candidate.name)} | "
                f"{markdown_escape(candidate.category)} | "
                f"{format_list(list(candidate.matches))} |"
            )
    else:
        lines.append("Keine semantisch passenden Status gefunden.")

    lines.extend(
        [
            "",
            "## Projekt-Auswertung",
            "",
            "| Projekt | Issue Type | Hat Kandidatenstatus? | Gefundene Kandidatenstatus | Alle Workflow-Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for result in results:
        if result.missing:
            has_candidate = "Issue Type nicht gefunden"
        else:
            has_candidate = "Ja" if result.matched_statuses else "Nein"

        lines.append(
            "| "
            f"{markdown_escape(result.project)} | "
            f"{markdown_escape(result.issue_type)} | "
            f"{has_candidate} | "
            f"{format_list(result.matched_statuses)} | "
            f"{format_list(result.workflow_statuses)} |"
        )

    lines.extend(["", "## Fehler / fehlende Rechte", ""])
    if errors:
        lines.extend(["| Projekt | Fehler |", "| --- | --- |"])
        for error in errors:
            lines.append(f"| {markdown_escape(error.project)} | {markdown_escape(error.error)} |")
    else:
        lines.append("Keine Fehler.")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether selected Jira projects have blocker-like workflow statuses "
            "for Task, Bug, and Story issue types."
        )
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=DEFAULT_PROJECTS,
        help=f"Project keys to check (default: {' '.join(DEFAULT_PROJECTS)})",
    )
    parser.add_argument(
        "--issue-types",
        nargs="+",
        default=DEFAULT_ISSUE_TYPES,
        help=f"Issue type names to check (default: {' '.join(DEFAULT_ISSUE_TYPES)})",
    )
    parser.add_argument(
        "--include-keywords",
        nargs="*",
        default=[],
        help="Additional keywords or phrases for semantic status candidate detection.",
    )
    parser.add_argument(
        "--exclude-statuses",
        nargs="*",
        default=[],
        help="Exact status names to exclude from semantic status candidate detection.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Markdown output path (default: {DEFAULT_OUTPUT})",
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

    print("Fetching all Jira statuses ...")
    all_statuses = fetch_all_statuses()
    candidates = classify_status_candidates(
        all_statuses,
        include_keywords=args.include_keywords,
        exclude_statuses=args.exclude_statuses,
    )
    print(f"Found {len(candidates)} blocker-like status candidate(s).")

    print("Checking project workflow statuses ...")
    results, errors = evaluate_projects(projects, args.issue_types, candidates)

    markdown = build_markdown(projects, args.issue_types, candidates, results, errors)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8", newline="\n")

    print(f"Markdown written to: {output_path}")
    if errors:
        print(f"Completed with {len(errors)} project error(s). See report for details.")


if __name__ == "__main__":
    main()
