"""Count open Bugs without a value in the "Has customer impact" custom field.

Iterates over a fixed list of Jira project keys and reports how many open Bugs
have an empty "Has customer impact" field per project.

Usage:
    py src/count_bugs_missing_customer_impact.py
    py src/count_bugs_missing_customer_impact.py --output tmp/bug-customer-impact-counts.txt
    py src/count_bugs_missing_customer_impact.py --projects REVIN INV
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jira_skill import jira_get_metadata as _jira_get
from jira_skill import search as _jira_search

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
    "CA",
    "GUARANTEE",
    "SEO"
]
CUSTOMER_IMPACT_FIELD_NAME = "Has customer impact"


def find_custom_field_by_name(field_name: str) -> tuple[str, str]:
    """Return (field_id, jql_clause_name) for a custom field display name."""
    fields = _jira_get("/rest/api/3/field")
    if not isinstance(fields, list):
        raise RuntimeError("Unexpected response from /rest/api/3/field")

    target = field_name.casefold()
    for field in fields:
        name = str(field.get("name") or "")
        if name.casefold() != target:
            continue
        field_id = str(field.get("id") or "")
        clause_names = [str(c) for c in (field.get("clauseNames") or [])]
        jql_clause_name = next(
            (clause for clause in clause_names if clause.casefold() == target),
            name,
        )
        return field_id, jql_clause_name

    raise ValueError(f'Custom field "{field_name}" not found in Jira.')


def build_jql(project_key: str, customer_impact_clause_name: str) -> str:
    return (
        f"project = {project_key} "
        f"AND issuetype = Bug "
        f"AND statusCategory != Done "
        f'AND "{customer_impact_clause_name}" IS EMPTY'
    )


def count_issues(jql: str) -> int:
    issues = _jira_search(jql=jql, fields=["key"], max_results=10_000)
    return len(issues)


def build_report(
    project_keys: list[str],
    counts_by_project: dict[str, int],
    field_id: str,
    field_name: str,
) -> str:
    lines = [
        f'Offene Bugs ohne Wert in "{field_name}" ({field_id})',
        "",
    ]
    total = sum(counts_by_project.get(project_key, 0) for project_key in project_keys)
    sorted_projects = sorted(
        project_keys,
        key=lambda key: (-counts_by_project.get(key, 0), key),
    )
    counts = [counts_by_project.get(project_key, 0) for project_key in sorted_projects]
    space_width = max(len("Space"), *(len(project_key) for project_key in sorted_projects), len("Total"))
    count_width = max(len("count"), *(len(str(count)) for count in counts), len(str(total)))

    lines.append(f"{'Space':<{space_width}}  {'count':>{count_width}}")
    lines.append(f"{'-' * space_width}  {'-' * count_width}")
    for project_key, count in zip(sorted_projects, counts, strict=True):
        lines.append(f"{project_key:<{space_width}}  {count:>{count_width}}")
    lines.extend(["", f"{'Total':<{space_width}}  {total:>{count_width}}"])
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description=(
            'Count open Bugs with empty "Has customer impact" per Jira project.'
        )
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=DEFAULT_PROJECTS,
        help="Jira project keys to scan (default: predefined space list)",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the text report",
    )
    args = parser.parse_args()

    field_id, jql_clause_name = find_custom_field_by_name(CUSTOMER_IMPACT_FIELD_NAME)
    print(
        f'Using custom field "{CUSTOMER_IMPACT_FIELD_NAME}" '
        f"({field_id}, JQL clause: \"{jql_clause_name}\")",
        file=sys.stderr,
    )

    counts_by_project: dict[str, int] = {}
    for project_key in args.projects:
        jql = build_jql(project_key, jql_clause_name)
        print(f"Searching {project_key} ...", file=sys.stderr)
        counts_by_project[project_key] = count_issues(jql)

    report = build_report(args.projects, counts_by_project, field_id, CUSTOMER_IMPACT_FIELD_NAME)
    print(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8", newline="\n")
        print(f"Report written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
