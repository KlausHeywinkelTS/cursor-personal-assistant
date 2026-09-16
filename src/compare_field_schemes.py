"""Compare Jira Field Schemes: field presence and required rules per issue type.

Uses the Field Schemes API (`/rest/api/3/config/fieldschemes`). Screens are out of
scope — only field association and required/optional configuration is compared.

Usage:
    py src/compare_field_schemes.py --from-mapping tmp/jira-field-schemes.txt
    py src/compare_field_schemes.py --scheme-ids 7 42 77
    py src/compare_field_schemes.py --from-mapping tmp/jira-field-schemes.txt --output-dir cache
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

DEFAULT_MAPPING = "tmp/jira-field-schemes.txt"
DEFAULT_OUTPUT_DIR = "cache"
MAPPING_LINE_RE = re.compile(r"^(\S+):\s+.+\(id=(\d+)\)\s*$")
ALL_ISSUE_TYPES = "*"


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
class WorkTypeRule:
    work_type_id: str
    is_required: bool


@dataclass
class SchemeFieldConfig:
    field_id: str
    global_required: bool
    work_type_rules: list[WorkTypeRule] = field(default_factory=list)


@dataclass(frozen=True)
class SchemeInfo:
    scheme_id: str
    name: str
    project_keys: tuple[str, ...]


def jira_get(path: str, params: Any | None = None) -> Any:
    user, token = _get_jira_auth()
    response = requests.get(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json"},
        auth=(user, token),
        params=params or {},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def fetch_paginated(path: str, extra_params: list[tuple[str, Any]] | None = None) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    start_at = 0
    max_results = 50

    while True:
        params = list(extra_params or [])
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


def parse_mapping_file(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Return unique scheme IDs (ordered) and scheme_id -> project keys."""
    if not path.is_file():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    scheme_order: list[str] = []
    projects_by_scheme: dict[str, list[str]] = defaultdict(list)

    for line in path.read_text(encoding="utf-8").splitlines():
        match = MAPPING_LINE_RE.match(line.strip())
        if not match:
            continue
        project_key, scheme_id = match.group(1), match.group(2)
        if scheme_id not in projects_by_scheme:
            scheme_order.append(scheme_id)
        projects_by_scheme[scheme_id].append(project_key)

    if not scheme_order:
        raise ValueError(f"No scheme mappings parsed from {path}")

    return scheme_order, dict(projects_by_scheme)


def fetch_scheme_name(scheme_id: str) -> str:
    data = jira_get(f"/rest/api/3/config/fieldschemes/{scheme_id}")
    if not isinstance(data, dict):
        return f"Scheme {scheme_id}"
    return str(data.get("name") or f"Scheme {scheme_id}")


def fetch_field_names() -> dict[str, str]:
    names: dict[str, str] = {}
    data = jira_get("/rest/api/3/field")
    items = data if isinstance(data, list) else fetch_paginated("/rest/api/3/field")
    for item in items:
        field_id = item.get("id") or item.get("key")
        if not field_id:
            continue
        names[str(field_id)] = str(item.get("name") or field_id)
    return names


def fetch_issue_type_names() -> dict[str, str]:
    names: dict[str, str] = {ALL_ISSUE_TYPES: "(all issue types)"}
    data = jira_get("/rest/api/3/issuetype")
    if isinstance(data, list):
        for item in data:
            issue_type_id = item.get("id")
            if issue_type_id is None:
                continue
            names[str(issue_type_id)] = str(item.get("name") or issue_type_id)
    return names


def _extract_work_type_parameters(raw: dict[str, Any]) -> list[WorkTypeRule]:
    params = raw.get("parameters") or {}
    entries = params.get("workTypeParameters") or raw.get("workTypeParameters") or []
    rules: list[WorkTypeRule] = []
    for entry in entries:
        work_type_id = entry.get("workTypeId")
        if work_type_id is None:
            continue
        rules.append(
            WorkTypeRule(
                work_type_id=str(work_type_id),
                is_required=bool(entry.get("isRequired")),
            )
        )
    return rules


def fetch_scheme_field_parameters(scheme_id: str, field_id: str) -> dict[str, Any]:
    data = jira_get(f"/rest/api/3/config/fieldschemes/{scheme_id}/fields/{field_id}/parameters")
    if not isinstance(data, dict):
        return {}
    return data


def fetch_scheme_fields(scheme_id: str) -> dict[str, SchemeFieldConfig]:
    fields: dict[str, SchemeFieldConfig] = {}

    for item in fetch_paginated(f"/rest/api/3/config/fieldschemes/{scheme_id}/fields"):
        field_id = item.get("fieldId")
        if not field_id:
            continue
        field_id = str(field_id)
        params = item.get("parameters") or {}
        global_required = bool(params.get("isRequired"))
        work_type_rules = _extract_work_type_parameters(item)

        if not work_type_rules and field_id.startswith("customfield_"):
            detail = fetch_scheme_field_parameters(scheme_id, field_id)
            work_type_rules = _extract_work_type_parameters(detail)

        fields[field_id] = SchemeFieldConfig(
            field_id=field_id,
            global_required=global_required,
            work_type_rules=work_type_rules,
        )

    return fields


def effective_required(config: SchemeFieldConfig, issue_type_id: str) -> bool:
    for rule in config.work_type_rules:
        if rule.work_type_id == issue_type_id:
            return rule.is_required
    return config.global_required


def issue_types_for_field(
    field_id: str,
    scheme_fields: dict[str, dict[str, SchemeFieldConfig]],
) -> set[str]:
    issue_types: set[str] = set()
    has_override = False

    for fields in scheme_fields.values():
        config = fields.get(field_id)
        if config is None:
            continue
        if config.work_type_rules:
            has_override = True
            issue_types.update(rule.work_type_id for rule in config.work_type_rules)

    if not has_override:
        return {ALL_ISSUE_TYPES}
    return issue_types


def build_scheme_infos(
    scheme_ids: list[str],
    projects_by_scheme: dict[str, list[str]],
) -> list[SchemeInfo]:
    infos: list[SchemeInfo] = []
    for scheme_id in scheme_ids:
        name = fetch_scheme_name(scheme_id)
        project_keys = tuple(projects_by_scheme.get(scheme_id, ()))
        infos.append(SchemeInfo(scheme_id=scheme_id, name=name, project_keys=project_keys))
    return infos


def write_presence_csv(
    path: Path,
    scheme_infos: list[SchemeInfo],
    scheme_fields: dict[str, dict[str, SchemeFieldConfig]],
    all_field_ids: list[str],
    field_names: dict[str, str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["scheme_id", "scheme_name", "project_keys", "field_id", "field_name", "present"]
        )
        for info in scheme_infos:
            fields = scheme_fields[info.scheme_id]
            projects = ",".join(info.project_keys)
            for field_id in all_field_ids:
                writer.writerow(
                    [
                        info.scheme_id,
                        info.name,
                        projects,
                        field_id,
                        field_names.get(field_id, field_id),
                        "yes" if field_id in fields else "no",
                    ]
                )


def write_required_csv(
    path: Path,
    scheme_infos: list[SchemeInfo],
    scheme_fields: dict[str, dict[str, SchemeFieldConfig]],
    field_names: dict[str, str],
    issue_type_names: dict[str, str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheme_id",
                "scheme_name",
                "field_id",
                "field_name",
                "issue_type_id",
                "issue_type_name",
                "required",
                "rule_source",
            ]
        )

        for info in scheme_infos:
            fields = scheme_fields[info.scheme_id]
            for field_id, config in sorted(fields.items()):
                if config.work_type_rules:
                    for rule in config.work_type_rules:
                        writer.writerow(
                            [
                                info.scheme_id,
                                info.name,
                                field_id,
                                field_names.get(field_id, field_id),
                                rule.work_type_id,
                                issue_type_names.get(rule.work_type_id, rule.work_type_id),
                                "true" if rule.is_required else "false",
                                "work_type",
                            ]
                        )
                    writer.writerow(
                        [
                            info.scheme_id,
                            info.name,
                            field_id,
                            field_names.get(field_id, field_id),
                            ALL_ISSUE_TYPES,
                            issue_type_names[ALL_ISSUE_TYPES],
                            "true" if config.global_required else "false",
                            "global_default",
                        ]
                    )
                else:
                    writer.writerow(
                        [
                            info.scheme_id,
                            info.name,
                            field_id,
                            field_names.get(field_id, field_id),
                            ALL_ISSUE_TYPES,
                            issue_type_names[ALL_ISSUE_TYPES],
                            "true" if config.global_required else "false",
                            "global",
                        ]
                    )


def build_conflicts_markdown(
    scheme_infos: list[SchemeInfo],
    scheme_fields: dict[str, dict[str, SchemeFieldConfig]],
    all_field_ids: list[str],
    field_names: dict[str, str],
    issue_type_names: dict[str, str],
) -> str:
    scheme_ids = [info.scheme_id for info in scheme_infos]
    lines: list[str] = [
        "# Field Scheme Konflikte",
        "",
        "Vergleich auf Field-Scheme-Ebene (Screens ausgeschlossen).",
        "",
        "## Verglichene Schemes",
        "",
        "| Scheme ID | Name | Spaces |",
        "| --- | --- | --- |",
    ]

    for info in scheme_infos:
        spaces = ", ".join(info.project_keys) if info.project_keys else "–"
        lines.append(f"| {info.scheme_id} | {info.name} | {spaces} |")

    lines.extend(["", "## Fehlende Felder (Präsenz)", ""])

    presence_rows: list[tuple[int, str, list[str], list[str]]] = []
    for field_id in all_field_ids:
        present_in = [sid for sid in scheme_ids if field_id in scheme_fields[sid]]
        missing_in = [sid for sid in scheme_ids if field_id not in scheme_fields[sid]]
        if not missing_in:
            continue
        presence_rows.append((len(present_in), field_id, present_in, missing_in))

    presence_rows.sort(key=lambda item: (item[0], item[1]))
    if not presence_rows:
        lines.append("Keine Präsenz-Abweichungen — alle Felder in allen Schemes vorhanden.")
    else:
        lines.extend(
            [
                "Felder, die nicht in allen Schemes vorkommen (Union-Ziel: alle aufnehmen).",
                "",
                "| Feld | Name | In Schemes | Fehlt in |",
                "| --- | --- | --- | --- |",
            ]
        )
        for count, field_id, present_in, missing_in in presence_rows:
            present_label = ", ".join(present_in)
            missing_label = ", ".join(missing_in)
            lines.append(
                f"| `{field_id}` | {field_names.get(field_id, field_id)} "
                f"| {count}/{len(scheme_ids)} ({present_label}) | {missing_label} |"
            )

    lines.extend(["", "## Required-Konflikte", ""])
    conflict_rows: list[tuple[str, str, str, str, str]] = []

    for field_id in all_field_ids:
        schemes_with_field = [sid for sid in scheme_ids if field_id in scheme_fields[sid]]
        if len(schemes_with_field) < 2:
            continue

        for issue_type_id in sorted(
            issue_types_for_field(field_id, scheme_fields),
            key=lambda value: (value != ALL_ISSUE_TYPES, value),
        ):
            required_by_scheme: dict[str, bool] = {}
            for scheme_id in schemes_with_field:
                config = scheme_fields[scheme_id][field_id]
                if issue_type_id == ALL_ISSUE_TYPES:
                    required_by_scheme[scheme_id] = config.global_required
                else:
                    required_by_scheme[scheme_id] = effective_required(config, issue_type_id)

            if len(set(required_by_scheme.values())) <= 1:
                continue

            details = ", ".join(
                f"{scheme_id}={'required' if value else 'optional'}"
                for scheme_id, value in sorted(required_by_scheme.items())
            )
            conflict_rows.append(
                (
                    field_id,
                    issue_type_id,
                    field_names.get(field_id, field_id),
                    issue_type_names.get(issue_type_id, issue_type_id),
                    details,
                )
            )

    if not conflict_rows:
        lines.append("Keine Required-Konflikte zwischen den verglichenen Schemes.")
    else:
        lines.extend(
            [
                "Gleiches Feld, gleicher Issue Type — unterschiedlicher Required-Status.",
                "",
                "| Feld | Name | Issue Type | Status pro Scheme |",
                "| --- | --- | --- | --- |",
            ]
        )
        for field_id, issue_type_id, field_name, issue_type_name, details in conflict_rows:
            lines.append(
                f"| `{field_id}` | {field_name} | {issue_type_name} (`{issue_type_id}`) | {details} |"
            )

    lines.extend(
        [
            "",
            "## Safe-Target-Regeln",
            "",
            "- **Präsenz:** Union aller Felder über alle Schemes — nichts entfernen.",
            "- **Required:** Konservativ = nur required, wenn **alle** Schemes das Feld "
            "für den Issue Type required haben; sonst optional lassen oder explizit entscheiden.",
            "",
            f"- Felder gesamt (Union): **{len(all_field_ids)}**",
            f"- Präsenz-Abweichungen: **{len(presence_rows)}**",
            f"- Required-Konflikte: **{len(conflict_rows)}**",
        ]
    )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Jira Field Schemes: field presence and required rules. "
            "Screens are excluded."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-mapping",
        metavar="PATH",
        help=f"Parse scheme IDs from mapping file (e.g. {DEFAULT_MAPPING})",
    )
    source.add_argument(
        "--scheme-ids",
        nargs="+",
        metavar="ID",
        help="Explicit field scheme IDs to compare",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for CSV/MD reports (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()

    if args.from_mapping:
        scheme_ids, projects_by_scheme = parse_mapping_file(Path(args.from_mapping))
    else:
        scheme_ids = [str(scheme_id) for scheme_id in args.scheme_ids]
        projects_by_scheme = {}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Comparing {len(scheme_ids)} field scheme(s): {', '.join(scheme_ids)}")

    print("Loading field and issue type names ...")
    field_names = fetch_field_names()
    issue_type_names = fetch_issue_type_names()

    scheme_infos = build_scheme_infos(scheme_ids, projects_by_scheme)
    scheme_fields: dict[str, dict[str, SchemeFieldConfig]] = {}

    for info in scheme_infos:
        print(f"Loading scheme {info.scheme_id} ({info.name}) ...")
        scheme_fields[info.scheme_id] = fetch_scheme_fields(info.scheme_id)
        print(f"  {len(scheme_fields[info.scheme_id])} fields")

    all_field_ids = sorted(
        {field_id for fields in scheme_fields.values() for field_id in fields},
        key=str.casefold,
    )

    presence_path = output_dir / "field-scheme-presence.csv"
    required_path = output_dir / "field-scheme-required.csv"
    conflicts_path = output_dir / "field-scheme-conflicts.md"

    write_presence_csv(presence_path, scheme_infos, scheme_fields, all_field_ids, field_names)
    write_required_csv(required_path, scheme_infos, scheme_fields, field_names, issue_type_names)
    conflicts_path.write_text(
        build_conflicts_markdown(
            scheme_infos,
            scheme_fields,
            all_field_ids,
            field_names,
            issue_type_names,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"Written: {presence_path}")
    print(f"Written: {required_path}")
    print(f"Written: {conflicts_path}")
    print(f"Union: {len(all_field_ids)} fields across {len(scheme_ids)} schemes")


if __name__ == "__main__":
    main()
