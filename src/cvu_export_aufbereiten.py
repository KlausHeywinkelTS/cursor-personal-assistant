"""Aufbereitung einer CVU-Teams-Export-Datei (reports/cvu-export-YYYY-MM.json).

Deterministische Schritte:
1. Hauptpostings mit text = null entfernen (Reaktionen, Dateien) und meta-Zähler aktualisieren.
2. teams_link je Posting setzen. Die Message-ID ist die Erstellzeit in Millisekunden UTC.
   Die Millisekunden stehen nur in der Rohdatei des Exports, deshalb wird sie benötigt.
3. votes je Posting setzen: Anzahl der D-Nummern (Kundennummern wie D564431) im Hauptposting
   plus in allen Replies, als eine Summe.
4. Struktur der Felder product-response prüfen (Inhalt bewertet der Skill, nicht dieses Script).

Aufruf:
    py -B src/cvu_export_aufbereiten.py reports/cvu-export-2026-10.json --raw "<Pfad zur Rohdatei>"

Exit-Code 0 = alles ok, 1 = Fehler oder Prüfung fehlgeschlagen.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CHANNEL = "19:Cb34wC_FZkgoQKEx69-5e8CizMh4P1hY4OBqH7FIBVo1@thread.tacv2"
TENANT = "38e736cd-1e05-48a5-adeb-5ae85d3376ae"
GROUP = "4a1913cf-829b-4e64-9628-57cbb21b89e5"
TEAM_NAME = "Customer%20voice%20-%20uncensored"
CHANNEL_NAME = "General"

REQUIRED_PR_KEYS = ("replies", "reason", "sales_summary")

D_NUMBER = re.compile(r"\bD\d+\b")


def to_ms(s: str) -> int:
    """ISO-Zeitstempel (UTC, optional mit Bruchteilen) -> Epoch-Millisekunden."""
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)(.*)$", s)
    if m:
        s = f"{m.group(1)}.{(m.group(2) + '000000')[:6]}{m.group(3)}"
    dt = datetime.fromisoformat(s).astimezone(timezone.utc)
    return round(dt.timestamp() * 1000)


def teams_link(ms: int) -> str:
    return (
        f"https://teams.microsoft.com/l/message/{CHANNEL}/{ms}"
        f"?tenantId={TENANT}&groupId={GROUP}&parentMessageId={ms}"
        f"&teamName={TEAM_NAME}&channelName={CHANNEL_NAME}&createdTime={ms}"
    )


def remove_textless(report: dict) -> int:
    before = len(report["postings"])
    report["postings"] = [p for p in report["postings"] if p.get("text") is not None]
    return before - len(report["postings"])


def update_meta_counts(report: dict) -> None:
    report.setdefault("meta", {})
    report["meta"]["postings_count"] = len(report["postings"])
    report["meta"]["replies_count"] = sum(len(p.get("replies") or []) for p in report["postings"])


def set_links(report: dict, raw: list[dict]) -> None:
    by_second: dict[int, list[int]] = {}
    for m in raw:
        if not m.get("created-at"):
            continue
        ms = to_ms(m["created-at"])
        by_second.setdefault(ms // 1000, []).append(ms)

    for p in report["postings"]:
        sec = to_ms(p["created_at"]) // 1000
        candidates = by_second.get(sec, [])
        if len(candidates) != 1:
            raise ValueError(
                f"Posting {p['created_at']}: {len(candidates)} Treffer in der Rohdatei (erwartet 1)."
            )
        p["teams_link"] = teams_link(candidates[0])


def set_votes(report: dict) -> None:
    """votes = Anzahl D-Nummern (Kundennummern wie D564431) im Hauptposting plus allen seinen Replies."""
    for p in report["postings"]:
        texts = [p.get("text") or ""] + [r.get("text") or "" for r in (p.get("replies") or [])]
        p["votes"] = sum(len(D_NUMBER.findall(t)) for t in texts)


def check_product_response(report: dict) -> list[str]:
    problems = []
    for i, p in enumerate(report["postings"], 1):
        if "product-response" not in p:
            problems.append(f"#{i}: Feld product-response fehlt.")
            continue
        pr = p["product-response"]
        if pr is False:
            continue
        if not isinstance(pr, dict):
            problems.append(f"#{i}: product-response muss false oder ein Objekt sein.")
            continue
        for key in REQUIRED_PR_KEYS:
            if key not in pr:
                problems.append(f"#{i}: product-response.{key} fehlt.")
        replies = pr.get("replies", [])
        if not isinstance(replies, list) or not all(
            isinstance(r, int) and 1 <= r <= len(p.get("replies") or []) for r in replies
        ):
            problems.append(f"#{i}: product-response.replies enthält ungültige Reply-Nummern.")
        for key in ("reason", "sales_summary"):
            text = pr.get(key, "")
            if isinstance(text, str) and re.search(r"\bR\d+\b", text):
                problems.append(f"#{i}: product-response.{key} enthält R-Nummern (R1, R5 …).")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="CVU-Export aufbereiten: Null-Posts entfernen, Teams-Links setzen, Struktur prüfen.")
    parser.add_argument("report", type=Path, help="Report-JSON, z. B. reports/cvu-export-2026-10.json")
    parser.add_argument("--raw", type=Path, required=True, help="Rohdatei des Teams-Exports (enthält die Millisekunden)")
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        raw = json.loads(args.raw.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Fehler beim Lesen: {exc}", file=sys.stderr)
        return 1

    if not isinstance(report.get("postings"), list) or not isinstance(raw, list):
        print("Fehler: Erwartet 'postings' im Report und eine Liste in der Rohdatei.", file=sys.stderr)
        return 1

    removed = remove_textless(report)
    try:
        set_links(report, raw)
    except ValueError as exc:
        print(f"Fehler beim Setzen der Links: {exc}", file=sys.stderr)
        return 1
    update_meta_counts(report)
    set_votes(report)

    problems = check_product_response(report)

    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    pr_true = sum(1 for p in report["postings"] if isinstance(p.get("product-response"), dict))
    print(f"Datei:                    {args.report}")
    print(f"Entfernte Null-Posts:     {removed}")
    print(f"Postings jetzt:           {len(report['postings'])}")
    print(f"Replies jetzt:            {report['meta']['replies_count']}")
    print(f"Links gesetzt:            {sum(1 for p in report['postings'] if p.get('teams_link'))}")
    print(f"product-response (Objekt): {pr_true}")
    if problems:
        print("Prüfung fehlgeschlagen:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("Prüfung ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
