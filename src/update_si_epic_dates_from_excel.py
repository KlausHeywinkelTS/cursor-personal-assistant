"""Traegt Start Date / End Date aus REQ_DEL_RAID_JIRA_with_Dates.xlsx in die bereits angelegten SI-Epics ein.

Matching: Excel-ID (Tab REQ: "ID", Tab DEL: "DEL ID") -> Jira-Key aus cache/si_epic_import_state.json.
Mapping:  "Start Date" -> Jira "Start date" (customfield_10015) | "End Date" -> Jira "Due date" (duedate).

Dry-Run (Standard): liest die aktuellen Werte aus Jira und zeigt pro Epic die geplante Aenderung.
Es wird nichts geschrieben.

    py src/update_si_epic_dates_from_excel.py                    # Dry-Run, 3 Zeilen je Tab
    py src/update_si_epic_dates_from_excel.py --rows 10          # Dry-Run, 10 Zeilen je Tab
    py src/update_si_epic_dates_from_excel.py --sheet DEL --rows 5

Ausfuehren (schreibt nur Epics, deren Werte sich unterscheiden - wiederholbar):

    py src/update_si_epic_dates_from_excel.py --execute --rows 2   # Testlauf mit 2 Zeilen je Tab
    py src/update_si_epic_dates_from_excel.py --execute            # alles

Credentials: Umgebungsvariablen ATLASSIAN_USER und ATLASSIAN_TOKEN.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from rich import box
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from import_si_epics_from_excel import DEFAULT_STATE, SHEETS, Jira, JiraError, clean, load_state

DEFAULT_XLSX = Path("tmp/REQ_DEL_RAID_JIRA_with_Dates.xlsx")
DEFAULT_DRY_RUN_ROWS = 3

START_COL = "Start Date"
END_COL = "End Date"
START_FIELD = "customfield_10015"  # Jira "Start date"
DUE_FIELD = "duedate"


@dataclass
class DateRow:
    sheet: str
    excel_row: int
    item_id: str
    start: date | None
    end: date | None


# ---------------------------------------------------------------------------
# Excel einlesen (rein, ohne Jira)
# ---------------------------------------------------------------------------

def parse_date(value: Any, *, label: str) -> date | None:
    if value is None or clean(value) == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{label}: '{text}' ist kein Datum")


def read_date_rows(xlsx: Path, sheet: str) -> list[DateRow]:
    spec = SHEETS[sheet]
    workbook = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    try:
        rows = list(workbook[sheet].iter_rows(values_only=True))
    finally:
        workbook.close()
    header = [clean(h) for h in rows[0]]
    for name in (spec.id_col, START_COL, END_COL):
        if name not in header:
            raise SystemExit(f"Tab {sheet}: Spalte '{name}' nicht gefunden. Vorhanden: {header}")
    id_idx, start_idx, end_idx = (header.index(n) for n in (spec.id_col, START_COL, END_COL))

    result: list[DateRow] = []
    for number, row in enumerate(rows[1:], start=2):
        item_id = clean(row[id_idx])
        if not item_id:
            continue
        result.append(DateRow(
            sheet=sheet,
            excel_row=number,
            item_id=item_id,
            start=parse_date(row[start_idx], label=f"{item_id} {START_COL}"),
            end=parse_date(row[end_idx], label=f"{item_id} {END_COL}"),
        ))
    return result


# ---------------------------------------------------------------------------
# Planung (rein)
# ---------------------------------------------------------------------------

def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def build_fields(row: DateRow, current: dict[str, str | None]) -> dict[str, str | None]:
    """Nur Felder, die sich vom aktuellen Jira-Wert unterscheiden. Leere Excel-Zellen loeschen nichts."""
    wanted = {START_FIELD: iso(row.start), DUE_FIELD: iso(row.end)}
    return {f: v for f, v in wanted.items() if v is not None and current.get(f) != v}


def problem_for(row: DateRow, key: str | None) -> str | None:
    if not key:
        return "kein Jira-Key im State (Epic nicht angelegt?)"
    if row.start and row.end and row.end < row.start:
        return f"End Date {row.end} liegt vor Start Date {row.start}"
    return None


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------

class DateJira(Jira):
    def current_dates(self, keys: list[str]) -> dict[str, dict[str, str | None]]:
        found: dict[str, dict[str, str | None]] = {}
        for start in range(0, len(keys), 50):
            chunk = keys[start:start + 50]
            for issue in self.search(f"key in ({','.join(chunk)})", [START_FIELD, DUE_FIELD]):
                fields = issue["fields"]
                found[issue["key"]] = {START_FIELD: fields.get(START_FIELD), DUE_FIELD: fields.get(DUE_FIELD)}
        return found

    def update_fields(self, key: str, fields: dict[str, Any]) -> None:
        self._request("PUT", f"/rest/api/3/issue/{key}", json={"fields": fields})


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    row: DateRow
    key: str | None
    current: dict[str, str | None] | None
    changes: dict[str, str | None]
    problem: str | None


def make_plans(rows: list[DateRow], state: dict[str, Any], jira: DateJira) -> list[Plan]:
    keys = {r.item_id: state["epics"].get(r.item_id, {}).get("key") for r in rows}
    current = jira.current_dates([k for k in keys.values() if k])
    plans: list[Plan] = []
    for row in rows:
        key = keys[row.item_id]
        problem = problem_for(row, key)
        if not problem and key not in current:
            problem = f"{key} in Jira nicht gefunden (oder keine Berechtigung)"
        cur = current.get(key) if key else None
        changes = build_fields(row, cur) if cur is not None and not problem else {}
        plans.append(Plan(row, key, cur, changes, problem))
    return plans


def render_plans(console: Console, plans: list[Plan]) -> None:
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False)
    for column in ("Tab", "Zeile", "ID", "Key", "Start Date (Jira -> Excel)", "Due Date (Jira -> Excel)", "Ergebnis"):
        table.add_column(column)
    for plan in plans:
        row, cur = plan.row, plan.current or {}
        if plan.problem:
            result = Text(plan.problem, style="bold red")
        elif plan.changes:
            result = Text("wird aktualisiert", style="bold green")
        else:
            result = Text("unveraendert", style="dim")
        table.add_row(
            row.sheet, str(row.excel_row), row.item_id, plan.key or "-",
            f"{cur.get(START_FIELD) or '-'} -> {iso(row.start) or '-'}",
            f"{cur.get(DUE_FIELD) or '-'} -> {iso(row.end) or '-'}",
            result,
        )
    console.print(table)


def summarize(plans: list[Plan]) -> tuple[int, int, int]:
    problems = sum(1 for p in plans if p.problem)
    changes = sum(1 for p in plans if p.changes)
    return changes, len(plans) - changes - problems, problems


def run(console: Console, jira: DateJira, plans: list[Plan], *, execute: bool, assume_yes: bool) -> int:
    render_plans(console, plans)
    changes, unchanged, problems = summarize(plans)
    console.print(f"Zu aendern: [bold]{changes}[/bold], unveraendert: {unchanged}, Probleme: {problems}")

    if not execute:
        console.print(Rule(style="yellow"))
        console.print("[bold yellow]Dry-Run beendet.[/bold yellow] Mit [bold]--execute[/bold] tatsaechlich schreiben.")
        return 1 if problems else 0

    todo = [p for p in plans if p.changes]
    if not todo:
        console.print("Nichts zu tun.")
        return 1 if problems else 0
    if not assume_yes and input(f"{len(todo)} Epics in Jira aktualisieren? [j/N] ").strip().casefold() not in {"j", "ja", "y", "yes"}:
        console.print("Abgebrochen.")
        return 1

    errors: list[str] = []
    for plan in todo:
        try:
            jira.update_fields(plan.key, plan.changes)  # type: ignore[arg-type]
            console.print(f"[green]+[/green] {plan.row.item_id} -> [bold]{plan.key}[/bold]  {plan.changes}")
        except JiraError as exc:
            errors.append(f"{plan.row.item_id} ({plan.key}): {exc}")
            console.print(f"[bold red]![/bold red] {plan.row.item_id} ({plan.key}): {exc}")
    console.print(Rule("[bold]Fertig[/bold]"))
    console.print(f"Aktualisiert: {len(todo) - len(errors)}, Fehler: {len(errors)}, Probleme (uebersprungen): {problems}")
    return 1 if errors or problems else 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Start-/Due-Date aus Excel in bereits angelegte SI-Epics eintragen")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--sheet", choices=["all", *SHEETS], default="all", help="Tab waehlen (Standard: beide)")
    parser.add_argument("--rows", type=int, default=None,
                        help=f"Anzahl Zeilen je Tab (Dry-Run Standard: {DEFAULT_DRY_RUN_ROWS}, --execute Standard: alle)")
    parser.add_argument("--execute", action="store_true", help="Tatsaechlich in Jira schreiben (ohne Flag: Dry-Run)")
    parser.add_argument("--yes", action="store_true", help="Rueckfrage vor --execute ueberspringen")
    args = parser.parse_args()

    console = Console(highlight=False)
    if not args.state_file.is_file():
        raise SystemExit(f"State-Datei {args.state_file} fehlt - ohne sie gibt es kein ID -> Key Mapping.")
    state = load_state(args.state_file)

    limit = args.rows if args.rows is not None else (None if args.execute else DEFAULT_DRY_RUN_ROWS)
    rows: list[DateRow] = []
    for sheet in (SHEETS if args.sheet == "all" else [args.sheet]):
        sheet_rows = read_date_rows(args.xlsx, sheet)
        rows.extend(sheet_rows[:limit] if limit is not None else sheet_rows)

    if not args.execute:
        console.print(Rule("[bold]DRY-RUN[/bold] - es wird nichts in Jira geschrieben", style="yellow"))
    jira = DateJira()
    plans = make_plans(rows, state, jira)
    return run(console, jira, plans, execute=args.execute, assume_yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
