"""Apply unified field-scheme changes to a target Jira Field Scheme.

Adds missing fields, aligns issue-type (work type) associations, and sets required
rules using a union policy: a field is required if it is required in any source scheme.

Usage:
    py src/apply_unified_field_scheme.py --dry-run --target-name "Product Development Standard Field Configuration Scheme"
    py src/apply_unified_field_scheme.py --apply --target-scheme-id 143 --from-mapping tmp/jira-field-schemes.txt
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

DEFAULT_MAPPING = "tmp/jira-field-schemes.txt"
DEFAULT_TARGET_NAME = "Product Development Standard Field Configuration Scheme"
MAPPING_LINE_RE = re.compile(r"^(\S+):\s+.+\(id=(\d+)\)\s*$")


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
    raise ModuleNotFoundError("Could not find read_jira_issue.py")


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


@dataclass
class FieldConfig:
    global_required: bool = False
    renderer_type: str | None = None
    description: str | None = None
    work_types: set[str] = field(default_factory=set)
    work_type_required: dict[str, bool] = field(default_factory=dict)


@dataclass
class PlannedChange:
    add_fields: list[tuple[str, FieldConfig]]
    association_updates: list[tuple[str, FieldConfig]]
    required_updates: list[tuple[str, FieldConfig]]


def jira_request(method: str, path: str, *, params: Any | None = None, json_body: Any | None = None) -> requests.Response:
    user, token = _get_jira_auth()
    response = requests.request(
        method,
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        auth=(user, token),
        params=params or {},
        json=json_body,
        timeout=120,
    )
    return response


def jira_get(path: str, params: Any | None = None) -> Any:
    response = jira_request("GET", path, params=params)
    response.raise_for_status()
    return response.json()


def parse_mapping_file(path: Path) -> list[str]:
    scheme_order: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MAPPING_LINE_RE.match(line.strip())
        if not match:
            continue
        scheme_id = match.group(2)
        if scheme_id not in seen:
            scheme_order.append(scheme_id)
            seen.add(scheme_id)
    if not scheme_order:
        raise ValueError(f"No scheme mappings parsed from {path}")
    return scheme_order


def find_scheme_id_by_name(name: str) -> str:
    start_at = 0
    while True:
        data = jira_get("/rest/api/3/config/fieldschemes", {"startAt": start_at, "maxResults": 50})
        for item in data.get("values") or []:
            if (item.get("name") or "").strip() == name.strip():
                return str(item["id"])
        if data.get("isLast", True):
            break
        start_at += len(data.get("values") or [])
    raise RuntimeError(f"Field scheme not found: {name}")


def _parse_field_item(item: dict[str, Any]) -> FieldConfig:
    params = item.get("parameters") or {}
    work_type_params = params.get("workTypeParameters") or item.get("workTypeParameters") or []
    cfg = FieldConfig(
        global_required=bool(params.get("isRequired")),
        renderer_type=params.get("rendererType"),
        description=params.get("description"),
        work_type_required={
            str(entry["workTypeId"]): bool(entry.get("isRequired"))
            for entry in work_type_params
            if entry.get("workTypeId") is not None
        },
    )
    restricted = item.get("workTypeIds") or item.get("restrictedToWorkTypes")
    if restricted:
        cfg.work_types = {str(value) for value in restricted}
    elif cfg.work_type_required:
        cfg.work_types = set(cfg.work_type_required.keys())
    return cfg


def fetch_scheme_fields(scheme_id: str, detail_for: set[str] | None = None) -> dict[str, FieldConfig]:
    fields: dict[str, FieldConfig] = {}
    start_at = 0
    while True:
        data = jira_get(
            f"/rest/api/3/config/fieldschemes/{scheme_id}/fields",
            {"startAt": start_at, "maxResults": 50},
        )
        for item in data.get("values") or []:
            field_id = str(item.get("fieldId") or "")
            if not field_id:
                continue
            cfg = _parse_field_item(item)
            if detail_for and field_id in detail_for and not cfg.work_type_required:
                detail = jira_get(f"/rest/api/3/config/fieldschemes/{scheme_id}/fields/{field_id}/parameters")
                detail_params = detail.get("parameters") or {}
                detail_wtp = detail.get("workTypeParameters") or detail_params.get("workTypeParameters") or []
                for entry in detail_wtp:
                    work_type_id = str(entry["workTypeId"])
                    cfg.work_types.add(work_type_id)
                    cfg.work_type_required[work_type_id] = bool(entry.get("isRequired"))
                if detail_params.get("rendererType"):
                    cfg.renderer_type = detail_params.get("rendererType")
                if detail_params.get("description") is not None:
                    cfg.description = detail_params.get("description")
                cfg.global_required = bool(detail_params.get("isRequired"))
            fields[field_id] = cfg
        if data.get("isLast", True):
            break
        start_at += len(data.get("values") or [])
    return fields


def effective_required(cfg: FieldConfig, work_type_id: str | None = None) -> bool:
    if work_type_id and work_type_id in cfg.work_type_required:
        return cfg.work_type_required[work_type_id]
    return cfg.global_required


def merge_union(configs: list[FieldConfig]) -> FieldConfig:
    merged = FieldConfig()
    work_types: set[str] = set()
    required_by_type: dict[str, bool] = {}

    for cfg in configs:
        work_types |= cfg.work_types
        if cfg.global_required:
            merged.global_required = True
        merged.renderer_type = merged.renderer_type or cfg.renderer_type
        merged.description = merged.description or cfg.description
        for work_type_id, required in cfg.work_type_required.items():
            if required:
                required_by_type[work_type_id] = True
            elif work_type_id not in required_by_type:
                required_by_type[work_type_id] = False

    if work_types:
        merged.work_types = work_types
        merged.work_type_required = required_by_type
    else:
        merged.work_type_required = required_by_type
    return merged


def build_unified_configs(
    source_scheme_ids: list[str],
    target_scheme_id: str,
) -> dict[str, FieldConfig]:
    target_fields = fetch_scheme_fields(target_scheme_id)
    all_field_ids = set(target_fields)
    source_fields_by_scheme: dict[str, dict[str, FieldConfig]] = {}

    for scheme_id in source_scheme_ids:
        source_fields_by_scheme[scheme_id] = fetch_scheme_fields(scheme_id)
        all_field_ids.update(source_fields_by_scheme[scheme_id])

    detail_candidates = set(all_field_ids)
    if detail_candidates:
        for scheme_id in source_scheme_ids:
            source_fields_by_scheme[scheme_id] = fetch_scheme_fields(scheme_id, detail_for=detail_candidates)

    unified: dict[str, FieldConfig] = {}
    for field_id in all_field_ids:
        configs = []
        if field_id in target_fields:
            configs.append(target_fields[field_id])
        for scheme_id in source_scheme_ids:
            cfg = source_fields_by_scheme[scheme_id].get(field_id)
            if cfg is not None:
                configs.append(cfg)
        if configs:
            unified[field_id] = merge_union(configs)
    return unified


def plan_changes(
    target_fields: dict[str, FieldConfig],
    unified: dict[str, FieldConfig],
) -> PlannedChange:
    add_fields: list[tuple[str, FieldConfig]] = []
    association_updates: list[tuple[str, FieldConfig]] = []
    required_updates: list[tuple[str, FieldConfig]] = []

    for field_id, desired in sorted(unified.items()):
        current = target_fields.get(field_id)
        if current is None:
            add_fields.append((field_id, desired))
            continue

        if desired.work_types and desired.work_types != current.work_types:
            association_updates.append((field_id, desired))

        needs_required_update = False
        updated = FieldConfig(
            global_required=current.global_required,
            renderer_type=current.renderer_type,
            description=current.description,
            work_types=set(current.work_types),
            work_type_required=dict(current.work_type_required),
        )

        if desired.global_required and not current.global_required:
            updated.global_required = True
            needs_required_update = True

        work_types_to_check = desired.work_types or current.work_types or set(desired.work_type_required)
        for work_type_id in work_types_to_check:
            desired_required = effective_required(desired, work_type_id or None)
            current_required = effective_required(current, work_type_id or None)
            if desired_required and not current_required:
                updated.work_type_required[work_type_id] = True
                needs_required_update = True

        if needs_required_update:
            required_updates.append((field_id, updated))

    return PlannedChange(
        add_fields=add_fields,
        association_updates=association_updates,
        required_updates=required_updates,
    )


def _work_type_ints(cfg: FieldConfig) -> list[int]:
    return sorted(int(value) for value in cfg.work_types)


def apply_association(field_id: str, scheme_id: int, cfg: FieldConfig) -> dict[str, Any]:
    item: dict[str, Any] = {"schemeIds": [scheme_id]}
    if cfg.work_types:
        item["restrictedToWorkTypes"] = _work_type_ints(cfg)
    body = {field_id: [item]}
    response = jira_request("PUT", "/rest/api/3/config/fieldschemes/fields", json_body=body)
    return {
        "action": "association",
        "fieldId": field_id,
        "status": response.status_code,
        "body": response.json() if response.content else {},
    }


def apply_required(field_id: str, scheme_id: int, cfg: FieldConfig, current: FieldConfig) -> dict[str, Any]:
    item: dict[str, Any] = {"schemeIds": [scheme_id]}
    work_type_parameters: list[dict[str, Any]] = []

    for work_type_id, required in sorted(cfg.work_type_required.items(), key=lambda pair: int(pair[0])):
        if not required:
            continue
        if current.work_type_required.get(work_type_id) is True:
            continue
        work_type_parameters.append({"workTypeId": int(work_type_id), "isRequired": True})

    if cfg.global_required and not current.global_required:
        params: dict[str, Any] = {"isRequired": True}
        if current.renderer_type:
            params["rendererType"] = current.renderer_type
        item["parameters"] = params
    elif work_type_parameters:
        item["workTypeParameters"] = work_type_parameters
    else:
        return {"action": "required", "fieldId": field_id, "status": "skipped"}

    body = {field_id: [item]}
    response = jira_request("PUT", "/rest/api/3/config/fieldschemes/fields/parameters", json_body=body)
    payload = response.json() if response.content else {}
    return {
        "action": "required",
        "fieldId": field_id,
        "status": response.status_code,
        "body": payload,
    }


def apply_plan(
    target_scheme_id: str,
    target_fields: dict[str, FieldConfig],
    plan: PlannedChange,
    *,
    dry_run: bool,
) -> list[dict[str, Any]]:
    scheme_id = int(target_scheme_id)
    results: list[dict[str, Any]] = []

    for field_id, cfg in plan.add_fields:
        entry = {"action": "add", "fieldId": field_id, "workTypes": sorted(cfg.work_types)}
        if dry_run:
            results.append(entry | {"status": "dry-run"})
            continue
        response_entry = apply_association(field_id, scheme_id, cfg)
        results.append(response_entry)
        if response_entry["status"] >= 400:
            continue
        current = target_fields.get(field_id, FieldConfig())
        req_entry = apply_required(field_id, scheme_id, cfg, current)
        if req_entry.get("status") != "skipped":
            results.append(req_entry)
        time.sleep(0.15)

    for field_id, cfg in plan.association_updates:
        if dry_run:
            results.append(
                {
                    "action": "association",
                    "fieldId": field_id,
                    "workTypes": sorted(cfg.work_types),
                    "status": "dry-run",
                }
            )
            continue
        results.append(apply_association(field_id, scheme_id, cfg))
        time.sleep(0.15)

    for field_id, cfg in plan.required_updates:
        current = target_fields.get(field_id, FieldConfig())
        if dry_run:
            results.append({"action": "required", "fieldId": field_id, "status": "dry-run"})
            continue
        results.append(apply_required(field_id, scheme_id, cfg, current))
        time.sleep(0.15)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply unified field-scheme changes to a target scheme.")
    parser.add_argument("--from-mapping", default=DEFAULT_MAPPING, help="Mapping file with source scheme IDs")
    parser.add_argument("--target-scheme-id", help="Target field scheme ID")
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME, help="Target field scheme name")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Only print planned changes")
    mode.add_argument("--apply", action="store_true", help="Apply planned changes")
    parser.add_argument(
        "--report",
        default="cache/field-scheme-apply-report.json",
        help="Write JSON report of planned/applied changes",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    if not args.dry_run and not args.apply:
        raise SystemExit("Specify --dry-run or --apply")

    source_scheme_ids = parse_mapping_file(Path(args.from_mapping))
    target_scheme_id = args.target_scheme_id or find_scheme_id_by_name(args.target_name)

    print(f"Target scheme: {target_scheme_id}")
    print(f"Source schemes: {', '.join(source_scheme_ids)}")
    print("Loading field configurations ...")

    target_fields = fetch_scheme_fields(target_scheme_id, detail_for=set())
    target_fields = fetch_scheme_fields(target_scheme_id)
    unified = build_unified_configs(source_scheme_ids, target_scheme_id)
    plan = plan_changes(target_fields, unified)

    print(f"Add fields: {len(plan.add_fields)}")
    print(f"Association updates: {len(plan.association_updates)}")
    print(f"Required updates: {len(plan.required_updates)}")

    results = apply_plan(target_scheme_id, target_fields, plan, dry_run=args.dry_run)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "targetSchemeId": target_scheme_id,
        "sourceSchemeIds": source_scheme_ids,
        "dryRun": args.dry_run,
        "counts": {
            "add": len(plan.add_fields),
            "associationUpdates": len(plan.association_updates),
            "requiredUpdates": len(plan.required_updates),
        },
        "addFields": [field_id for field_id, _ in plan.add_fields],
        "associationUpdates": [
            {"fieldId": field_id, "workTypes": sorted(cfg.work_types)} for field_id, cfg in plan.association_updates
        ],
        "requiredUpdates": [field_id for field_id, _ in plan.required_updates],
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Report written: {report_path}")

    failures = [item for item in results if isinstance(item.get("status"), int) and item["status"] >= 400]
    if failures:
        print(f"Completed with {len(failures)} failure(s).")
        for item in failures[:10]:
            print(json.dumps(item, ensure_ascii=False))
        raise SystemExit(1)

    if args.apply:
        verify_fields = fetch_scheme_fields(target_scheme_id)
        print(f"Verified field count in target scheme: {len(verify_fields)}")


if __name__ == "__main__":
    main()
