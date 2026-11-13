"""Statistik über einen Teams-Export (z. B. reports/cvu-export-2026-10.json).

Auswertung:
- Anzahl Main-Postings mit text ungleich null
- Davon: Anzahl Postings mit mehr als einem reply (absolut und in Prozent)

Aufruf:
    py src/cvu_export_stats.py reports/cvu-export-2026-10.json
"""

import argparse
import json
import sys
from pathlib import Path


def compute_stats(postings: list[dict]) -> dict:
    with_text = [p for p in postings if p.get("text") is not None]
    multi_reply = [p for p in with_text if len(p.get("replies") or []) > 1]

    total = len(with_text)
    multi = len(multi_reply)
    percent = (multi / total * 100) if total else 0.0

    return {
        "postings_total": len(postings),
        "postings_with_text": total,
        "postings_more_than_one_reply": multi,
        "percent_more_than_one_reply": percent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Statistik über eine Teams-Export-JSON.")
    parser.add_argument("file", type=Path, help="Pfad zur JSON-Datei (z. B. reports/cvu-export-2026-10.json)")
    args = parser.parse_args()

    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Fehler beim Lesen von {args.file}: {exc}", file=sys.stderr)
        return 1

    postings = data.get("postings")
    if not isinstance(postings, list):
        print(f"Fehler: In {args.file} fehlt das Array 'postings'.", file=sys.stderr)
        return 1

    stats = compute_stats(postings)

    print(f"Datei: {args.file}")
    print(f"Main-Postings gesamt:               {stats['postings_total']}")
    print(f"Main-Postings mit Text (ungleich null): {stats['postings_with_text']}")
    print(
        "Davon mit mehr als einem reply:     "
        f"{stats['postings_more_than_one_reply']} "
        f"({stats['percent_more_than_one_reply']:.1f} %)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
