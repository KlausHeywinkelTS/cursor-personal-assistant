"""Retrieve Tempo Worklogs and resolve their authors through Jira.

Required environment variables:
    TEMPO_TOKEN: Tempo Bearer token
    ATLASSIAN_USER: Atlassian account email address
    ATLASSIAN_API_TOKEN: Atlassian API token for klausheywinkel.atlassian.net

Usage:
    py src/test_tempo_worklogs.py
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any
from xml.sax.saxutils import escape

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TEMPO_WORKLOGS_URL = "https://api.tempo.io/4/worklogs"
ATLASSIAN_BASE_URL = "https://klausheywinkel.atlassian.net"
REQUEST_TIMEOUT_SECONDS = 30
REPORTS_DIRECTORY = Path("reports")
GERMAN_MONTH_NAMES = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def get_required_environment_variable(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} ist nicht gesetzt. "
            f'Setze ihn z. B. mit: $env:{name} = "..."'
        )
    return value


def retrieve_worklogs(tempo_token: str) -> dict[str, Any]:
    """Retrieve worklogs without query parameters."""
    response = requests.get(
        TEMPO_WORKLOGS_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {tempo_token}",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = response.text[:500].strip()
        raise RuntimeError(
            f"Tempo API antwortete mit HTTP {response.status_code}: {detail or error}"
        ) from error

    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Unerwartetes Antwortformat: erwartetes JSON-Objekt fehlt.")
    return data


def get_author_account_id(worklog: dict[str, Any]) -> str | None:
    author = worklog.get("author")
    if not isinstance(author, dict):
        return None

    account_id = author.get("accountId")
    return str(account_id) if account_id else None


def resolve_author_names(
    account_ids: set[str], atlassian_user: str, atlassian_api_token: str
) -> dict[str, str]:
    """Resolve Jira display names once for each distinct Tempo author."""
    names: dict[str, str] = {}
    for account_id in account_ids:
        try:
            response = requests.get(
                f"{ATLASSIAN_BASE_URL}/rest/api/3/user",
                headers={"Accept": "application/json"},
                auth=(atlassian_user, atlassian_api_token),
                params={"accountId": account_id},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            user = response.json()
        except requests.RequestException as error:
            status_code = error.response.status_code if error.response is not None else "?"
            detail = error.response.text[:200].strip() if error.response is not None else ""
            names[account_id] = (
                f"<nicht auflösbar: HTTP {status_code}"
                f"{f' – {detail}' if detail else f' – {error}'}>"
            )
            continue
        except ValueError as error:
            detail = response.text[:200].strip()
            names[account_id] = (
                f"<nicht auflösbar: HTTP {response.status_code}"
                f"{f' – {detail}' if detail else f' – {error}'}>"
            )
            continue

        if not isinstance(user, dict):
            names[account_id] = "<nicht auflösbar: unerwartete Jira-Antwort>"
            continue
        names[account_id] = str(user.get("displayName") or "<ohne Anzeigename>")
    return names


def format_worklog(worklog: dict[str, Any], author_names: dict[str, str]) -> str:
    issue = worklog.get("issue") or {}
    issue_id = issue.get("id") if isinstance(issue, dict) else None
    author = worklog.get("author")
    author_output = json.dumps(author, ensure_ascii=False) if author is not None else "<ohne Author>"
    author_account_id = get_author_account_id(worklog)
    author_name = author_names.get(author_account_id, "<ohne accountId>") if author_account_id else "<ohne accountId>"
    return (
        f"{worklog.get('tempoWorklogId', '<ohne Tempo-Worklog-ID>')} | "
        f"{worklog.get('startDate', '<ohne Startdatum>')} | "
        f"{issue_id or '<ohne Issue-ID>'} | "
        f"{worklog.get('timeSpentSeconds', '<ohne Dauer>')} Sekunden | "
        f"Author: {author_name} | Author-Rohdaten: {author_output}"
    )


def get_issue_id(worklog: dict[str, Any]) -> str:
    issue = worklog.get("issue")
    if not isinstance(issue, dict) or not issue.get("id"):
        return "<ohne Issue-ID>"
    return str(issue["id"])


def resolve_issue_labels(
    issue_ids: set[str], atlassian_user: str, atlassian_api_token: str
) -> dict[str, str]:
    """Resolve Jira issue keys and summaries once for each distinct issue."""
    labels: dict[str, str] = {}
    for issue_id in issue_ids:
        if issue_id == "<ohne Issue-ID>":
            labels[issue_id] = issue_id
            continue

        try:
            response = requests.get(
                f"{ATLASSIAN_BASE_URL}/rest/api/3/issue/{issue_id}",
                headers={"Accept": "application/json"},
                auth=(atlassian_user, atlassian_api_token),
                params={"fields": "summary"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            issue = response.json()
        except requests.RequestException as error:
            status_code = error.response.status_code if error.response is not None else "?"
            labels[issue_id] = f"{issue_id} – <nicht auflösbar: HTTP {status_code}>"
            continue
        except ValueError:
            labels[issue_id] = f"{issue_id} – <nicht auflösbar: ungültige Jira-Antwort>"
            continue

        if not isinstance(issue, dict):
            labels[issue_id] = f"{issue_id} – <nicht auflösbar: unerwartete Jira-Antwort>"
            continue

        key = str(issue.get("key") or issue_id)
        fields = issue.get("fields") or {}
        summary = fields.get("summary") if isinstance(fields, dict) else None
        labels[issue_id] = f"{key} – {summary or '<ohne Summary>'}"
    return labels


def get_worklog_duration_seconds(worklog: dict[str, Any]) -> int:
    duration = worklog.get("timeSpentSeconds", 0)
    try:
        return int(duration)
    except (TypeError, ValueError):
        return 0


def format_duration(seconds: int) -> str:
    """Render a duration as hours and minutes for the compact PDF table."""
    hours, remaining_seconds = divmod(seconds, 3600)
    minutes = remaining_seconds // 60
    return f"{hours}:{minutes:02d}"


def aggregate_current_month_worklogs(
    worklogs: list[Any], current_date: date
) -> dict[str, dict[date, int]]:
    """Sum valid worklogs by Jira issue and day in the current month."""
    totals: dict[str, dict[date, int]] = {}
    for worklog in worklogs:
        if not isinstance(worklog, dict):
            continue

        start_date = worklog.get("startDate")
        if not isinstance(start_date, str):
            continue
        try:
            worklog_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        if worklog_date.year != current_date.year or worklog_date.month != current_date.month:
            continue

        issue_id = get_issue_id(worklog)
        issue_totals = totals.setdefault(issue_id, {})
        issue_totals[worklog_date] = (
            issue_totals.get(worklog_date, 0) + get_worklog_duration_seconds(worklog)
        )
    return totals


def create_monthly_pdf_report(
    worklogs: list[Any], current_date: date, issue_labels: dict[str, str]
) -> Path:
    """Create a landscape A3 report with daily Tempo effort per Jira issue."""
    days_in_month = monthrange(current_date.year, current_date.month)[1]
    month_days = [date(current_date.year, current_date.month, day) for day in range(1, days_in_month + 1)]
    worklogs_by_issue = aggregate_current_month_worklogs(worklogs, current_date)
    has_no_bookings = not worklogs_by_issue

    report_path = REPORTS_DIRECTORY / (
        f"tempo-worklogs-{current_date.year}-{current_date.month:02d}.pdf"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    page_size = landscape(A3)
    left_margin = 15 * mm
    right_margin = 15 * mm
    document = SimpleDocTemplate(
        str(report_path),
        pagesize=page_size,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    month_title = f"{GERMAN_MONTH_NAMES[current_date.month - 1]} {current_date.year}"
    styles = getSampleStyleSheet()
    story = [Paragraph(month_title, styles["Title"]), Spacer(1, 6 * mm)]

    header = ["Jira-Issue", *(f"{day.day}." for day in month_days), "Summe"]
    issue_style = styles["BodyText"].clone("IssueLabel")
    issue_style.fontSize = 7
    issue_style.leading = 8
    table_data: list[list[Any]] = [header]
    for issue_id in sorted(worklogs_by_issue):
        daily_totals = worklogs_by_issue[issue_id]
        issue_label = issue_labels.get(issue_id, issue_id)
        row: list[Any] = [Paragraph(escape(issue_label), issue_style)]
        row.extend(
            format_duration(daily_totals[day]) if day in daily_totals else "–"
            for day in month_days
        )
        row.append(format_duration(sum(daily_totals.values())))
        table_data.append(row)

    if has_no_bookings:
        table_data.append(["Keine Buchungen im aktuellen Monat.", *([""] * (len(header) - 1))])

    available_width = page_size[0] - left_margin - right_margin
    issue_column_width = 60 * mm
    total_column_width = 18 * mm
    day_column_width = (available_width - issue_column_width - total_column_width) / days_in_month
    table = Table(
        table_data,
        colWidths=[issue_column_width, *([day_column_width] * days_in_month), total_column_width],
        repeatRows=1,
    )
    style_commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#A6A6A6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if has_no_bookings:
        style_commands.append(("SPAN", (0, 1), (-1, 1)))
        style_commands.append(("ALIGN", (0, 1), (-1, 1), "LEFT"))
    table.setStyle(TableStyle(style_commands))
    story.append(table)
    document.build(story)
    return report_path


def main() -> int:
    try:
        data = retrieve_worklogs(get_required_environment_variable("TEMPO_TOKEN"))
        atlassian_user = get_required_environment_variable("ATLASSIAN_USER")
        atlassian_api_token = get_required_environment_variable("ATLASSIAN_API_TOKEN")
    except (requests.RequestException, RuntimeError, ValueError) as error:
        print(f"Fehler beim Tempo-API-Zugriff: {error}", file=sys.stderr)
        return 1

    worklogs = data.get("results")
    metadata = data.get("metadata") or {}
    if not isinstance(worklogs, list):
        print("Fehler: Die API-Antwort enthält kein 'results'-Array.", file=sys.stderr)
        return 1

    print(
        "Tempo API-Zugriff erfolgreich. "
        f"{len(worklogs)} Worklog(s) empfangen "
        f"(Offset: {metadata.get('offset', 'unbekannt')}, "
        f"Limit: {metadata.get('limit', 'unbekannt')}, "
        f"Gesamt: {metadata.get('count', 'unbekannt')})."
    )
    author_account_ids = {
        account_id
        for worklog in worklogs
        if isinstance(worklog, dict)
        if (account_id := get_author_account_id(worklog))
    }
    author_names = resolve_author_names(author_account_ids, atlassian_user, atlassian_api_token)

    for worklog in worklogs:
        if isinstance(worklog, dict):
            print(format_worklog(worklog, author_names))

    current_date = date.today()
    current_month_worklogs = aggregate_current_month_worklogs(worklogs, current_date)
    issue_labels = resolve_issue_labels(
        set(current_month_worklogs), atlassian_user, atlassian_api_token
    )
    try:
        report_path = create_monthly_pdf_report(worklogs, current_date, issue_labels)
    except (OSError, ValueError) as error:
        print(f"Fehler beim Erstellen des PDF-Reports: {error}", file=sys.stderr)
        return 1
    print(f"PDF-Report erstellt: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
