"""Rename the daily journal header "## Manueller Inhalt" to "## Reflektion: Mein Tag heute".

One-off migration for existing journal files. Only the exact header line is
replaced; free-text occurrences of the phrase are left untouched. Idempotent:
files without the old header are skipped.

Usage:
    py src/migrate_journal_manual_header.py
    py src/migrate_journal_manual_header.py --journal-dir journal
"""

from __future__ import annotations

import argparse
from pathlib import Path

OLD_HEADER_LINE = "## Manueller Inhalt"
NEW_HEADER_LINE = "## Reflektion: Mein Tag heute"


def _is_daily_journal_file(path: Path) -> bool:
    if path.parent.name in ("wochen-rueckschau", "monats-rueckschau"):
        return False
    return path.name.startswith("journal-") and path.suffix == ".md"


def migrate_file(path: Path) -> bool:
    """Replace the old header line in-place. Returns True if the file was changed."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    changed = False
    for index, line in enumerate(lines):
        if line.strip() == OLD_HEADER_LINE:
            lines[index] = NEW_HEADER_LINE
            changed = True
    if not changed:
        return False
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return True


def migrate_journal_dir(journal_dir: str) -> int:
    """Migrate all daily journal files under `journal_dir`. Returns count of changed files."""
    root = Path(journal_dir)
    changed_count = 0
    for path in sorted(root.glob("**/journal-*.md")):
        if not _is_daily_journal_file(path):
            continue
        if migrate_file(path):
            changed_count += 1
            print(f"Migriert: {path}")
    return changed_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rename "## Manueller Inhalt" to "## Reflektion: Mein Tag heute" in daily journals'
    )
    parser.add_argument(
        "--journal-dir",
        default="journal",
        help="Directory containing journal markdown files (default: journal)",
    )
    args = parser.parse_args()

    changed_count = migrate_journal_dir(args.journal_dir)
    print(f"Fertig: {changed_count} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
