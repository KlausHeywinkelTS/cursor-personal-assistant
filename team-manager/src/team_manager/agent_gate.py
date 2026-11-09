"""Command-Hook für PreToolUse(Agent): Gate vor dem Start eines Team-Agenten.

Läuft als eigener Prozess (nur Standardbibliothek, schneller Start):
  - Fremde Subagenten (Explore, general-purpose, ...) passieren sofort ohne Ausgabe.
  - Team-Agenten werden an den Service weitergereicht (POST /hooks) und dessen Antwort ausgegeben.
  - Ist der Service nicht erreichbar, wird der Start eines Team-Agenten abgelehnt (fail-closed),
    damit kein nicht beobachteter Agentenlauf entsteht. Grund: `if`-Filter greifen im Hook nicht
    auf subagent_type (docs/feasibility.md, V7), ein pauschales onFailure=block würde alle Subagenten sperren.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_S = 5


def _home() -> Path:
    return Path(os.environ.get("TEAM_MANAGER_HOME", Path.home() / ".team-manager"))


def _deny(reason: str) -> str:
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}
    )


def _team_names(home: Path) -> set[str] | None:
    try:
        return {n.lower() for n in json.loads((home / "team_agents.json").read_text(encoding="utf-8"))["names"]}
    except (OSError, ValueError, KeyError):
        return None


def _token(home: Path) -> str:
    return os.environ.get("TEAM_MANAGER_TOKEN") or (home / "token").read_text(encoding="utf-8").strip()


def run(raw: str) -> str:
    """Gibt den Text für stdout zurück (leer = durchlassen)."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return ""
    if payload.get("tool_name") != "Agent":
        return ""
    home = _home()
    names = _team_names(home)
    subagent = str((payload.get("tool_input") or {}).get("subagent_type") or "").strip().lower()
    if names is None or subagent not in names:
        return ""
    url = f"http://127.0.0.1:{os.environ.get('TEAM_MANAGER_PORT', '8765')}/hooks"
    try:
        request = urllib.request.Request(
            url,
            data=raw.encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token(home)}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (fest 127.0.0.1)
            body = response.read().decode("utf-8")
        return body if body.strip() not in ("", "{}") else ""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return _deny(
            f"Der Team-Manager ist nicht erreichbar ({type(exc).__name__}). {subagent.capitalize()} wird nicht gestartet, "
            "damit kein unbeobachteter Auftrag entsteht. Erledige den Auftrag nicht selbst, "
            "sondern bitte den Benutzer, den Team-Manager zu starten (py -m team_manager)."
        )


def main() -> None:
    # Hook-Ein- und Ausgabe sind UTF-8. Die Textstreams nutzen unter Windows die Locale (cp1252),
    # was Umlaute in Auftragstiteln zu "Ã¤" verfälscht. Deshalb direkt über die Byte-Streams.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(run(raw).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
