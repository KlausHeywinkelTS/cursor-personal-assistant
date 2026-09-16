"""Add bug triage fields to Bug screens listed in tmp/jira-bug-screen-list.txt.

Adds these fields to the first tab of each unique Bug screen:
  - Has customer impact (customfield_11260)
  - Has CSM relevance (customfield_11261)

Note: Jira field name is "Has CSM relevance", not CMS.

Usage:
    py src/add_bug_screen_fields.py --dry-run
    py src/add_bug_screen_fields.py --apply
    py src/add_bug_screen_fields.py --apply --input tmp/jira-bug-screen-list.txt
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_INPUT = "tmp/jira-bug-screen-list.txt"
DEFAULT_REPORT = "tmp/jira-bug-screen-fields-report.txt"
SCREEN_LINE_RE = re.compile(r"^([A-Z0-9]+):\s+.+\(id=(\d+)\)\s*$")

FIELDS_TO_ADD = [
    ("customfield_11260", "Has customer impact"),
    ("customfield_11261", "Has CSM relevance"),
]


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
class BugScreenRef:
    project_key: str
    screen_id: str
    screen_name: str


@dataclass
class ScreenFieldResult:
    screen_id: str
    screen_name: str
    project_keys: list[str]
    tab_id: str = ""
    tab_name: str = ""
    added: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def jira_request(method: str, path: str, params: Any | None = None, json_body: Any | None = None) -> Any:
    user, token = _get_jira_auth()
    response = requests.request(
        method,
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        auth=(user, token),
        params=params or {},
        json=json_body,
        timeout=30,
    )
    response.raise_for_status()
    if response.text:
        return response.json()
    return None


def jira_get(path: str, params: Any | None = None) -> Any:
    return jira_request("GET", path, params=params)


def _http_error_message(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else "?"
    detail = ""
    if exc.response is not None:
        detail = (exc.response.text or "").strip().replace("\n", " ")
        if len(detail) > 240:
            detail = detail[:237] + "..."
    return f"HTTP {status}" + (f": {detail}" if detail else "")


def parse_bug_screens(input_path: Path) -> list[BugScreenRef]:
    refs: list[BugScreenRef] = []
    in_section = False
    for line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "## Bug screens":
            in_section = True
            continue
        if stripped.startswith("## ") and stripped != "## Bug screens":
            in_section = False
            continue
        if not in_section or not stripped or stripped.startswith("#"):
            continue
        match = SCREEN_LINE_RE.match(stripped)
        if not match:
            continue
        project_key, screen_id = match.group(1), match.group(2)
        screen_name = stripped.split(":", 1)[1].rsplit("(id=", 1)[0].strip()
        refs.append(BugScreenRef(project_key=project_key, screen_id=screen_id, screen_name=screen_name))
    return refs


def group_by_screen(refs: list[BugScreenRef]) -> dict[str, tuple[str, list[str]]]:
    grouped: dict[str, tuple[str, list[str]]] = {}
    for ref in refs:
        existing = grouped.get(ref.screen_id)
        if existing is None:
            grouped[ref.screen_id] = (ref.screen_name, [ref.project_key])
        elif ref.project_key not in existing[1]:
            existing[1].append(ref.project_key)
    return grouped


def fetch_screen_name(screen_id: str) -> str:
    data = jira_get("/rest/api/3/screens", params={"id": screen_id})
    values = data.get("values") if isinstance(data, dict) else None
    if values:
        return str(values[0].get("name") or f"Screen {screen_id}")
    return f"Screen {screen_id}"


def fetch_first_tab(screen_id: str) -> tuple[str, str]:
    tabs = jira_get(f"/rest/api/3/screens/{screen_id}/tabs")
    if not isinstance(tabs, list) or not tabs:
        raise RuntimeError(f"Screen {screen_id} has no tabs")
    tab = tabs[0]
    return str(tab["id"]), str(tab.get("name") or "Tab")


def fetch_tab_field_ids(screen_id: str, tab_id: str) -> set[str]:
    fields = jira_get(f"/rest/api/3/screens/{screen_id}/tabs/{tab_id}/fields")
    if not isinstance(fields, list):
        return set()
    return {str(item.get("id")) for item in fields if item.get("id")}


def add_field_to_tab(screen_id: str, tab_id: str, field_id: str) -> None:
    jira_request(
        "POST",
        f"/rest/api/3/screens/{screen_id}/tabs/{tab_id}/fields",
        json_body={"fieldId": field_id},
    )


def process_screen(
    screen_id: str,
    screen_name: str,
    project_keys: list[str],
    apply: bool,
) -> ScreenFieldResult:
    result = ScreenFieldResult(
        screen_id=screen_id,
        screen_name=screen_name,
        project_keys=project_keys,
    )

    try:
        result.screen_name = fetch_screen_name(screen_id)
        result.tab_id, result.tab_name = fetch_first_tab(screen_id)
        present = fetch_tab_field_ids(screen_id, result.tab_id)
    except requests.HTTPError as exc:
        result.errors.append(_http_error_message(exc))
        return result
    except Exception as exc:
        result.errors.append(str(exc))
        return result

    for field_id, field_name in FIELDS_TO_ADD:
        label = f"{field_name} ({field_id})"
        if field_id in present:
            result.already_present.append(label)
            continue

        if not apply:
            result.added.append(label)
            continue

        try:
            add_field_to_tab(screen_id, result.tab_id, field_id)
            result.added.append(label)
        except requests.HTTPError as exc:
            result.errors.append(f"{label}: {_http_error_message(exc)}")
        except Exception as exc:
            result.errors.append(f"{label}: {exc}")

    return result


def build_report_lines(results: list[ScreenFieldResult], apply: bool) -> list[str]:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode = "apply" if apply else "dry-run"
    lines = [
        f"# Bug screen fields report ({mode}, generated {generated})",
        f"# Fields: {', '.join(name for _, name in FIELDS_TO_ADD)}",
        "",
    ]

    errors = [r for r in results if r.errors]
    if errors:
        lines.extend(["## Errors", ""])
        for result in errors:
            spaces = ", ".join(result.project_keys)
            lines.append(f"Screen {result.screen_id} ({result.screen_name}) [{spaces}]")
            for error in result.errors:
                lines.append(f"  - {error}")
        lines.append("")

    lines.extend(["## Results", ""])
    for result in results:
        spaces = ", ".join(result.project_keys)
        lines.append(
            f"{result.screen_id} | {result.screen_name} | spaces: {spaces} | tab: {result.tab_name} ({result.tab_id})"
        )
        if result.added:
            action = "added" if apply else "would add"
            lines.append(f"  {action}: {', '.join(result.added)}")
        if result.already_present:
            lines.append(f"  already present: {', '.join(result.already_present)}")
        if not result.added and not result.already_present and not result.errors:
            lines.append("  no changes")
        lines.append("")

    added_count = sum(len(r.added) for r in results)
    present_count = sum(len(r.already_present) for r in results)
    error_count = sum(len(r.errors) for r in results)
    lines.append(
        f"Summary: {len(results)} screen(s), {added_count} field addition(s), "
        f"{present_count} already present, {error_count} error(s)"
    )
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add Has customer impact and Has CSM relevance to Bug screens."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=DEFAULT_INPUT,
        help=f"Bug screen list file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--report",
        "-o",
        default=DEFAULT_REPORT,
        help=f"Report output path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually add missing fields to Jira screens (default: dry-run)",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    apply = bool(args.apply)
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    refs = parse_bug_screens(input_path)
    if not refs:
        print(f"No Bug screens found in {input_path}")
        sys.exit(1)

    grouped = group_by_screen(refs)
    mode_label = "Applying" if apply else "Dry-run"
    print(f"{mode_label}: {len(grouped)} unique Bug screen(s), {len(refs)} project mapping(s)")

    results: list[ScreenFieldResult] = []
    for screen_id, (screen_name, project_keys) in sorted(grouped.items(), key=lambda item: item[0]):
        result = process_screen(screen_id, screen_name, project_keys, apply=apply)
        results.append(result)
        spaces = ", ".join(project_keys)
        if result.errors:
            print(f"  ERROR screen {screen_id} [{spaces}]: {'; '.join(result.errors)}")
        elif result.added:
            verb = "Added" if apply else "Would add"
            print(f"  {verb} on {screen_id} [{spaces}]: {', '.join(result.added)}")
        elif result.already_present:
            print(f"  OK screen {screen_id} [{spaces}]: already complete")
        else:
            print(f"  OK screen {screen_id} [{spaces}]: no changes")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = build_report_lines(results, apply)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nReport: {report_path}")

    if any(r.errors for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
