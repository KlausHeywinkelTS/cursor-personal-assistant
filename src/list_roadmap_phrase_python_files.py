r"""Find configured phrases in Python files below one or more directories.

The default scan covers the user's Dev and AI-Agent directory trees and writes
a Markdown report with matching file names, line numbers, and source excerpts.

Usage:
    py src/list_roadmap_phrase_python_files.py
    py src/list_roadmap_phrase_python_files.py --root C:\Projects
    py src/list_roadmap_phrase_python_files.py --term "another phrase"
    py src/list_roadmap_phrase_python_files.py --output reports/custom-report.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tokenize
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOTS = (
    Path(r"C:\Users\Kl6713\Dev"),
    Path(r"C:\Users\Kl6713\AI-Agent"),
)
DEFAULT_TERMS = (
    "relevant" + " for " + "roadmap",
    "customfield_10112",
)
MAX_SNIPPET_LENGTH = 300


@dataclass(frozen=True)
class SourceReference:
    line_number: int
    occurrence_count: int
    snippet: str


@dataclass(frozen=True)
class FileMatch:
    path: Path
    references: tuple[SourceReference, ...]

    @property
    def occurrence_count(self) -> int:
        return sum(reference.occurrence_count for reference in self.references)


@dataclass(frozen=True)
class ScanError:
    path: Path
    message: str


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _extended_path(path: Path) -> Path:
    """Use Windows' extended path syntax so deep dependency trees remain readable."""
    absolute_path = os.path.abspath(path)
    if os.name != "nt" or absolute_path.startswith("\\\\?\\"):
        return Path(absolute_path)
    if absolute_path.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute_path[2:])
    return Path("\\\\?\\" + absolute_path)


def _display_path(path: Path) -> str:
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def discover_python_files(roots: list[Path]) -> tuple[list[Path], list[ScanError]]:
    """Return unique .py files below roots while retaining traversal errors."""
    discovered: dict[str, Path] = {}
    errors: list[ScanError] = []

    for root in roots:
        expanded_root = root.expanduser()
        if not expanded_root.exists():
            errors.append(ScanError(expanded_root, "Pfad existiert nicht."))
            continue
        if not expanded_root.is_dir():
            errors.append(ScanError(expanded_root, "Pfad ist kein Ordner."))
            continue

        walk_root = _extended_path(expanded_root)

        def record_walk_error(error: OSError) -> None:
            error_path = Path(error.filename) if error.filename else walk_root
            errors.append(ScanError(error_path, str(error)))

        for directory, directory_names, file_names in os.walk(
            walk_root, topdown=True, onerror=record_walk_error, followlinks=False
        ):
            directory_names.sort(key=str.casefold)
            for file_name in sorted(file_names, key=str.casefold):
                if not file_name.casefold().endswith(".py"):
                    continue
                path = Path(directory) / file_name
                discovered.setdefault(_path_key(path), path)

    files = sorted(
        discovered.values(), key=lambda path: _display_path(path).casefold()
    )
    return files, errors


def _shorten_line(line: str) -> str:
    text = line.rstrip("\r\n").strip()
    if len(text) <= MAX_SNIPPET_LENGTH:
        return text
    return text[: MAX_SNIPPET_LENGTH - 3] + "..."


def scan_file(
    path: Path, patterns: dict[str, re.Pattern[str]]
) -> dict[str, FileMatch]:
    """Read a Python source file and find matches for each configured phrase."""
    references_by_term: dict[str, list[SourceReference]] = {
        term: [] for term in patterns
    }
    with tokenize.open(path) as source_file:
        for line_number, line in enumerate(source_file, start=1):
            for term, pattern in patterns.items():
                occurrences = len(pattern.findall(line))
                if occurrences:
                    references_by_term[term].append(
                        SourceReference(
                            line_number=line_number,
                            occurrence_count=occurrences,
                            snippet=_shorten_line(line),
                        )
                    )
    return {
        term: FileMatch(path=path, references=tuple(references))
        for term, references in references_by_term.items()
        if references
    }


def scan_python_files(
    files: list[Path], terms: list[str]
) -> tuple[dict[str, list[FileMatch]], list[ScanError]]:
    patterns = {term: re.compile(re.escape(term), re.IGNORECASE) for term in terms}
    matches_by_term: dict[str, list[FileMatch]] = {term: [] for term in terms}
    errors: list[ScanError] = []

    for index, path in enumerate(files, start=1):
        if index == 1 or index % 100 == 0 or index == len(files):
            print(f"  [{index}/{len(files)}] {_display_path(path)}")
        try:
            matches = scan_file(path, patterns)
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(ScanError(path, str(exc)))
            continue
        for term, match in matches.items():
            matches_by_term[term].append(match)

    for matches in matches_by_term.values():
        matches.sort(key=lambda match: _display_path(match.path).casefold())
    errors.sort(key=lambda error: _display_path(error.path).casefold())
    return matches_by_term, errors


def _escape_pipe(text: str) -> str:
    return text.replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def _escape_inline_code(text: str) -> str:
    return text.replace("`", "'")


def build_markdown(
    roots: list[Path],
    terms: list[str],
    matches_by_term: dict[str, list[FileMatch]],
    errors: list[ScanError],
    total_scanned: int,
) -> str:
    generated_at = (
        datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    )
    lines: list[str] = [
        "# Python-Dateien mit Roadmap-Feldreferenzen",
        "",
        f"_Generiert: {generated_at}_",
        "",
        (
            f"Durchsucht: {total_scanned} Python-Dateien nach {len(terms)} "
            f"Zeichenfolgen. Nicht vollständig prüfbar: {len(errors)} Pfade."
        ),
        "",
        "Die Suche ignoriert Groß-/Kleinschreibung.",
        "",
        "## Ergebnisübersicht",
        "",
        "| Zeichenfolge | Dateien | Vorkommen |",
        "| --- | ---: | ---: |",
    ]
    for term in terms:
        matches = matches_by_term[term]
        occurrences = sum(match.occurrence_count for match in matches)
        lines.append(
            f"| `{_escape_pipe(_escape_inline_code(term))}` | {len(matches)} | "
            f"{occurrences} |"
        )
    lines.extend(
        [
            "",
            "## Durchsuchte Stammordner",
            "",
        ]
    )
    lines.extend(
        f"- `{_escape_inline_code(str(root.expanduser()))}`" for root in roots
    )
    lines.append("")

    for term in terms:
        matches = matches_by_term[term]
        lines.extend(
            [
                f'## Ergebnisse für "{term}"',
                "",
            ]
        )
        if not matches:
            lines.extend(
                [
                    "_Keine Python-Datei mit dieser Zeichenfolge gefunden._",
                    "",
                ]
            )
            continue

        lines.extend(
            [
                "| Python-Datei | Zeilen | Vorkommen |",
                "| --- | ---: | ---: |",
            ]
        )
        for match in matches:
            path = _escape_pipe(_escape_inline_code(_display_path(match.path)))
            lines.append(
                f"| `{path}` | {len(match.references)} | {match.occurrence_count} |"
            )
        lines.extend(["", f'### Details für "{term}"', ""])

        for match in matches:
            path = _escape_inline_code(_display_path(match.path))
            lines.extend(
                [
                    f'#### `{path}` für "{term}"',
                    "",
                    f"- **Vorkommen:** {match.occurrence_count}",
                    f"- **Betroffene Zeilen:** {len(match.references)}",
                    "",
                ]
            )
            for reference in match.references:
                snippet = _escape_inline_code(reference.snippet)
                suffix = (
                    f" ({reference.occurrence_count} Vorkommen)"
                    if reference.occurrence_count > 1
                    else ""
                )
                lines.append(
                    f"- Zeile {reference.line_number}{suffix}: `{snippet}`"
                )
            lines.append("")
    if errors:
        lines.extend(
            [
                "## Nicht vollständig geprüfte Pfade",
                "",
                (
                    "Diese Pfade konnten nicht gelesen oder durchsucht werden. "
                    "Das Ergebnis ist dort daher nicht vollständig."
                ),
                "",
            ]
        )
        for error in errors:
            path = _escape_inline_code(_display_path(error.path))
            message = _escape_pipe(_escape_inline_code(error.message))
            lines.append(f"- `{path}`: {message}")
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search recursively through Python files and write matching source "
            "locations to a Markdown report."
        )
    )
    parser.add_argument(
        "--root",
        action="append",
        default=None,
        help=(
            "Root directory to scan. May be supplied more than once. "
            "Defaults to the configured Dev and AI-Agent directories."
        ),
    )
    parser.add_argument(
        "--term",
        action="append",
        default=None,
        help=(
            "Additional case-insensitive search phrase. May be supplied more "
            "than once; the two default Roadmap phrases are always included."
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Output Markdown path "
            "(default: reports/python-files-relevant-for-roadmap-<date>.md)"
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
    roots = [Path(root) for root in args.root] if args.root else list(DEFAULT_ROOTS)
    terms = list(DEFAULT_TERMS)
    for term in args.term or []:
        if not term:
            raise ValueError("Search phrase must not be empty.")
        if term.casefold() not in {known_term.casefold() for known_term in terms}:
            terms.append(term)

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = (
        args.output or f"reports/python-files-relevant-for-roadmap-{today}.md"
    )

    print("Discovering Python files ...")
    files, discovery_errors = discover_python_files(roots)
    print(f"  -> {len(files)} Python file(s) found")

    print(f"Checking Python files for: {', '.join(repr(term) for term in terms)} ...")
    matches_by_term, scan_errors = scan_python_files(files, terms)
    errors = sorted(
        [*discovery_errors, *scan_errors],
        key=lambda error: _display_path(error.path).casefold(),
    )
    for term in terms:
        matches = matches_by_term[term]
        occurrence_count = sum(match.occurrence_count for match in matches)
        print(
            f'  -> "{term}": {len(matches)} matching file(s), '
            f"{occurrence_count} occurrence(s)"
        )
    print(f"  -> {len(errors)} error(s)")

    markdown = build_markdown(
        roots=roots,
        terms=terms,
        matches_by_term=matches_by_term,
        errors=errors,
        total_scanned=len(files),
    )
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8", newline="\n")
    print(f"\nMarkdown written to: {output_file}")


if __name__ == "__main__":
    main()
