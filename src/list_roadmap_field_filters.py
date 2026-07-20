"""List Jira filters whose JQL uses the "Relevant for P&E Roadmap" custom field.

Scans all Jira filters that are visible to the authenticated user (owned or
shared with them - the Jira REST API has no endpoint that returns literally
every filter in the instance for non-admin accounts) and reports every filter
whose JQL references the given custom field, together with its JQL.

Usage:
    py src/list_roadmap_field_filters.py
    py src/list_roadmap_field_filters.py --field-id customfield_10112
    py src/list_roadmap_field_filters.py --output reports/custom-report.md
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FIELD_ID = "customfield_10112"
DEFAULT_FIELD_LABEL = "Relevant for P&E Roadmap"


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
    return getattr(module, "_jira_get"), getattr(module, "JIRA_BASE_URL")


_jira_get, JIRA_BASE_URL = _load_jira_helpers()


@dataclass(frozen=True)
class FilterMatch:
    id: str
    name: str
    owner: str
    jql: str
    view_url: str
    favourite_count: int


def get_field_metadata(field_id: str) -> tuple[str, list[str]]:
    """Look up display name and all valid JQL clause aliases for a custom field.

    Jira custom fields can be renamed over time; existing filter JQL keeps whatever
    clause text was typed originally (e.g. the field's former name, or "cf[10112]").
    The field API's "clauseNames" list contains every alias Jira still resolves,
    so matching against it (rather than just the current display name) is required
    to reliably find filters that reference the field.
    """
    fields = _jira_get("/rest/api/3/field")
    if isinstance(fields, list):
        for field in fields:
            if field.get("id") == field_id:
                name = str(field.get("name") or field_id)
                clause_names = [str(c) for c in (field.get("clauseNames") or [])]
                return name, clause_names

    fallback_name = DEFAULT_FIELD_LABEL if field_id == DEFAULT_FIELD_ID else field_id
    return fallback_name, [field_id]


def fetch_all_filters() -> list[dict[str, Any]]:
    """Fetch every filter visible to the authenticated user, with JQL and owner."""
    filters: list[dict[str, Any]] = []
    start_at = 0
    page_size = 50

    while True:
        try:
            data = _jira_get(
                "/rest/api/3/filter/search",
                params={
                    "startAt": start_at,
                    "maxResults": page_size,
                    "expand": "jql,owner,description",
                    "orderBy": "name",
                },
            )
        except Exception:
            # Some tenants reject unknown expand values - retry with defaults.
            data = _jira_get(
                "/rest/api/3/filter/search",
                params={"startAt": start_at, "maxResults": page_size, "orderBy": "name"},
            )

        values = data.get("values") or []
        filters.extend(values)

        if data.get("isLast", True) or not values:
            break
        start_at += len(values)

    return filters


def _field_reference_pattern(field_id: str, field_name: str, clause_names: list[str]) -> re.Pattern[str]:
    """Build a case-insensitive regex matching any JQL notation for the field.

    Matches on word boundaries so that e.g. "Relevant for roadmap" does not also
    match an unrelated clause name that merely contains it as a substring.
    """
    alternatives = {field_id, field_name, *clause_names}
    alternatives.discard("")

    escaped = sorted((re.escape(a) for a in alternatives), key=len, reverse=True)
    return re.compile(r"(?<![\w\[])(" + "|".join(escaped) + r")(?![\w])", re.IGNORECASE)


def find_matching_filters(
    filters: list[dict[str, Any]], field_id: str, field_name: str, clause_names: list[str]
) -> list[FilterMatch]:
    pattern = _field_reference_pattern(field_id, field_name, clause_names)
    matches: list[FilterMatch] = []

    for f in filters:
        jql = str(f.get("jql") or "")
        if not jql or not pattern.search(jql):
            continue

        owner = (f.get("owner") or {}).get("displayName") or "–"
        filter_id = str(f.get("id") or "")
        view_url = f.get("viewUrl") or f"{JIRA_BASE_URL}/issues/?filter={filter_id}"
        matches.append(
            FilterMatch(
                id=filter_id,
                name=str(f.get("name") or "–"),
                owner=owner,
                jql=jql,
                view_url=view_url,
                favourite_count=int(f.get("favouritedCount") or 0),
            )
        )

    matches.sort(key=lambda m: m.name.lower())
    return matches


def _escape_pipe(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", " ")


def build_markdown(
    field_id: str,
    field_name: str,
    clause_names: list[str],
    matches: list[FilterMatch],
    total_scanned: int,
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines: list[str] = []

    lines.append(f"# Jira-Filter, die das Feld \"{field_name}\" ({field_id}) nutzen")
    lines.append("")
    lines.append(f"_Generiert: {generated_at}_")
    lines.append("")
    lines.append(
        f"Durchsucht: {total_scanned} Filter (alle für den aktuellen Nutzer sichtbaren Filter – "
        "eigene und geteilte). Gefunden: "
        f"{len(matches)} Filter mit Bezug auf das Feld."
    )
    lines.append("")
    lines.append(f"Gesuchte JQL-Aliasse für dieses Feld: {', '.join(f'`{c}`' for c in clause_names)}")
    lines.append("")

    if not matches:
        lines.append("_Kein Filter mit Bezug auf dieses Feld gefunden._")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Übersicht")
    lines.append("")
    lines.append("| Filter-ID | Name | Owner | Favoriten |")
    lines.append("| --- | --- | --- | --- |")
    for m in matches:
        name_link = f"[{_escape_pipe(m.name)}]({m.view_url})"
        lines.append(f"| {m.id} | {name_link} | {_escape_pipe(m.owner)} | {m.favourite_count} |")
    lines.append("")

    lines.append("## Details")
    lines.append("")
    for m in matches:
        lines.append(f"### {_escape_pipe(m.name)} ({m.id})")
        lines.append("")
        lines.append(f"- **Owner:** {m.owner}")
        lines.append(f"- **Link:** {m.view_url}")
        lines.append(f"- **Favoriten:** {m.favourite_count}")
        lines.append("")
        lines.append("```sql")
        lines.append(m.jql)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='List Jira filters whose JQL uses the "Relevant for P&E Roadmap" custom field.'
    )
    parser.add_argument(
        "--field-id",
        default=DEFAULT_FIELD_ID,
        help=f"Custom field ID to search for (default: {DEFAULT_FIELD_ID})",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output markdown file path (default: reports/filters-<field-id>-<date>.md)",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    field_id = args.field_id
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or f"reports/filters-{field_id}-{today}.md"

    print(f"Looking up field metadata for {field_id} ...")
    field_name, clause_names = get_field_metadata(field_id)
    print(f"  → \"{field_name}\" (Aliasse: {', '.join(clause_names)})")

    print("Fetching all visible Jira filters ...")
    filters = fetch_all_filters()
    print(f"  → {len(filters)} filter(s) found")

    print(f"Checking filters for references to {field_id} ...")
    matches = find_matching_filters(filters, field_id, field_name, clause_names)
    print(f"  → {len(matches)} matching filter(s)")

    markdown = build_markdown(field_id, field_name, clause_names, matches, total_scanned=len(filters))

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8", newline="\n")

    print(f"\nMarkdown written to: {output_file}")


if __name__ == "__main__":
    main()
