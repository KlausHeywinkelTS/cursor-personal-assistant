"""List Jira screens that contain one or more custom fields by display name.

Resolves field IDs from Jira by Klarnamen and scans all screens (all tabs).

Usage:
    py src/list_screens_with_field.py
    py src/list_screens_with_field.py --field "Has customer impact"
    py src/list_screens_with_field.py --field "Has customer impact" --field "Has CSM relevance"
    py src/list_screens_with_field.py --output tmp/jira-screens-with-field.txt
    py src/list_screens_with_field.py --field "Remind date" --require-all
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

DEFAULT_FIELD_NAMES = (
    "Has customer impact",
    "Has CSM relevance",
)


def _candidate_jira_helper_dirs() -> list[Path]:
    candidates: list[Path] = [Path(__file__).resolve().parent]

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
class ScreenInfo:
    screen_id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class TabFieldHit:
    tab_id: str
    tab_name: str
    field_ids: set[str]


@dataclass
class ScreenMatch:
    screen: ScreenInfo
    hits: list[TabFieldHit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def matched_field_ids(self) -> set[str]:
        matched: set[str] = set()
        for hit in self.hits:
            matched.update(hit.field_ids)
        return matched


@dataclass
class ScanSummary:
    matches: list[ScreenMatch]
    skipped_screens: list[tuple[ScreenInfo, str]] = field(default_factory=list)


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


def fetch_paginated(path: str, extra_params: list[tuple[str, Any]] | None = None) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    start_at = 0
    max_results = 50
    extra_params = extra_params or []

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


def resolve_custom_fields(field_names: tuple[str, ...]) -> dict[str, str]:
    """Return mapping field_id -> display name for the requested custom fields."""
    fields = jira_get("/rest/api/3/field")
    if not isinstance(fields, list):
        raise RuntimeError("Unexpected response from /rest/api/3/field")

    targets = {name.casefold(): name for name in field_names}
    resolved: dict[str, str] = {}

    for item in fields:
        name = str(item.get("name") or "")
        canonical = targets.get(name.casefold())
        if canonical is None:
            continue
        field_id = str(item.get("id") or "")
        if not field_id:
            continue
        resolved[field_id] = canonical

    found_names = {name.casefold() for name in resolved.values()}
    missing = [name for name in field_names if name.casefold() not in found_names]
    if missing:
        raise ValueError("Field(s) not found in Jira: " + ", ".join(f'"{name}"' for name in missing))

    return resolved


def fetch_all_screens() -> list[ScreenInfo]:
    screens: list[ScreenInfo] = []
    for item in fetch_paginated("/rest/api/3/screens"):
        screen_id = item.get("id")
        if screen_id is None:
            continue
        screens.append(
            ScreenInfo(
                screen_id=str(screen_id),
                name=str(item.get("name") or f"Screen {screen_id}"),
                description=str(item.get("description") or ""),
            )
        )
    return screens


def _http_error_message(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else "?"
    detail = ""
    if exc.response is not None:
        detail = (exc.response.text or "").strip().replace("\n", " ")
        if len(detail) > 240:
            detail = detail[:237] + "..."
    return f"HTTP {status}" + (f": {detail}" if detail else "")


def fetch_screen_tabs(screen_id: str) -> list[tuple[str, str]]:
    tabs = jira_get(f"/rest/api/3/screens/{screen_id}/tabs")
    if not isinstance(tabs, list):
        return []

    result: list[tuple[str, str]] = []
    for tab in tabs:
        tab_id = tab.get("id")
        if tab_id is None:
            continue
        result.append((str(tab_id), str(tab.get("name") or "Tab")))
    return result


def fetch_tab_field_ids(screen_id: str, tab_id: str) -> set[str]:
    fields = jira_get(f"/rest/api/3/screens/{screen_id}/tabs/{tab_id}/fields")
    if not isinstance(fields, list):
        return set()
    return {str(item.get("id")) for item in fields if item.get("id")}


def scan_screens(
    screens: list[ScreenInfo],
    target_fields: dict[str, str],
    require_all: bool,
) -> ScanSummary:
    target_ids = set(target_fields)
    matches: list[ScreenMatch] = []
    skipped: list[tuple[ScreenInfo, str]] = []

    for index, screen in enumerate(screens, start=1):
        print(
            f"Scanning screen {index}/{len(screens)}: {screen.screen_id} ({screen.name})",
            file=sys.stderr,
        )

        hits: list[TabFieldHit] = []
        matched_ids: set[str] = set()
        warnings: list[str] = []

        try:
            tabs = fetch_screen_tabs(screen.screen_id)
        except requests.HTTPError as exc:
            message = _http_error_message(exc)
            print(
                f"  WARNING: could not read tabs for screen {screen.screen_id}: {message}",
                file=sys.stderr,
            )
            skipped.append((screen, message))
            continue

        for tab_id, tab_name in tabs:
            try:
                present = fetch_tab_field_ids(screen.screen_id, tab_id)
            except requests.HTTPError as exc:
                message = _http_error_message(exc)
                warnings.append(f"Tab {tab_name} (id={tab_id}): {message}")
                print(
                    f"  WARNING: could not read fields for tab {tab_id}: {message}",
                    file=sys.stderr,
                )
                continue

            tab_hits = present & target_ids
            if not tab_hits:
                continue
            hits.append(TabFieldHit(tab_id=tab_id, tab_name=tab_name, field_ids=tab_hits))
            matched_ids.update(tab_hits)

        if require_all:
            if matched_ids == target_ids:
                matches.append(ScreenMatch(screen=screen, hits=hits, warnings=warnings))
        elif matched_ids:
            matches.append(ScreenMatch(screen=screen, hits=hits, warnings=warnings))

    return ScanSummary(matches=matches, skipped_screens=skipped)


def build_report(
    summary: ScanSummary,
    target_fields: dict[str, str],
    total_screens: int,
    require_all: bool,
) -> str:
    matches = summary.matches
    mode = "all target fields" if require_all else "at least one target field"
    lines = [
        "Jira screens containing target field(s)",
        f"Match mode: {mode}",
        f"Target fields: {', '.join(f'{name} ({field_id})' for field_id, name in sorted(target_fields.items(), key=lambda item: item[1]))}",
        f"Matched screens: {len(matches)} of {total_screens}",
    ]
    if summary.skipped_screens:
        lines.append(f"Skipped screens due to API errors: {len(summary.skipped_screens)}")
    lines.append("")

    if not matches and not summary.skipped_screens:
        lines.append("No matching screens found.")
        return "\n".join(lines)

    for match in sorted(matches, key=lambda item: (item.screen.name.casefold(), item.screen.screen_id)):
        screen = match.screen
        field_names = ", ".join(
            sorted(target_fields[field_id] for field_id in match.matched_field_ids)
        )
        lines.append(f"{screen.name} (id={screen.screen_id})")
        lines.append(f"  Fields: {field_names}")
        for hit in match.hits:
            hit_names = ", ".join(
                sorted(target_fields[field_id] for field_id in hit.field_ids)
            )
            lines.append(f"  Tab: {hit.tab_name} (id={hit.tab_id}) -> {hit_names}")
        for warning in match.warnings:
            lines.append(f"  Warning: {warning}")
        if screen.description:
            lines.append(f"  Description: {screen.description}")
        lines.append("")

    if summary.skipped_screens:
        lines.append("## Skipped screens")
        lines.append("")
        for screen, reason in sorted(
            summary.skipped_screens,
            key=lambda item: (item[0].name.casefold(), item[0].screen_id),
        ):
            lines.append(f"{screen.name} (id={screen.screen_id}): {reason}")
        lines.append("")

    return "\n".join(lines).rstrip()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="List Jira screens that contain one or more fields by display name."
    )
    parser.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="NAME",
        help=(
            "Display name of a field to search for (repeatable). "
            f"Default without --field: {', '.join(DEFAULT_FIELD_NAMES)}"
        ),
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the text report",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Only list screens that contain all specified target fields (default: any)",
    )
    args = parser.parse_args()

    field_names = tuple(args.fields) if args.fields else DEFAULT_FIELD_NAMES

    try:
        target_fields = resolve_custom_fields(field_names)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"Jira API error while resolving fields: HTTP {status}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(
        "Target fields: "
        + ", ".join(f'"{name}" ({field_id})' for field_id, name in target_fields.items()),
        file=sys.stderr,
    )

    try:
        screens = fetch_all_screens()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 403:
            print(
                "HTTP 403: Administer Jira permission required to list screens.",
                file=sys.stderr,
            )
        else:
            print(f"Jira API error while listing screens: HTTP {status}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Found {len(screens)} screen(s) in Jira.", file=sys.stderr)

    try:
        summary = scan_screens(screens, target_fields, require_all=args.require_all)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 403:
            print(
                "HTTP 403: Administer Jira permission required to read screen tabs/fields.",
                file=sys.stderr,
            )
        else:
            print(f"Jira API error while scanning screens: HTTP {status}", file=sys.stderr)
        raise SystemExit(1) from exc

    report = build_report(
        summary,
        target_fields,
        total_screens=len(screens),
        require_all=args.require_all,
    )
    print(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8", newline="\n")
        print(f"Report written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
