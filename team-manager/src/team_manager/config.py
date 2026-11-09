"""Konfiguration des Services. Alles überschreibbar per Umgebungsvariable (TEAM_MANAGER_*)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


# Einzige Quelle für den Standard-Port. scripts/install.py hat denselben Wert (ein Test prüft die Gleichheit).
# Bewusst abseits der üblichen Entwicklerports (8000, 8080, 8765, ...) und unter dem Ephemeral-Bereich ab 49152.
DEFAULT_PORT = 48765


def _default_home() -> Path:
    return Path(os.environ.get("TEAM_MANAGER_HOME", Path.home() / ".team-manager"))


def _default_agents_dir() -> Path:
    return Path(os.environ.get("TEAM_MANAGER_AGENTS_DIR", Path.home() / ".claude" / "agents"))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass
class Settings:
    home: Path = field(default_factory=_default_home)
    host: str = "127.0.0.1"
    port: int = field(default_factory=lambda: _env_int("TEAM_MANAGER_PORT", DEFAULT_PORT))
    # Verzeichnis mit den Claude-Code-Agentenprofilen (Quelle der Agentendefinitionen).
    agents_dir: Path = field(default_factory=_default_agents_dir)
    # Ein REGISTERED-Auftrag ohne bestätigten Start wird nach dieser Zeit FAILED.
    registered_timeout_s: int = field(default_factory=lambda: _env_int("TEAM_MANAGER_REGISTERED_TIMEOUT_S", 120))
    # Ohne Aktivitätsnachweis so lange -> möglicherweise verwaist (Status bleibt unverändert).
    orphan_timeout_s: int = field(default_factory=lambda: _env_int("TEAM_MANAGER_ORPHAN_TIMEOUT_S", 15 * 60))
    # Nach SessionEnd ohne Aktivität so lange -> FAILED (Fenster geschlossen, Agent beendet).
    session_end_grace_s: int = field(default_factory=lambda: _env_int("TEAM_MANAGER_SESSION_END_GRACE_S", 120))
    watchdog_interval_s: float = 15.0
    # So lange wartet ein MCP-Aufruf auf die Zuordnung tool_use_id -> Agent aus dem Hook.
    bridge_wait_s: float = 2.0
    notifications: bool = field(default_factory=lambda: os.environ.get("TEAM_MANAGER_NOTIFICATIONS", "1") != "0")
    # Optional fest vorgegeben (Tests); sonst Datei im Home-Verzeichnis.
    token: str | None = field(default_factory=lambda: os.environ.get("TEAM_MANAGER_TOKEN") or None)

    @property
    def db_path(self) -> Path:
        return self.home / "team.db"

    @property
    def token_path(self) -> Path:
        return self.home / "token"

    @property
    def team_agents_cache(self) -> Path:
        """Namen der Team-Agenten, vom Service geschrieben, vom Gate-Hook gelesen."""
        return self.home / "team_agents.json"

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def ensure_home(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)

    def load_token(self) -> str:
        """Token aus Konfiguration oder Datei; wird beim ersten Start erzeugt."""
        if self.token:
            return self.token
        self.ensure_home()
        if self.token_path.exists():
            value = self.token_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_urlsafe(32)
        self.token_path.write_text(value + "\n", encoding="utf-8")
        try:
            self.token_path.chmod(0o600)
        except OSError:
            pass
        return value
