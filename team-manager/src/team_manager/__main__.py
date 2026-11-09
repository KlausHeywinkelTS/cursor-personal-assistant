"""Start: py -m team_manager   (Standard: http://127.0.0.1:48765)"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app
from .config import DEFAULT_PORT, Settings
from .logs import configure_logging


def port_in_use(port: int) -> bool:
    """True, wenn auf 127.0.0.1:port bereits etwas lauscht (zum Beispiel ein laufender Dienst)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def open_browser_when_ready(port: int, timeout_s: float = 15.0) -> None:
    """Wartet im Hintergrund, bis der Port lauscht, und öffnet dann das Cockpit im Standardbrowser."""

    def _run() -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if port_in_use(port):
                webbrowser.open(f"http://127.0.0.1:{port}/")
                return
            time.sleep(0.25)

    threading.Thread(target=_run, name="open-browser", daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(prog="team_manager", description="Team-Manager für Claude-Code-Agenten")
    parser.add_argument("--port", type=int, help=f"Port (Standard {DEFAULT_PORT})")
    parser.add_argument("--home", type=Path, help="Datenverzeichnis (Standard ~/.team-manager)")
    parser.add_argument("--agents-dir", type=Path, help="Verzeichnis der Agentenprofile (Standard ~/.claude/agents)")
    parser.add_argument("--skip-if-running", action="store_true",
                        help="Beenden ohne Fehler, wenn der Port schon belegt ist (für den automatischen Start aus VS Code)")
    parser.add_argument("--open-browser", action="store_true",
                        help="Nach dem Start das Cockpit im Standardbrowser öffnen")
    parser.add_argument("--log-level", default=os.environ.get("TEAM_MANAGER_LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    settings = Settings()
    if args.port:
        settings.port = args.port
    if args.home:
        settings.home = args.home
    if args.agents_dir:
        settings.agents_dir = args.agents_dir

    if args.skip_if_running and port_in_use(settings.port):
        print(f"Team-Manager läuft bereits auf http://127.0.0.1:{settings.port}, kein zweiter Start.")
        return

    # Ohne Konsole (pythonw, Autostart) schreibt der Service in <home>/service.log.
    configure_logging(args.log_level, log_file=settings.home / "service.log" if sys.stderr is None else None)
    app = create_app(settings)
    if args.open_browser:
        open_browser_when_ready(settings.port)
    # Bewusst fest auf Loopback: der Dienst darf nicht im Netzwerk erreichbar sein.
    uvicorn.run(app, host="127.0.0.1", port=settings.port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
