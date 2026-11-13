"""Erstellt aus der Rohdatei eines Teams-Exports die Report-Datei für einen Zeitraum.

Enthalten sind alle Hauptpostings, deren Erstellzeit (Europa/Berlin) im Zeitraum liegt,
mit allen ihren Replies. Postings ohne Text bleiben hier drin, sie entfernt
src/cvu_export_aufbereiten.py im nächsten Schritt.

Zeitraum (genau eines):
    --zeitraum "letzte Woche"          letzte vollständig abgeschlossene Woche (Mo–So)
    --zeitraum "letzte zwei Wochen"    die letzten N vollständig abgeschlossenen Wochen
    --zeitraum "letzter Monat"         letzter vollständig abgeschlossener Kalendermonat
    --month 2026-10                    ein Kalendermonat
    --from 2026-10-26 --to 2026-11-08  freier Zeitraum, beide Tage inklusive

Mit --heute YYYY-MM-DD lässt sich „heute“ festlegen (Tests, Nachholen).

Aufrufe:
    py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --zeitraum "letzte Woche"
    py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --month 2026-10
    py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --from 2026-10-26 --to 2026-11-08 --output reports/x.json

Exit-Code 0 = geschrieben, 1 = Fehler (z. B. Export reicht nicht bis zum Zeitraumbeginn).
"""

import argparse
import calendar
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
CHANNEL_LABEL = "Teams > Allgemein (Trusted Shops)"
REPO_ROOT = Path(__file__).resolve().parent.parent

NUMBER_WORDS = {
    "eine": 1, "einen": 1, "einer": 1, "ein": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8,
}


# --- Zeitraum ---------------------------------------------------------------

def last_completed_week_end(today: date) -> date:
    """Sonntag der letzten vollständig abgeschlossenen Woche (Mo–So)."""
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=1)


def resolve_zeitraum(text: str, today: date) -> tuple[date, date, str]:
    t = " ".join(text.strip().lower().split())

    if re.fullmatch(r"(letzte[rn]?|vergangene[rn]?|vorige[rn]?)\s+woche", t):
        n = 1
    else:
        m = re.fullmatch(r"(letzte[rn]?|vergangene[rn]?|vorige[rn]?)\s+(\w+)\s+wochen?", t)
        if m:
            word = m.group(2)
            if word.isdigit():
                n = int(word)
            elif word in NUMBER_WORDS:
                n = NUMBER_WORDS[word]
            else:
                raise ValueError(f"Anzahl Wochen nicht erkannt: '{word}'")
        else:
            if re.fullmatch(r"(letzte[rn]?|vergangene[rn]?|vorige[rn]?)\s+monat", t):
                first_this = today.replace(day=1)
                last_prev = first_this - timedelta(days=1)
                first_prev = last_prev.replace(day=1)
                return first_prev, last_prev, "letzter Monat"
            raise ValueError(f"Zeitraum nicht erkannt: '{text}'")

    end = last_completed_week_end(today)
    start = end - timedelta(days=7 * n - 1)
    label = "letzte Woche" if n == 1 else f"letzte {n} Wochen"
    return start, end, label


def month_range(month: str) -> tuple[date, date]:
    year, mon = (int(x) for x in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


# --- Zeitstempel ------------------------------------------------------------

def parse_utc(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)(.*)$", s)
    if m:
        s = f"{m.group(1)}.{(m.group(2) + '000000')[:6]}{m.group(3)}"
    return datetime.fromisoformat(s)


def to_local(s: str) -> datetime:
    return parse_utc(s).astimezone(TZ)


def iso_local(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def local_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=TZ)


# --- Report -----------------------------------------------------------------

def build_report(raw: list[dict], start: date, end: date, label: str, raw_path: Path) -> dict:
    lo, hi = local_start(start), local_start(end + timedelta(days=1))
    postings = []
    for m in raw:
        if not m.get("created-at"):
            continue
        created = to_local(m["created-at"])
        if not (lo <= created < hi):
            continue
        replies = sorted(
            (
                {"created_at": iso_local(to_local(r["created-at"])), "text": r.get("reply-text")}
                for r in (m.get("replies") or [])
                if r.get("created-at")
            ),
            key=lambda r: r["created_at"],
        )
        postings.append({"created_at": iso_local(created), "text": m.get("msg"), "replies": replies})

    postings.sort(key=lambda p: p["created_at"])
    return {
        "meta": {
            "channel": CHANNEL_LABEL,
            "zeitraum": label,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "timezone": "Europe/Berlin",
            "selection": f"Hauptpostings mit created_at im Zeitraum {start.isoformat()} bis {end.isoformat()}; alle Replies dieser Postings",
            "source_export": str(raw_path),
            "exported_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "postings_count": len(postings),
            "replies_count": sum(len(p["replies"]) for p in postings),
            "note": "Export ist anonym: keine Absenderinformationen.",
        },
        "postings": postings,
    }


def default_output(start: date, end: date) -> Path:
    if start.day == 1 and end == month_range(start.strftime("%Y-%m"))[1]:
        name = f"cvu-export-{start.strftime('%Y-%m')}.json"
    else:
        name = f"cvu-export-{start.isoformat()}_bis_{end.isoformat()}.json"
    return REPO_ROOT / "reports" / name


# --- CLI --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Report-JSON für einen Zeitraum aus der Teams-Rohdatei erstellen.")
    parser.add_argument("--raw", type=Path, required=True, help="Rohdatei des Teams-Exports")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zeitraum", help='z. B. "letzte Woche", "letzte zwei Wochen", "letzter Monat"')
    group.add_argument("--month", help="Kalendermonat YYYY-MM")
    group.add_argument("--from", dest="date_from", help="Beginn YYYY-MM-DD (zusammen mit --to)")
    parser.add_argument("--to", dest="date_to", help="Ende YYYY-MM-DD, inklusive (zusammen mit --from)")
    parser.add_argument("--heute", help="Bezugsdatum YYYY-MM-DD statt heute (für Tests)")
    parser.add_argument("--output", type=Path, help="Zieldatei (Standard: reports/cvu-export-…json)")
    args = parser.parse_args()

    if args.date_from and not args.date_to or args.date_to and not args.date_from:
        print("Fehler: --from und --to gehören zusammen.", file=sys.stderr)
        return 1

    try:
        today = date.fromisoformat(args.heute) if args.heute else datetime.now(TZ).date()
        if args.zeitraum:
            start, end, label = resolve_zeitraum(args.zeitraum, today)
        elif args.month:
            start, end = month_range(args.month)
            label = args.month
        else:
            start, end = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)
            label = f"{start.isoformat()} bis {end.isoformat()}"
    except ValueError as exc:
        print(f"Fehler beim Zeitraum: {exc}", file=sys.stderr)
        return 1

    if start > end:
        print(f"Fehler: Beginn {start} liegt nach Ende {end}.", file=sys.stderr)
        return 1

    try:
        raw = json.loads(args.raw.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Fehler beim Lesen der Rohdatei: {exc}", file=sys.stderr)
        return 1
    if not isinstance(raw, list):
        print("Fehler: Rohdatei ist keine Liste von Nachrichten.", file=sys.stderr)
        return 1

    timestamps = [to_local(m["created-at"]) for m in raw if m.get("created-at")]
    if not timestamps:
        print("Fehler: Rohdatei enthält keine Zeitstempel.", file=sys.stderr)
        return 1

    earliest = min(timestamps)
    if earliest > local_start(start):
        print(
            f"Fehler: Der Export reicht nur bis {iso_local(earliest)}, der Zeitraum beginnt aber am "
            f"{start.isoformat()}. Mit mehr Loops neu exportieren.",
            file=sys.stderr,
        )
        return 1

    report = build_report(raw, start, end, label, args.raw)
    output = args.output or default_output(start, end)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Zeitraum:                    {label} ({start.isoformat()} bis {end.isoformat()})")
    print(f"Geschrieben:                 {output}")
    print(f"Älteste Nachricht im Export: {iso_local(earliest)}")
    print(f"Hauptpostings im Zeitraum:   {report['meta']['postings_count']}")
    print(f"Replies dazu:                {report['meta']['replies_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
