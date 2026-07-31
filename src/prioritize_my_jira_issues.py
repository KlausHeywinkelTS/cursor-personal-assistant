"""Rank the current user's open Jira issues with transparent score reasons.

The script only reads Jira. It does not write to Jira or create local reports.

Usage:
    py src/prioritize_my_jira_issues.py
    py src/prioritize_my_jira_issues.py --max-results 500
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


DONE_STATUSES = frozenset({"done", "rejected"})
PRIORITY_POINTS = {
    "showstopper": 100,
    "high": 50,
    "medium": 20,
    "low": 5,
}
BLOCKED_OR_WAITING = frozenset({"blocked", "waiting"})


@dataclass(frozen=True)
class RankedIssue:
    """An issue together with its calculated score and score explanations."""

    key: str
    summary: str
    status: str
    score: int
    reasons: tuple[str, ...]


def _candidate_jira_helper_dirs() -> list[Path]:
    """Return likely locations for the shared Jira skill helper script."""
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
        "Could not find read_jira_issue.py. Install the Jira user skill or set "
        f"CURSOR_JIRA_SKILL_SRC to its src directory.\nSearched:\n{searched}"
    )


def _load_jira_search() -> Any:
    helper_file = _find_jira_helper_file()
    spec = importlib.util.spec_from_file_location("cursor_jira_read_issue", helper_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Jira helper module from {helper_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, "_jira_search")


_jira_search = _load_jira_search()


def normalize_name(value: Any) -> str:
    """Normalize status, priority and issue type names for stable comparisons."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def field_name(fields: dict[str, Any], name: str) -> str:
    value = fields.get(name) or {}
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def extract_parent_keys(raw_issue: dict[str, Any]) -> set[str]:
    """Return parent-model and classic Epic Link candidates from an issue."""
    fields = raw_issue.get("fields") or {}
    keys: set[str] = set()

    parent = fields.get("parent") or {}
    if isinstance(parent, dict):
        parent_key = str(parent.get("key") or "").strip()
        if parent_key:
            keys.add(parent_key)

    classic_epic_link = fields.get("customfield_10014")
    if isinstance(classic_epic_link, dict):
        classic_epic_link = classic_epic_link.get("key") or classic_epic_link.get("value")
    classic_key = str(classic_epic_link or "").strip()
    if classic_key:
        keys.add(classic_key)

    return keys


def is_open(fields: dict[str, Any]) -> bool:
    status = fields.get("status") or {}
    status_category = status.get("statusCategory") or {} if isinstance(status, dict) else {}
    category_name = (
        status_category.get("key") or status_category.get("name") or ""
        if isinstance(status_category, dict)
        else status_category
    )
    return (
        normalize_name(field_name(fields, "status")) not in DONE_STATUSES
        and normalize_name(category_name) != "done"
    )


def is_subtask(fields: dict[str, Any]) -> bool:
    return normalize_name(field_name(fields, "issuetype")) == "subtask"


def parse_jira_date(value: Any) -> date | None:
    """Parse Jira date-only or ISO timestamp values without failing a ranking."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def quote_jql_keys(keys: set[str]) -> str:
    """Return Jira issue keys safely quoted for an IN-clause."""
    return ", ".join(f'"{key.replace(chr(34), r"\"")}"' for key in sorted(keys))


def fetch_open_issues(max_results: int) -> list[dict[str, Any]]:
    """Fetch every open, assigned, non-Epic issue with ranking-relevant fields."""
    jql = (
        "assignee = currentUser() "
        'AND issuetype != Epic '
        'AND statusCategory != Done '
        "ORDER BY key ASC"
    )
    fields = [
        "summary",
        "status",
        "priority",
        "issuetype",
        "parent",
        "customfield_10014",
        "customfield_10246",
        "updated",
    ]
    return _jira_search(jql=jql, fields=fields, max_results=max_results)


def fetch_epic_summaries(parent_candidates: set[str], max_results: int) -> dict[str, str]:
    """Return the key and summary of every candidate that is a Jira Epic."""
    if not parent_candidates:
        return {}

    issues = _jira_search(
        jql=f"key IN ({quote_jql_keys(parent_candidates)}) AND issuetype = Epic",
        fields=["issuetype", "summary"],
        max_results=max_results,
    )
    return {
        key: str((issue.get("fields") or {}).get("summary") or "").strip()
        for issue in issues
        if (key := str(issue.get("key") or "").strip())
        and normalize_name(field_name(issue.get("fields") or {}, "issuetype")) == "epic"
    }


def fetch_open_direct_epic_children(
    epic_keys: set[str],
    max_results: int,
) -> dict[str, set[str]]:
    """Return open direct child keys by Epic for parent and classic link models."""
    children_by_epic: dict[str, set[str]] = defaultdict(set)
    if not epic_keys:
        return children_by_epic

    quoted_keys = quote_jql_keys(epic_keys)
    common_fields = ["status", "issuetype", "parent", "customfield_10014"]
    parent_model_issues = _jira_search(
        jql=(
            f"parent IN ({quoted_keys}) "
            "AND statusCategory != Done"
        ),
        fields=common_fields,
        max_results=max_results,
    )
    classic_model_issues = _jira_search(
        jql=(
            f"cf[10014] IN ({quoted_keys}) "
            "AND statusCategory != Done"
        ),
        fields=common_fields,
        max_results=max_results,
    )

    for raw_issue in [*parent_model_issues, *classic_model_issues]:
        key = str(raw_issue.get("key") or "").strip()
        fields = raw_issue.get("fields") or {}
        if not key or not is_open(fields) or is_subtask(fields):
            continue

        for epic_key in extract_parent_keys(raw_issue) & epic_keys:
            children_by_epic[epic_key].add(key)

    return children_by_epic


def score_issue(
    raw_issue: dict[str, Any],
    epic_keys: set[str],
    open_children_by_epic: dict[str, set[str]],
    today: date,
    epic_summaries: dict[str, str] | None = None,
) -> RankedIssue:
    """Calculate the score and explanation list for one open issue."""
    fields = raw_issue.get("fields") or {}
    key = str(raw_issue.get("key") or "").strip()
    summary = str(fields.get("summary") or "").strip()
    status = field_name(fields, "status")
    score = 0
    reasons: list[str] = []

    parent_epics = extract_parent_keys(raw_issue) & epic_keys
    epic_summaries = epic_summaries or {}
    epic_summary = next(
        (epic_summaries.get(epic_key, "") for epic_key in sorted(parent_epics)),
        "",
    )
    if epic_summary:
        summary = f"{summary} ({epic_summary})" if summary else f"({epic_summary})"

    for epic_key in sorted(parent_epics):
        if open_children_by_epic.get(epic_key) == {key}:
            score += 50
            reasons.append(f"+50 letzter offener direkter Task im Epic {epic_key}")
            break

    priority = field_name(fields, "priority")
    priority_points = PRIORITY_POINTS.get(normalize_name(priority), 0)
    if priority_points:
        score += priority_points
        reasons.append(f"+{priority_points} Priorität {priority}")

    normalized_status = normalize_name(status)
    if normalized_status == "inprogress":
        score += 50
        reasons.append("+50 Status In Progress")
    elif normalized_status == "todo":
        score += 20
        reasons.append("+20 Status To Do/ToDo")
    elif normalized_status == "toberefined":
        score -= 50
        reasons.append("-50 Status To be refined")

    remind_date = parse_jira_date(fields.get("customfield_10246"))
    if normalized_status in BLOCKED_OR_WAITING and remind_date:
        if remind_date > today:
            score -= 100
            reasons.append(f"-100 {status} mit künftigem Remind-Date ({remind_date.isoformat()})")
        else:
            score += 20
            reasons.append(f"+20 {status} mit fälligem Remind-Date ({remind_date.isoformat()})")

    updated_date = parse_jira_date(fields.get("updated"))
    if normalized_status == "todo" and updated_date:
        inactive_days = (today - updated_date).days
        completed_weeks = inactive_days // 7
        if completed_weeks >= 4:
            inactivity_points = (completed_weeks - 3) * 20
            score += inactivity_points
            reasons.append(
                f"+{inactivity_points} seit {completed_weeks} Wochen ohne Jira-Aktivität"
            )

    return RankedIssue(
        key=key,
        summary=summary,
        status=status,
        score=score,
        reasons=tuple(reasons),
    )


def rank_issues(
    raw_issues: list[dict[str, Any]],
    epic_keys: set[str],
    open_children_by_epic: dict[str, set[str]],
    today: date | None = None,
    epic_summaries: dict[str, str] | None = None,
) -> list[RankedIssue]:
    """Rank already fetched issues; kept pure to make the scoring testable."""
    ranking_day = today or date.today()
    ranked = [
        score_issue(
            raw_issue,
            epic_keys,
            open_children_by_epic,
            ranking_day,
            epic_summaries,
        )
        for raw_issue in raw_issues
        if is_open(raw_issue.get("fields") or {})
        and normalize_name(field_name(raw_issue.get("fields") or {}, "issuetype")) != "epic"
    ]
    return sorted(ranked, key=lambda issue: (-issue.score, issue.key.casefold()))


def fetch_ranked_issues(max_results: int = 2000) -> list[RankedIssue]:
    """Fetch and rank the current user's open non-Epic issues from Jira."""
    if max_results < 1:
        raise ValueError("max_results must be at least 1.")

    raw_issues = fetch_open_issues(max_results)
    parent_candidates = (
        set().union(*(extract_parent_keys(issue) for issue in raw_issues))
        if raw_issues
        else set()
    )
    epic_summaries = fetch_epic_summaries(parent_candidates, max_results)
    epic_keys = set(epic_summaries)
    open_children_by_epic = fetch_open_direct_epic_children(epic_keys, max_results)
    return rank_issues(
        raw_issues,
        epic_keys,
        open_children_by_epic,
        epic_summaries=epic_summaries,
    )


def get_ranked_issues(max_results: int = 2000) -> list[dict[str, Any]]:
    """Return the current ranking as a JSON-compatible array of objects.

    Every item contains ``key``, ``summary``, ``status``, ``score`` and the
    list of score ``reasons``. The caller can pass the result directly to a
    JSON response or serialize it with ``json.dumps``.
    """
    return [
        {
            "key": issue.key,
            "summary": issue.summary,
            "status": issue.status,
            "score": issue.score,
            "reasons": list(issue.reasons),
        }
        for issue in fetch_ranked_issues(max_results)
    ]


def get_ranked_issues_json(max_results: int = 2000) -> str:
    """Return the current ranking as a serialized JSON array."""
    return json.dumps(get_ranked_issues(max_results), ensure_ascii=False)


def format_ranking(issues: list[RankedIssue]) -> str:
    """Format the requested compact, human-readable ranking list."""
    if not issues:
        return "Keine offenen, dir zugewiesenen Nicht-Epic-Issues gefunden."

    lines = [f"Jira-Task-Ranking: {len(issues)} Issue(s)", ""]
    for issue in issues:
        lines.append(
            f"{issue.key} | {issue.summary or '(ohne Summary)'} | "
            f"{issue.status or '(ohne Status)'} | {issue.score} Punkte"
        )
        if issue.reasons:
            lines.extend(f"  - {reason}" for reason in issue.reasons)
        else:
            lines.append("  - 0 Punkte: Keine der konfigurierten Regeln trifft zu.")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Rank open Jira issues assigned to the current user without modifying Jira."
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=2000,
        help="Maximum number of Jira results per query (default: 2000).",
    )
    args = parser.parse_args()
    if args.max_results < 1:
        parser.error("--max-results must be at least 1.")

    try:
        print(format_ranking(fetch_ranked_issues(args.max_results)))
    except Exception as exc:
        print(f"Fehler beim Lesen der Jira-Issues: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
