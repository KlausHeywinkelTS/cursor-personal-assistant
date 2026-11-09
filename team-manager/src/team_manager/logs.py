"""Strukturierte Logs (eine JSON-Zeile pro Ereignis)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD:
                entry[key] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Logs nach stderr; ohne Konsole (pythonw/Autostart) oder mit log_file in eine rotierende Datei."""
    if log_file is None and sys.stderr is not None:
        handler: logging.Handler = logging.StreamHandler(sys.stderr)
    else:
        log_file = log_file or Path.home() / ".team-manager" / "service.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("team_manager")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
