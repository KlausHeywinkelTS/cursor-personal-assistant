"""Schaltet die Spike-Konfiguration an und aus (alles reversibel, mit Backup).

  py spike_ctl.py on    # Hooks + env in ~/.claude/settings.json, karla.md nach ~/.claude/agents, MCP-Server (user scope)
  py spike_ctl.py off   # entfernt genau das wieder
  py spike_ctl.py status

Es werden nur Einträge angefasst, die an der Spike-URL (127.0.0.1:8799) bzw. am Namen spike-team erkennbar sind.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SETTINGS = HOME / ".claude" / "settings.json"
BACKUP = HOME / ".claude" / "settings.json.spike-backup"
AGENT_DST = HOME / ".claude" / "agents" / "karla.md"
AGENT_SRC = Path(__file__).parent / "agents" / "karla.md"
HOOK_URL = "http://127.0.0.1:8799/hook"
HOOK_URL_IF = "http://127.0.0.1:8799/hook-if-karla"
MCP_NAME = "spike-team"
MCP_URL = "http://127.0.0.1:8798/mcp"
ENV_KEY = "TEAM_SPIKE_TOKEN"

EVENTS = [
    "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
    "SubagentStart", "SubagentStop", "SessionStart", "SessionEnd", "Stop",
]


def http_hook(url: str, **extra) -> dict:
    hook = {
        "type": "http",
        "url": url,
        "timeout": 3,
        "headers": {"Authorization": f"Bearer ${ENV_KEY}"},
        "allowedEnvVars": [ENV_KEY],
    }
    hook.update(extra)
    return hook


def find_claude() -> str:
    candidates = sorted((HOME / ".vscode" / "extensions").glob("anthropic.claude-code-*/resources/native-binary/claude.exe"))
    if not candidates:
        sys.exit("claude.exe nicht gefunden")
    return str(candidates[-1])


def load() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_spike(entry: dict) -> bool:
    return any(str(h.get("url", "")).startswith("http://127.0.0.1:8799/") for h in entry.get("hooks", []))


def on() -> None:
    if not BACKUP.exists():
        shutil.copy2(SETTINGS, BACKUP)
        print(f"Backup: {BACKUP}")
    data = load()
    hooks = data.setdefault("hooks", {})
    for event in EVENTS:
        entries = [e for e in hooks.get(event, []) if not is_spike(e)]
        entries.append({"hooks": [http_hook(HOOK_URL)]})
        if event == "PreToolUse":  # V7: if-Filter auf subagent_type
            entries.append({"matcher": "Agent", "hooks": [http_hook(HOOK_URL_IF, **{"if": "Agent(karla)"})]})
        hooks[event] = entries
    data.setdefault("env", {})[ENV_KEY] = "spike-secret-123"
    save(data)
    AGENT_DST.parent.mkdir(parents=True, exist_ok=True)
    if AGENT_DST.exists():
        sys.exit(f"{AGENT_DST} existiert bereits, nicht überschrieben.")
    shutil.copy2(AGENT_SRC, AGENT_DST)
    subprocess.run([find_claude(), "mcp", "add", "--transport", "http", "--scope", "user", MCP_NAME, MCP_URL], check=False)
    print("Spike AN. Neue Claude-Code-Session/VS-Code-Fenster öffnen, damit Hooks, Agent und MCP geladen werden.")


def off() -> None:
    data = load()
    hooks = data.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [e for e in hooks[event] if not is_spike(e)]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        data.pop("hooks", None)
    data.get("env", {}).pop(ENV_KEY, None)
    if not data.get("env", True):
        data.pop("env", None)
    save(data)
    if AGENT_DST.exists() and AGENT_DST.read_bytes() == AGENT_SRC.read_bytes():
        AGENT_DST.unlink()
    subprocess.run([find_claude(), "mcp", "remove", "--scope", "user", MCP_NAME], check=False)
    print("Spike AUS. (Backup bleibt liegen:", BACKUP, ")")


def status() -> None:
    data = load()
    n = sum(1 for ev in data.get("hooks", {}).values() for e in ev if is_spike(e))
    print(f"Spike-Hook-Einträge: {n}; env gesetzt: {ENV_KEY in data.get('env', {})}; karla.md: {AGENT_DST.exists()}")


if __name__ == "__main__":
    {"on": on, "off": off, "status": status}.get(sys.argv[1] if len(sys.argv) > 1 else "status", status)()
