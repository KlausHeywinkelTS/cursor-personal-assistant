"""List Jira automation rules that use the "Relevant for P&E Roadmap" field.

The script combines Jira's field metadata endpoint with Atlassian's Automation
Rule Management API. It scans every automation rule visible to the authenticated
user and writes a Markdown report containing all matching rules and the locations
inside their configurations where the field is referenced.

Usage:
    py src/list_roadmap_field_automations.py
    py src/list_roadmap_field_automations.py --field-id customfield_10112
    py src/list_roadmap_field_automations.py --output reports/custom-report.md

Credentials are read from ATLASSIAN_USER and ATLASSIAN_TOKEN. The Automation API
currently requires a non-scoped Atlassian API token; OAuth and scoped API tokens
are not supported by this endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from list_roadmap_field_filters import (
    DEFAULT_FIELD_ID,
    DEFAULT_FIELD_LABEL,
    JIRA_BASE_URL,
    get_field_metadata,
)


AUTOMATION_API_ROOT = "https://api.atlassian.com/automation/public/jira"
DEFAULT_PAGE_SIZE = 100
MAX_REFERENCE_SNIPPET_LENGTH = 240


@dataclass(frozen=True)
class FieldReference:
    path: str
    matched_alias: str
    snippet: str


@dataclass(frozen=True)
class AutomationMatch:
    uuid: str
    name: str
    state: str
    description: str
    author_account_id: str
    scopes: tuple[str, ...]
    updated: str
    edit_url: str
    references: tuple[FieldReference, ...]


@dataclass(frozen=True)
class ScanError:
    uuid: str
    name: str
    message: str


def _get_auth() -> tuple[str, str]:
    user = os.getenv("ATLASSIAN_USER")
    token = os.getenv("ATLASSIAN_TOKEN")
    if not user or not token:
        raise RuntimeError(
            "Missing credentials. Set ATLASSIAN_USER and ATLASSIAN_TOKEN "
            "environment variables."
        )
    return user, token


def create_session() -> requests.Session:
    session = requests.Session()
    session.auth = _get_auth()
    session.headers.update({"Accept": "application/json"})
    return session


def _response_error(response: requests.Response) -> str:
    body = response.text.strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 400:
        body = body[:397] + "..."
    suffix = f": {body}" if body else ""
    return f"HTTP {response.status_code} for {response.url}{suffix}"


def get_cloud_id(session: requests.Session) -> str:
    """Resolve the Jira site's cloud ID required by the Automation API."""
    response = session.get(f"{JIRA_BASE_URL}/_edge/tenant_info", timeout=30)
    if not response.ok:
        raise RuntimeError(_response_error(response))

    cloud_id = str((response.json() or {}).get("cloudId") or "").strip()
    if not cloud_id:
        raise RuntimeError("The tenant_info response did not contain a cloudId.")
    return cloud_id


def _automation_get(
    session: requests.Session,
    cloud_id: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{AUTOMATION_API_ROOT}/{cloud_id}/rest/v1{path}"
    response = session.get(url, params=params, timeout=60)
    if not response.ok:
        message = _response_error(response)
        if response.status_code in {401, 403}:
            message += (
                ". The Automation API requires sufficient Jira automation "
                "permissions and a non-scoped Atlassian API token."
            )
        raise RuntimeError(message)

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected Automation API response for {response.url}.")
    return payload


def _next_cursor(links: Any) -> str:
    if not isinstance(links, dict):
        return ""

    next_link = str(links.get("next") or "").strip()
    if not next_link:
        return ""

    query = urlparse(next_link).query
    if not query and next_link.startswith("?"):
        query = next_link[1:]
    values = parse_qs(query).get("cursor") or []
    return str(values[0]) if values else ""


def fetch_all_rule_summaries(
    session: requests.Session, cloud_id: str
) -> list[dict[str, Any]]:
    """Fetch every automation rule summary visible to the current user."""
    summaries: list[dict[str, Any]] = []
    cursor = ""
    seen_cursors: set[str] = set()

    while True:
        params: dict[str, Any] = {"limit": DEFAULT_PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor

        payload = _automation_get(
            session, cloud_id, "/rule/summary", params=params
        )
        page = payload.get("data") or []
        if not isinstance(page, list):
            raise RuntimeError("Automation rule summary response has invalid data.")
        summaries.extend(item for item in page if isinstance(item, dict))

        next_cursor = _next_cursor(payload.get("links"))
        if not next_cursor:
            break
        if next_cursor in seen_cursors:
            raise RuntimeError("Automation API returned a repeated pagination cursor.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return summaries


def fetch_rule(
    session: requests.Session, cloud_id: str, rule_uuid: str
) -> dict[str, Any]:
    """Fetch a complete rule while redacting unrelated sensitive values."""
    return _automation_get(
        session,
        cloud_id,
        f"/rule/{rule_uuid}",
        params={"redactSensitiveFields": "true"},
    )


def _field_aliases(
    field_id: str, field_name: str, clause_names: list[str]
) -> list[str]:
    aliases = {field_id, field_name, *clause_names}
    if field_id.startswith("customfield_"):
        numeric_id = field_id.removeprefix("customfield_")
        aliases.add(f"cf[{numeric_id}]")

    return sorted((alias for alias in aliases if alias), key=len, reverse=True)


def _alias_pattern(aliases: list[str]) -> re.Pattern[str]:
    escaped = [re.escape(alias) for alias in aliases]
    return re.compile(
        r"(?<![\w])(" + "|".join(escaped) + r")(?![\w])", re.IGNORECASE
    )


def _json_path_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f".{key}"
    return f"[{json.dumps(key, ensure_ascii=False)}]"


def _shorten(value: str, match_start: int) -> str:
    text = " ".join(value.split())
    if len(text) <= MAX_REFERENCE_SNIPPET_LENGTH:
        return text

    radius = MAX_REFERENCE_SNIPPET_LENGTH // 2
    start = max(0, match_start - radius)
    end = min(len(text), start + MAX_REFERENCE_SNIPPET_LENGTH)
    start = max(0, end - MAX_REFERENCE_SNIPPET_LENGTH)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def find_field_references(
    payload: Any, field_id: str, field_name: str, clause_names: list[str]
) -> list[FieldReference]:
    """Find field references recursively in keys and string values."""
    aliases = _field_aliases(field_id, field_name, clause_names)
    pattern = _alias_pattern(aliases)
    references: list[FieldReference] = []
    seen: set[tuple[str, str, str]] = set()

    def add(path: str, matched_alias: str, snippet: str) -> None:
        key = (path, matched_alias.lower(), snippet)
        if key not in seen:
            seen.add(key)
            references.append(
                FieldReference(
                    path=path,
                    matched_alias=matched_alias,
                    snippet=snippet,
                )
            )

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for raw_key, child in value.items():
                key = str(raw_key)
                child_path = path + _json_path_key(key)
                key_match = pattern.search(key)
                if key_match:
                    add(
                        child_path,
                        key_match.group(1),
                        f"Konfigurationsschlüssel: {key}",
                    )
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            for match in pattern.finditer(value):
                add(path, match.group(1), _shorten(value, match.start()))

    visit(payload, "$")
    references.sort(key=lambda item: (item.path.lower(), item.matched_alias.lower()))
    return references


def _format_timestamp(value: Any) -> str:
    if value in (None, ""):
        return "–"
    try:
        timestamp = float(value)
        return (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M %Z")
        )
    except (TypeError, ValueError, OSError):
        return str(value)


def _rule_edit_url(rule_uuid: str) -> str:
    return f"{JIRA_BASE_URL}/jira/settings/automation#/rule/{rule_uuid}"


def scan_rules(
    session: requests.Session,
    cloud_id: str,
    summaries: list[dict[str, Any]],
    field_id: str,
    field_name: str,
    clause_names: list[str],
) -> tuple[list[AutomationMatch], list[ScanError]]:
    matches: list[AutomationMatch] = []
    errors: list[ScanError] = []

    for index, summary in enumerate(summaries, start=1):
        rule_uuid = str(summary.get("uuid") or "").strip()
        name = str(summary.get("name") or "–")
        print(f"  [{index}/{len(summaries)}] {name}")

        if not rule_uuid:
            errors.append(
                ScanError(uuid="–", name=name, message="Rule summary has no UUID.")
            )
            continue

        try:
            payload = fetch_rule(session, cloud_id, rule_uuid)
            references = find_field_references(
                payload, field_id, field_name, clause_names
            )
        except Exception as exc:
            errors.append(
                ScanError(uuid=rule_uuid, name=name, message=str(exc))
            )
            continue

        if not references:
            continue

        rule = payload.get("rule") or {}
        if not isinstance(rule, dict):
            rule = {}
        scopes = rule.get("ruleScopeARIs") or summary.get("ruleScopeARIs") or []
        if not isinstance(scopes, list):
            scopes = [str(scopes)]

        matches.append(
            AutomationMatch(
                uuid=rule_uuid,
                name=str(rule.get("name") or name),
                state=str(rule.get("state") or summary.get("state") or "–"),
                description=str(
                    rule.get("description") or summary.get("description") or ""
                ),
                author_account_id=str(
                    rule.get("authorAccountId")
                    or summary.get("authorAccountId")
                    or "–"
                ),
                scopes=tuple(str(scope) for scope in scopes),
                updated=_format_timestamp(
                    rule.get("updated") or summary.get("updated")
                ),
                edit_url=_rule_edit_url(rule_uuid),
                references=tuple(references),
            )
        )

    matches.sort(key=lambda item: item.name.lower())
    errors.sort(key=lambda item: item.name.lower())
    return matches, errors


def _escape_pipe(text: str) -> str:
    return text.replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def _escape_inline_code(text: str) -> str:
    return text.replace("`", "'")


def build_markdown(
    field_id: str,
    field_name: str,
    aliases: list[str],
    matches: list[AutomationMatch],
    errors: list[ScanError],
    total_scanned: int,
) -> str:
    generated_at = (
        datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    )
    lines: list[str] = [
        f'# Jira-Automationen, die das Feld "{field_name}" ({field_id}) nutzen',
        "",
        f"_Generiert: {generated_at}_",
        "",
        (
            f"Durchsucht: {total_scanned} für den aktuellen Nutzer sichtbare "
            f"Automationen. Gefunden: {len(matches)} Automationen mit Bezug auf "
            f"das Feld. Nicht vollständig prüfbar: {len(errors)}."
        ),
        "",
        (
            "Gesuchte Feld-Aliasse: "
            + ", ".join(f"`{_escape_inline_code(alias)}`" for alias in aliases)
        ),
        "",
    ]

    if matches:
        lines.extend(
            [
                "## Übersicht",
                "",
                "| Automation | Status | Scope | Referenzen | Aktualisiert |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for match in matches:
            scopes = "<br>".join(_escape_pipe(scope) for scope in match.scopes) or "–"
            name_link = f"[{_escape_pipe(match.name)}]({match.edit_url})"
            lines.append(
                f"| {name_link} | {_escape_pipe(match.state)} | {scopes} | "
                f"{len(match.references)} | {_escape_pipe(match.updated)} |"
            )
        lines.append("")

        lines.extend(["## Details", ""])
        for match in matches:
            lines.extend(
                [
                    f"### {_escape_pipe(match.name)}",
                    "",
                    f"- **UUID:** `{match.uuid}`",
                    f"- **Status:** {match.state}",
                    f"- **Autor-Account-ID:** `{match.author_account_id}`",
                    f"- **Aktualisiert:** {match.updated}",
                    f"- **Link:** {match.edit_url}",
                    (
                        "- **Scope:** "
                        + (
                            ", ".join(
                                f"`{_escape_inline_code(scope)}`"
                                for scope in match.scopes
                            )
                            or "–"
                        )
                    ),
                ]
            )
            if match.description:
                lines.append(
                    f"- **Beschreibung:** {_escape_pipe(match.description)}"
                )
            lines.extend(["", "Gefundene Referenzen:", ""])
            for reference in match.references:
                lines.append(
                    f"- `{_escape_inline_code(reference.path)}` über Alias "
                    f"`{_escape_inline_code(reference.matched_alias)}`: "
                    f"{_escape_pipe(reference.snippet)}"
                )
            lines.append("")
    else:
        lines.extend(
            [
                "_Keine Automation mit Bezug auf dieses Feld gefunden._",
                "",
            ]
        )

    if errors:
        lines.extend(
            [
                "## Nicht vollständig geprüfte Automationen",
                "",
                (
                    "Diese Regeln konnten nicht geladen werden. Das Ergebnis ist "
                    "daher für diese Regeln nicht vollständig."
                ),
                "",
            ]
        )
        for error in errors:
            lines.append(
                f"- **{_escape_pipe(error.name)}** (`{error.uuid}`): "
                f"{_escape_pipe(error.message)}"
            )
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'List Jira automation rules that use the "Relevant for P&E Roadmap" '
            "custom field."
        )
    )
    parser.add_argument(
        "--field-id",
        default=DEFAULT_FIELD_ID,
        help=f"Custom field ID to search for (default: {DEFAULT_FIELD_ID})",
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Output markdown file path "
            "(default: reports/automations-<field-id>-<date>.md)"
        ),
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
    output_path = (
        args.output or f"reports/automations-{field_id}-{today}.md"
    )

    print(f"Looking up field metadata for {field_id} ...")
    field_name, clause_names = get_field_metadata(field_id)
    if not field_name:
        field_name = (
            DEFAULT_FIELD_LABEL if field_id == DEFAULT_FIELD_ID else field_id
        )
    aliases = _field_aliases(field_id, field_name, clause_names)
    print(f'  -> "{field_name}" (aliases: {", ".join(aliases)})')

    session = create_session()
    print("Resolving Jira cloud ID ...")
    cloud_id = get_cloud_id(session)
    print(f"  -> {cloud_id}")

    print("Fetching visible Jira automation rules ...")
    summaries = fetch_all_rule_summaries(session, cloud_id)
    print(f"  -> {len(summaries)} automation rule(s) found")

    print(f"Checking rules for references to {field_id} ...")
    matches, errors = scan_rules(
        session,
        cloud_id,
        summaries,
        field_id,
        field_name,
        clause_names,
    )
    print(f"  -> {len(matches)} matching rule(s), {len(errors)} error(s)")

    markdown = build_markdown(
        field_id,
        field_name,
        aliases,
        matches,
        errors,
        total_scanned=len(summaries),
    )
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8", newline="\n")
    print(f"\nMarkdown written to: {output_file}")


if __name__ == "__main__":
    main()
