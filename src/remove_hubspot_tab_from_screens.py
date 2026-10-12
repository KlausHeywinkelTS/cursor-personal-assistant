"""Remove the "HubSpot" tab from all Jira screens.

Background (PROPS-1319): the Jira<->HubSpot integration added a tab "HubSpot" (one
field, "HubSpot ticket count") as last tab to every screen. The tab is removed from
ALL screens, including the PO space (changed from the original ticket text).
Screens that must keep the tab can be listed with --keep-screen-id.

Safety checks per screen before a tab is deleted:
  - Tab name matches exactly (case-insensitive) and the screen has other tabs left.
  - The tab only contains HubSpot fields (--field-prefix); otherwise it is skipped.

Usage:
    py src/remove_hubspot_tab_from_screens.py                      # dry-run, all screens
    py src/remove_hubspot_tab_from_screens.py --screen-id 1 --screen-id 10097 --apply   # pilot
    py src/remove_hubspot_tab_from_screens.py --apply
    py src/remove_hubspot_tab_from_screens.py --apply --keep-screen-id 10271

On --apply a JSON backup (screen, tab id/name/position, field ids) is written first,
so removed tabs can be rebuilt by hand if needed. Requires "Administer Jira".
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

import list_screens_with_field as jira

DEFAULT_TAB_NAME = "HubSpot"
DEFAULT_FIELD_PREFIX = "HubSpot"
DEFAULT_REPORT = "tmp/hubspot-tab-removal-report.txt"
DEFAULT_BACKUP = "tmp/hubspot-tab-removal-backup.json"

MAX_RETRIES = 3


@dataclass
class ScreenPlan:
    screen_id: str
    screen_name: str
    tab_id: str = ""
    tab_name: str = ""
    tab_position: int = -1
    tab_count: int = 0
    field_ids: list[str] = field(default_factory=list)
    action: str = ""  # remove | keep | skip
    reason: str = ""
    outcome: str = ""  # dry-run | removed | already-gone | verify-failed | error: ...


def jira_delete(path: str) -> int:
    """DELETE with a small retry for HTTP 429. Returns the final status code."""
    user, token = jira._get_jira_auth()
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.delete(
            f"{jira.JIRA_BASE_URL}{path}",
            headers={"Accept": "application/json"},
            auth=(user, token),
            timeout=30,
        )
        if response.status_code == 429 and attempt < MAX_RETRIES:
            time.sleep(int(response.headers.get("Retry-After", "5")))
            continue
        if response.status_code == 404:
            return 404
        response.raise_for_status()
        return response.status_code
    return 429


def inspect_screen(
    screen: jira.ScreenInfo,
    tab_name: str,
    field_names: dict[str, str],
) -> ScreenPlan | None:
    """Return a plan for screens that carry the tab, None otherwise."""
    tabs = jira.fetch_screen_tabs(screen.screen_id)
    for position, (tab_id, name) in enumerate(tabs):
        if name.casefold() != tab_name.casefold():
            continue
        fields = jira.jira_get(f"/rest/api/3/screens/{screen.screen_id}/tabs/{tab_id}/fields")
        for item in fields:
            field_names[str(item.get("id"))] = str(item.get("name") or "")
        field_ids = sorted(str(item.get("id")) for item in fields if item.get("id"))
        return ScreenPlan(
            screen_id=screen.screen_id,
            screen_name=screen.name,
            tab_id=tab_id,
            tab_name=name,
            tab_position=position,
            tab_count=len(tabs),
            field_ids=field_ids,
        )
    return None


def decide(
    plan: ScreenPlan,
    keep_screen_ids: set[str],
    field_names: dict[str, str],
    field_prefix: str,
) -> None:
    if plan.screen_id in keep_screen_ids:
        plan.action, plan.reason = "keep", "explicit --keep-screen-id"
        return
    if plan.tab_count < 2:
        plan.action, plan.reason = "skip", "tab is the only tab on the screen"
        return
    foreign = [
        f"{field_id} ({field_names.get(field_id, '?')})"
        for field_id in plan.field_ids
        if not field_names.get(field_id, "").casefold().startswith(field_prefix.casefold())
    ]
    if foreign:
        plan.action, plan.reason = "skip", "tab contains non-HubSpot fields: " + ", ".join(foreign)
        return
    plan.action, plan.reason = "remove", ""


def apply_removal(plan: ScreenPlan) -> None:
    try:
        status = jira_delete(f"/rest/api/3/screens/{plan.screen_id}/tabs/{plan.tab_id}")
    except requests.HTTPError as exc:
        plan.outcome = "error: " + jira._http_error_message(exc)
        return
    if status == 404:
        plan.outcome = "already-gone"
        return
    remaining = [name for _, name in jira.fetch_screen_tabs(plan.screen_id)]
    still_there = any(name.casefold() == plan.tab_name.casefold() for name in remaining)
    plan.outcome = "verify-failed" if still_there else "removed"


def build_report(
    plans: list[ScreenPlan],
    skipped_reads: list[tuple[jira.ScreenInfo, str]],
    total_screens: int,
    apply: bool,
) -> str:
    by_action: dict[str, list[ScreenPlan]] = {"remove": [], "keep": [], "skip": []}
    for plan in plans:
        by_action[plan.action].append(plan)

    lines = [
        "Remove tab from Jira screens",
        f"Mode: {'APPLY' if apply else 'DRY-RUN (no changes)'}",
        f"Screens in Jira: {total_screens}; with tab: {len(plans)}",
        f"To remove: {len(by_action['remove'])}; kept: {len(by_action['keep'])}; "
        f"skipped by safety check: {len(by_action['skip'])}; "
        f"unreadable screens: {len(skipped_reads)}",
        "",
    ]

    if apply:
        outcomes: dict[str, int] = {}
        for plan in by_action["remove"]:
            key = plan.outcome.split(":")[0] or "-"
            outcomes[key] = outcomes.get(key, 0) + 1
        lines.append("Outcomes: " + ", ".join(f"{key}={count}" for key, count in sorted(outcomes.items())))
        lines.append("")

    def section(title: str, items: list[ScreenPlan], with_outcome: bool = False) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for plan in sorted(items, key=lambda p: (p.screen_name.casefold(), p.screen_id)):
            suffix = f" -> {plan.outcome}" if with_outcome and plan.outcome else ""
            reason = f" [{plan.reason}]" if plan.reason else ""
            lines.append(
                f"{plan.screen_name} (id={plan.screen_id}, tab={plan.tab_id}){reason}{suffix}"
            )
        lines.append("")

    section("Kept (tab stays)", by_action["keep"])
    section("Skipped (needs a human)", by_action["skip"])
    section("Remove", by_action["remove"], with_outcome=apply)

    if skipped_reads:
        lines.append("## Unreadable screens (HTTP errors, not touched)")
        lines.append("")
        for screen, reason in sorted(skipped_reads, key=lambda item: item[0].screen_id):
            lines.append(f"{screen.name} (id={screen.screen_id}): {reason}")
        lines.append("")

    return "\n".join(lines).rstrip()


def write_text(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Remove the HubSpot tab from all Jira screens. Dry-run by default."
    )
    parser.add_argument("--tab-name", default=DEFAULT_TAB_NAME, help=f"Tab to remove (default: {DEFAULT_TAB_NAME})")
    parser.add_argument("--keep-screen-id", action="append", default=[], metavar="ID", help="Keep this screen id (repeatable)")
    parser.add_argument(
        "--screen-id",
        action="append",
        default=[],
        metavar="ID",
        help="Restrict the run to these screen ids, e.g. for a pilot (repeatable)",
    )
    parser.add_argument(
        "--field-prefix",
        default=DEFAULT_FIELD_PREFIX,
        help=f"Only delete tabs whose fields all start with this name (default: {DEFAULT_FIELD_PREFIX})",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete tabs (default: dry-run)")
    parser.add_argument("--output", default=DEFAULT_REPORT, help=f"Report path (default: {DEFAULT_REPORT})")
    parser.add_argument("--backup", default=DEFAULT_BACKUP, help=f"Backup JSON path, written on --apply (default: {DEFAULT_BACKUP})")
    args = parser.parse_args()

    try:
        screens = jira.fetch_all_screens()
    except requests.HTTPError as exc:
        print(f"Cannot list screens ({jira._http_error_message(exc)}). Administer Jira permission needed.", file=sys.stderr)
        raise SystemExit(1) from exc
    if args.screen_id:
        wanted = set(args.screen_id)
        screens = [screen for screen in screens if screen.screen_id in wanted]
    print(f"{len(screens)} screen(s) in scope.", file=sys.stderr)

    keep_screen_ids = set(args.keep_screen_id)

    plans: list[ScreenPlan] = []
    skipped_reads: list[tuple[jira.ScreenInfo, str]] = []
    field_names: dict[str, str] = {}
    for index, screen in enumerate(screens, start=1):
        print(f"Scanning {index}/{len(screens)}: {screen.screen_id} ({screen.name})", file=sys.stderr)
        try:
            plan = inspect_screen(screen, args.tab_name, field_names)
        except requests.HTTPError as exc:
            skipped_reads.append((screen, jira._http_error_message(exc)))
            continue
        if plan is None:
            continue
        decide(plan, keep_screen_ids, field_names, args.field_prefix)
        plans.append(plan)

    to_remove = [plan for plan in plans if plan.action == "remove"]

    if args.apply and to_remove:
        backup = {
            "created": datetime.now(timezone.utc).isoformat(),
            "tab_name": args.tab_name,
            "tabs": [asdict(plan) for plan in to_remove],
        }
        write_text(args.backup, json.dumps(backup, indent=2, ensure_ascii=False))
        print(f"Backup written to {args.backup}", file=sys.stderr)
        for index, plan in enumerate(to_remove, start=1):
            print(f"Removing {index}/{len(to_remove)}: screen {plan.screen_id} tab {plan.tab_id}", file=sys.stderr)
            apply_removal(plan)
    else:
        for plan in to_remove:
            plan.outcome = "dry-run"

    report = build_report(
        plans,
        skipped_reads,
        total_screens=len(screens),
        apply=args.apply,
    )
    print(report)
    write_text(args.output, report)
    print(f"Report written to {args.output}", file=sys.stderr)

    if args.apply and any(plan.outcome not in {"removed", "already-gone"} for plan in to_remove):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
