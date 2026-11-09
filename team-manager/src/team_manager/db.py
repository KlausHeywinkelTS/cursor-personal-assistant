"""SQLite-Zugriff: eine Verbindung pro Operation, Schreibzugriffe mit BEGIN IMMEDIATE."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Serialisierte Schreibtransaktion: BEGIN IMMEDIATE sperrt andere Schreiber sofort aus."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
        finally:
            conn.close()

    def migrate(self) -> list[int]:
        """Wendet alle noch nicht angewendeten Migrationen an. Gibt die neu angewendeten Versionen zurück."""
        applied: list[int] = []
        with self.read() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            done = {row["version"] for row in conn.execute("SELECT version FROM schema_version")}
        for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            match = re.match(r"(\d+)_", file.name)
            if not match:
                continue
            version = int(match.group(1))
            if version in done:
                continue
            script = file.read_text(encoding="utf-8")
            conn = self._connect()
            try:
                conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + script
                    + f"\nINSERT INTO schema_version (version, applied_at) VALUES ({version}, '{now_iso()}');\nCOMMIT;"
                )
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
            applied.append(version)
        return applied
