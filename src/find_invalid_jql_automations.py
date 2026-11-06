"""Find Jira automation rules whose JQL Jira will reject from 2026-11-23.

Background: Atlassian announced that Jira will require *all* clauses of a JQL
query to be valid (no more silently ignored clauses, e.g. `status IN
openSprints()`, `sprint WAS "..."` or `project IS "IT Support"`).

The script
1. loads every automation rule visible to the authenticated user
   (Automation Rule Management API, same approach as
   list_roadmap_field_automations.py),
2. extracts every JQL string from the rule configuration
   (scheduled triggers, JQL conditions, related-issue branches, lookup smart
   values, webhook triggers, ...),
3. validates them with Jira's `POST /rest/api/3/jql/parse?validation=strict`,
4. writes a Markdown report with all rules that contain invalid JQL.

Smart values such as `{{issue.key}}` are replaced by a placeholder before the
check. Errors that merely complain about that placeholder are dropped, so only
errors that do not depend on the runtime value remain. Queries with smart
values are marked in the report because value checks are not possible for them.

Usage:
    py src/find_invalid_jql_automations.py
    py src/find_invalid_jql_automations.py --output reports/my-report.md
    py src/find_invalid_jql_automations.py --include-ok   # also list valid JQL

Credentials are read from ATLASSIAN_USER and ATLASSIAN_TOKEN. The Automation
API requires a non-scoped Atlassian API token.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from list_roadmap_field_automations import (
    JIRA_BASE_URL,
    ScanError,
    _escape_inline_code,
    _escape_pipe,
    _format_timestamp,
    _json_path_key,
    _rule_edit_url,
    create_session,
    fetch_all_rule_summaries,
    fetch_rule,
    get_cloud_id,
)


JQL_PARSE_PATH = "/rest/api/3/jql/parse"
PARSE_BATCH_SIZE = 50
PLACEHOLDER = "SMARTVALUEPLACEHOLDER"
ENFORCEMENT_DATE = "2026-11-23"

# Component types whose own `value` is a JQL string.
JQL_VALUE_COMPONENT_TYPES = {"jira.jql.condition"}
# Dictionary keys that hold JQL strings (compared case-insensitively).
JQL_KEYS = {"jql", "comparejql", "relatedjql"}
# Jira error texts that depend on the validating user (visibility/existence of
# projects, issues, request types ...). The check runs as the API user, while an
# automation runs as its actor, so these may be false alarms.
VALUE_ERROR_MARKERS = (
    "does not exist",
    "permission",
    "could not be found",
    "you need access",
)
MAX_DESCRIPTION_LENGTH = 240


@dataclass(frozen=True)
class JqlReference:
    path: str
    component_type: str
    jql: str


def is_value_error(error: str) -> bool:
    """True for errors that depend on who runs the check (visibility, existence)."""
    lowered = error.lower()
    return any(marker in lowered for marker in VALUE_ERROR_MARKERS)


@dataclass(frozen=True)
class JqlFinding:
    reference: JqlReference
    errors: tuple[str, ...]
    has_smart_value: bool

    @property
    def structural_errors(self) -> tuple[str, ...]:
        """Syntax, operator, field or function errors - independent of the user."""
        return tuple(error for error in self.errors if not is_value_error(error))

    @property
    def value_errors(self) -> tuple[str, ...]:
        """Value/permission errors - may be false alarms for the rule's actor."""
        return tuple(error for error in self.errors if is_value_error(error))


@dataclass(frozen=True)
class RuleResult:
    uuid: str
    name: str
    state: str
    description: str
    scopes: tuple[str, ...]
    updated: str
    edit_url: str
    checked: tuple[JqlFinding, ...]

    @property
    def invalid(self) -> list[JqlFinding]:
        return [finding for finding in self.checked if finding.errors]

    @property
    def definite(self) -> list[JqlFinding]:
        return [finding for finding in self.checked if finding.structural_errors]

    @property
    def to_review(self) -> list[JqlFinding]:
        return [
            finding
            for finding in self.checked
            if finding.value_errors and not finding.structural_errors
        ]


def _text_value(value: Any) -> str:
    """Return the text of a plain string or of a {"type": ..., "value": ...} dict."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("value"), str):
        return value["value"]
    return ""


def extract_jql(rule: dict[str, Any]) -> list[JqlReference]:
    """Collect every JQL string in a rule configuration (deduplicated by path)."""
    references: list[JqlReference] = []
    seen: set[tuple[str, str]] = set()

    def add(path: str, component_type: str, jql: str) -> None:
        jql = jql.strip()
        if jql and (path, jql) not in seen:
            seen.add((path, jql))
            references.append(JqlReference(path, component_type, jql))

    def visit(value: Any, path: str, component_type: str) -> None:
        if isinstance(value, dict):
            raw_type = value.get("type")
            own_type = raw_type if isinstance(raw_type, str) else component_type

            if own_type in JQL_VALUE_COMPONENT_TYPES:
                add(path + ".value", own_type, _text_value(value.get("value")))
            # Lookup smart value: {"type": "JQL", "query": {"value": "..."}}
            if raw_type == "JQL" and "query" in value:
                add(path + ".query", "smart value (JQL lookup)", _text_value(value["query"]))

            for key, child in value.items():
                child_path = path + _json_path_key(str(key))
                if str(key).lower() in JQL_KEYS:
                    add(child_path, own_type, _text_value(child))
                visit(child, child_path, own_type)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]", component_type)

    visit(rule, "$", "")
    return references


def neutralize_smart_values(jql: str) -> tuple[str, bool]:
    """Replace `{{smart values}}` by a placeholder so Jira can parse the JQL.

    Inside quotes only the smart value is replaced; outside quotes the
    placeholder is wrapped in quotes so it stays a syntactically valid value.
    """
    out: list[str] = []
    quote = ""
    found = False
    index = 0

    while index < len(jql):
        if jql.startswith("{{", index):
            end = jql.find("}}", index + 2)
            if end != -1:
                found = True
                out.append(PLACEHOLDER if quote else f'"{PLACEHOLDER}"')
                index = end + 2
                continue

        char = jql[index]
        if quote:
            if char == "\\" and index + 1 < len(jql):
                out.append(jql[index : index + 2])
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        out.append(char)
        index += 1

    return "".join(out), found


def _post_parse(session: requests.Session, queries: list[str]) -> list[list[str]]:
    """Validate queries with Jira. Returns one error list per query."""
    response = session.post(
        f"{JIRA_BASE_URL}{JQL_PARSE_PATH}",
        params={"validation": "strict"},
        json={"queries": queries},
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    results = (response.json() or {}).get("queries") or []
    if len(results) != len(queries):
        raise RuntimeError("JQL parse response does not match the request.")
    return [[str(error) for error in (item.get("errors") or [])] for item in results]


def validate_queries(
    session: requests.Session, queries: list[str]
) -> dict[str, list[str]]:
    """Validate unique queries in batches; falls back to single calls on failure."""
    unique = list(dict.fromkeys(queries))
    errors_by_query: dict[str, list[str]] = {}

    for start in range(0, len(unique), PARSE_BATCH_SIZE):
        batch = unique[start : start + PARSE_BATCH_SIZE]
        try:
            batch_errors = _post_parse(session, batch)
        except RuntimeError:
            batch_errors = []
            for query in batch:
                try:
                    batch_errors.append(_post_parse(session, [query])[0])
                except RuntimeError as exc:
                    batch_errors.append([f"Validierung fehlgeschlagen: {exc}"])
        errors_by_query.update(zip(batch, batch_errors))

    return errors_by_query


def load_rules(
    session: requests.Session,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[ScanError], int]:
    cloud_id = get_cloud_id(session)
    summaries = fetch_all_rule_summaries(session, cloud_id)
    print(f"  -> {len(summaries)} automation rule(s) found")

    rules: list[tuple[dict[str, Any], dict[str, Any]]] = []
    errors: list[ScanError] = []
    for index, summary in enumerate(summaries, start=1):
        rule_uuid = str(summary.get("uuid") or "").strip()
        name = str(summary.get("name") or "–")
        print(f"  [{index}/{len(summaries)}] {name}")
        if not rule_uuid:
            errors.append(ScanError("–", name, "Rule summary has no UUID."))
            continue
        try:
            payload = fetch_rule(session, cloud_id, rule_uuid)
        except Exception as exc:
            errors.append(ScanError(rule_uuid, name, str(exc)))
            continue
        rule = payload.get("rule")
        rules.append((summary, rule if isinstance(rule, dict) else {}))
    return rules, errors, len(summaries)


def check_rules(
    session: requests.Session,
    rules: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[RuleResult]:
    extracted = [(summary, rule, extract_jql(rule)) for summary, rule in rules]
    neutralized = {
        reference.jql: neutralize_smart_values(reference.jql)
        for _, _, references in extracted
        for reference in references
    }
    print(f"  -> {len(neutralized)} distinct JQL string(s) to validate")
    errors_by_query = validate_queries(
        session, [query for query, _ in neutralized.values()]
    )

    results: list[RuleResult] = []
    for summary, rule, references in extracted:
        findings: list[JqlFinding] = []
        for reference in references:
            query, has_smart_value = neutralized[reference.jql]
            errors = errors_by_query.get(query, [])
            if has_smart_value:
                # Complaints about the placeholder are artifacts of the replacement.
                errors = [error for error in errors if PLACEHOLDER not in error]
            findings.append(JqlFinding(reference, tuple(errors), has_smart_value))

        scopes = rule.get("ruleScopeARIs") or summary.get("ruleScopeARIs") or []
        if not isinstance(scopes, list):
            scopes = [str(scopes)]
        rule_uuid = str(rule.get("uuid") or summary.get("uuid") or "")
        results.append(
            RuleResult(
                uuid=rule_uuid,
                name=str(rule.get("name") or summary.get("name") or "–"),
                state=str(rule.get("state") or summary.get("state") or "–"),
                description=str(
                    rule.get("description") or summary.get("description") or ""
                ),
                scopes=tuple(str(scope) for scope in scopes),
                updated=_format_timestamp(rule.get("updated") or summary.get("updated")),
                edit_url=_rule_edit_url(rule_uuid),
                checked=tuple(findings),
            )
        )

    results.sort(
        key=lambda item: (
            not item.definite,
            item.state != "ENABLED",
            item.name.strip().lower(),
        )
    )
    return results


def _short_scope(scope: str) -> str:
    return scope.rsplit("/", 1)[-1] if "/" in scope else scope


def _short_text(text: str, limit: int = MAX_DESCRIPTION_LENGTH) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 3] + "..."


def _scopes_cell(result: RuleResult) -> str:
    return "<br>".join(_escape_pipe(_short_scope(s)) for s in result.scopes) or "–"


def build_markdown(
    results: list[RuleResult],
    load_errors: list[ScanError],
    total_rules: int,
    include_ok: bool,
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    definite_rules = [result for result in results if result.definite]
    review_rules = [
        result for result in results if not result.definite and result.to_review
    ]
    with_jql = [result for result in results if result.checked]
    total_jql = sum(len(result.checked) for result in results)
    smart_ok = sum(
        1
        for result in results
        for finding in result.checked
        if finding.has_smart_value and not finding.errors
    )

    lines: list[str] = [
        f"# Jira-Automationen mit ungültigem JQL (Stichtag {ENFORCEMENT_DATE})",
        "",
        f"_Generiert: {generated_at}_",
        "",
        (
            f"Ab dem {ENFORCEMENT_DATE} lehnt Jira Suchen ab, in denen eine einzelne "
            "Klausel ungültig ist. Geprüft wurde jede JQL-Angabe in den "
            "Automationen mit `POST /rest/api/3/jql/parse` (strict)."
        ),
        "",
        "## Ergebnis",
        "",
        f"- Sichtbare Automationen: {total_rules}",
        f"- Automationen mit JQL: {len(with_jql)} (insgesamt {total_jql} JQL-Angaben)",
        f"- **Eindeutig ungültig** (Syntax, Operator, Feld, Funktion): "
        f"**{len(definite_rules)} Automationen**",
        f"- **Manuell prüfen** (Wert oder Berechtigung): **{len(review_rules)} Automationen**",
        f"- Nicht ladbare Automationen: {len(load_errors)}",
        "",
        (
            "Wert- und Berechtigungsfehler (z. B. \"Projekt existiert nicht\", "
            "\"Issue existiert nicht oder keine Berechtigung\") entstehen, weil die "
            "Prüfung als der API-Nutzer läuft. Eine Automation läuft als ihr Actor "
            "und sieht womöglich mehr. Diese Treffer sind deshalb nur Verdachtsfälle."
        ),
        "",
    ]

    if smart_ok:
        lines.extend(
            [
                (
                    f"{smart_ok} fehlerfrei geprüfte JQL-Angaben enthalten Smart Values "
                    "(`{{...}}`). Deren Werte lassen sich ohne Laufzeitkontext nicht "
                    "prüfen; Operator-, Feld- und Syntaxfehler wurden trotzdem erkannt."
                ),
                "",
            ]
        )

    affected = definite_rules + review_rules
    if affected:
        lines.extend(
            [
                "## Übersicht",
                "",
                "| Automation | Status | Eindeutig ungültig | Prüfen | Scope | Aktualisiert |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in affected:
            lines.append(
                f"| [{_escape_pipe(result.name)}]({result.edit_url}) | "
                f"{_escape_pipe(result.state)} | {len(result.definite)} | "
                f"{len(result.to_review)} | {_scopes_cell(result)} | "
                f"{_escape_pipe(result.updated)} |"
            )
        lines.append("")

        lines.extend(["## Details", ""])
        for result in affected:
            lines.extend(_rule_details(result, only_invalid=not include_ok))
    else:
        lines.extend(["_Keine Automation mit ungültigem JQL gefunden._", ""])

    if include_ok:
        valid = [result for result in with_jql if not result.invalid]
        if valid:
            lines.extend(["## Automationen mit gültigem JQL", ""])
            for result in valid:
                lines.append(
                    f"- [{_escape_pipe(result.name)}]({result.edit_url}) "
                    f"({result.state}, {len(result.checked)} JQL)"
                )
            lines.append("")

    if load_errors:
        lines.extend(
            [
                "## Nicht geprüfte Automationen",
                "",
                "Diese Regeln konnten nicht geladen werden; das Ergebnis ist dafür unvollständig.",
                "",
            ]
        )
        for error in load_errors:
            lines.append(
                f"- **{_escape_pipe(error.name)}** (`{error.uuid}`): {_escape_pipe(error.message)}"
            )
        lines.append("")

    return "\n".join(lines)


def _rule_details(result: RuleResult, *, only_invalid: bool) -> list[str]:
    lines = [
        f"### {_escape_pipe(result.name.strip())} ({result.uuid[:8]})",
        "",
        f"- **Status:** {result.state}",
        f"- **Link:** {result.edit_url}",
        f"- **UUID:** `{result.uuid}`",
    ]
    if result.description:
        lines.append(f"- **Beschreibung:** {_escape_pipe(_short_text(result.description))}")
    lines.append("")

    findings = result.invalid if only_invalid else list(result.checked)
    for finding in findings:
        reference = finding.reference
        lines.extend(
            [
                f"Fundstelle `{_escape_inline_code(reference.path)}` "
                f"({_escape_inline_code(reference.component_type) or 'unbekannt'}):",
                "",
                "```sql",
                reference.jql,
                "```",
                "",
            ]
        )
        if finding.structural_errors:
            lines.extend(
                f"- **Ungültig:** {_escape_pipe(error)}"
                for error in finding.structural_errors
            )
        if finding.value_errors:
            lines.extend(
                f"- Prüfen (Wert/Berechtigung): {_escape_pipe(error)}"
                for error in finding.value_errors
            )
        if not finding.errors:
            lines.append("- Gültig.")
        elif finding.has_smart_value:
            lines.append("- Enthält Smart Values; Fehler sind unabhängig vom Laufzeitwert.")
        lines.append("")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find Jira automation rules with JQL that Jira will reject "
            f"from {ENFORCEMENT_DATE}."
        )
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output markdown file (default: reports/invalid-jql-automations-<date>.md)",
    )
    parser.add_argument(
        "--include-ok",
        action="store_true",
        help="Also list automations whose JQL is valid, and valid JQL of affected rules.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or f"reports/invalid-jql-automations-{today}.md"

    session = create_session()
    print("Fetching visible Jira automation rules ...")
    rules, load_errors, total_rules = load_rules(session)

    print("Extracting and validating JQL ...")
    results = check_rules(session, rules)
    definite = sum(1 for result in results if result.definite)
    review = sum(1 for result in results if not result.definite and result.to_review)
    print(
        f"  -> {definite} definitely invalid rule(s), {review} to review manually, "
        f"{len(load_errors)} load error(s)"
    )

    markdown = build_markdown(results, load_errors, total_rules, args.include_ok)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8", newline="\n")
    print(f"\nMarkdown written to: {output_file}")


if __name__ == "__main__":
    main()
