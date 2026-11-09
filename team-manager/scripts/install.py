"""Installation des Team-Managers (nur Standardbibliothek, läuft mit dem System-Python).

  py team-manager/scripts/install.py             # installieren / aktualisieren (idempotent)
  py team-manager/scripts/install.py --dry-run   # nur anzeigen, was passieren würde
  py team-manager/scripts/install.py --uninstall # Hooks, MCP-Eintrag, Autostart und Profil-Kopien entfernen

Was passiert:
  1. venv in team-manager/.venv anlegen und das Paket installieren
  2. Datenverzeichnis (~/.team-manager) und Token anlegen
  3. Agentenprofile nach ~/.claude/agents kopieren (vorhandene Dateien bleiben, außer mit --force-agents)
  4. Hook-Block in ~/.claude/settings.json einmischen (Backup einmalig als settings.json.team-backup)
  5. MCP-Server `team` im User-Scope registrieren
  6. Autostart einrichten (Windows: Run-Schlüssel, macOS: LaunchAgent-Datei, ungetestet)
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_TEMPLATE = ROOT / "hooks" / "settings-hooks.json"
AGENTS_SRC = ROOT / "agents"
IS_WINDOWS = sys.platform == "win32"
MCP_NAME = "team"
RUN_KEY_NAME = "TeamManager"
LAUNCH_AGENT = "de.teammanager.service.plist"


# --------------------------------------------------------------------------- reine Funktionen (getestet)


def render_hooks(template: dict, *, python: str, port: int, token: str) -> dict:
    """Setzt Platzhalter ein und entfernt Kommentarfelder."""

    def sub(value):
        if isinstance(value, str):
            return value.replace("{{PYTHON}}", python).replace("{{PORT}}", str(port)).replace("{{TOKEN}}", token)
        if isinstance(value, list):
            return [sub(v) for v in value]
        if isinstance(value, dict):
            return {k: sub(v) for k, v in value.items()}
        return value

    return {event: sub(entries) for event, entries in template.items() if not event.startswith("_")}


def is_ours(entry: dict) -> bool:
    """Erkennt Hook-Einträge dieses Projekts (egal mit welchem Port/Token)."""
    for hook in entry.get("hooks", []):
        url = str(hook.get("url", ""))
        if url.startswith("http://127.0.0.1:") and url.endswith("/hooks"):
            return True
        if "team_manager.agent_gate" in (hook.get("args") or []):
            return True
    return False


def merge_hooks(settings: dict, hooks: dict) -> dict:
    result = copy.deepcopy(settings)
    block = result.setdefault("hooks", {})
    for event, entries in hooks.items():
        block[event] = [e for e in block.get(event, []) if not is_ours(e)] + copy.deepcopy(entries)
    return result


def remove_hooks(settings: dict) -> dict:
    result = copy.deepcopy(settings)
    block = result.get("hooks", {})
    for event in list(block):
        block[event] = [e for e in block[event] if not is_ours(e)]
        if not block[event]:
            del block[event]
    if not block:
        result.pop("hooks", None)
    return result


# --------------------------------------------------------------------------- Ausführung


class Installer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.home = Path(os.environ.get("TEAM_MANAGER_HOME", Path.home() / ".team-manager"))
        self.claude_dir = Path.home() / ".claude"
        self.settings_path = self.claude_dir / "settings.json"
        self.venv_python = ROOT / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

    def say(self, text: str) -> None:
        print(("[dry-run] " if self.args.dry_run else "") + text)

    def run(self, cmd: list[str], **kw) -> subprocess.CompletedProcess:
        shown = ["Authorization: Bearer ***" if c.startswith("Authorization: Bearer ") else c for c in cmd]
        self.say("$ " + " ".join(shown))
        if self.args.dry_run:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(cmd, **kw)

    # -- Bausteine

    def ensure_venv(self) -> None:
        if not self.venv_python.exists():
            self.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
        self.run([str(self.venv_python), "-m", "pip", "install", "-q", "-e", str(ROOT)], check=True)

    def ensure_token(self) -> str:
        token_file = self.home / "token"
        if token_file.exists() and not self.args.rotate_token:
            return token_file.read_text(encoding="utf-8").strip()
        token = secrets.token_urlsafe(32)
        self.say(f"Token {'neu erzeugt' if token_file.exists() else 'erzeugt'}: {token_file}")
        if not self.args.dry_run:
            self.home.mkdir(parents=True, exist_ok=True)
            token_file.write_text(token + "\n", encoding="utf-8")
            try:
                token_file.chmod(0o600)
            except OSError:
                pass
        return token

    def copy_agents(self) -> None:
        target = self.claude_dir / "agents"
        for src in sorted(AGENTS_SRC.glob("*.md")):
            dst = target / src.name
            if dst.exists() and dst.read_bytes() == src.read_bytes():
                continue
            if dst.exists() and not self.args.force_agents:
                self.say(f"Profil bleibt unverändert (existiert, weicht ab): {dst}  [--force-agents zum Überschreiben]")
                continue
            self.say(f"Profil kopieren: {src.name} -> {dst}")
            if not self.args.dry_run:
                target.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.copy2(dst, dst.with_suffix(".md.bak"))
                shutil.copy2(src, dst)

    def load_settings(self) -> dict:
        if not self.settings_path.exists():
            return {}
        return json.loads(self.settings_path.read_text(encoding="utf-8"))

    def write_settings(self, settings: dict) -> None:
        backup = self.settings_path.with_name("settings.json.team-backup")
        if self.settings_path.exists() and not backup.exists():
            self.say(f"Backup: {backup}")
            if not self.args.dry_run:
                shutil.copy2(self.settings_path, backup)
        if not self.args.dry_run:
            self.claude_dir.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def install_hooks(self, token: str) -> None:
        template = json.loads(HOOKS_TEMPLATE.read_text(encoding="utf-8"))
        hooks = render_hooks(template, python=str(self.venv_python), port=self.args.port, token=token)
        self.say(f"Hooks in {self.settings_path} einmischen ({len(hooks)} Events)")
        self.write_settings(merge_hooks(self.load_settings(), hooks))

    def uninstall_hooks(self) -> None:
        if not self.settings_path.exists():
            return
        self.say(f"Hooks aus {self.settings_path} entfernen")
        self.write_settings(remove_hooks(self.load_settings()))

    def find_claude(self) -> str | None:
        found = shutil.which("claude")
        if found:
            return found
        pattern = str(Path.home() / ".vscode" / "extensions" / "anthropic.claude-code-*" / "resources" / "native-binary" / ("claude.exe" if IS_WINDOWS else "claude"))
        matches = sorted(glob.glob(pattern))
        return matches[-1] if matches else None

    def register_mcp(self, token: str) -> None:
        claude = self.find_claude()
        url = f"http://127.0.0.1:{self.args.port}/mcp"
        add = ["mcp", "add", "--transport", "http", "--scope", "user", MCP_NAME, url, "--header", f"Authorization: Bearer {token}"]
        if not claude:
            self.say("claude nicht gefunden. Bitte manuell ausführen:  claude " + " ".join(add[:-1]) + " 'Authorization: Bearer <Token aus ~/.team-manager/token>'")
            return
        self.say("MCP-Server registrieren (Token wird maskiert angezeigt)")
        self.run([claude, "mcp", "remove", "--scope", "user", MCP_NAME], capture_output=True)
        self.run([claude, *add], check=False)

    def unregister_mcp(self) -> None:
        claude = self.find_claude()
        if claude:
            self.run([claude, "mcp", "remove", "--scope", "user", MCP_NAME], check=False)

    def autostart_command(self) -> list[str]:
        python = self.venv_python.with_name("pythonw.exe") if IS_WINDOWS else self.venv_python
        return [str(python), "-m", "team_manager", "--port", str(self.args.port)]

    def install_autostart(self) -> None:
        cmd = self.autostart_command()
        if IS_WINDOWS:
            value = " ".join(f'"{c}"' if " " in c else c for c in cmd)
            self.run(["reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", RUN_KEY_NAME, "/t", "REG_SZ", "/d", value, "/f"], check=False)
        elif sys.platform == "darwin":
            plist = Path.home() / "Library" / "LaunchAgents" / LAUNCH_AGENT
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                f"<key>Label</key><string>de.teammanager.service</string><key>RunAtLoad</key><true/>"
                "<key>ProgramArguments</key><array>" + "".join(f"<string>{c}</string>" for c in cmd) + "</array></dict></plist>\n"
            )
            self.say(f"LaunchAgent schreiben: {plist}  (danach: launchctl load {plist})  [macOS: ungetestet]")
            if not self.args.dry_run:
                plist.parent.mkdir(parents=True, exist_ok=True)
                plist.write_text(body, encoding="utf-8")
        else:
            self.say("Autostart für dieses System nicht vorgesehen; Start manuell: " + " ".join(cmd))

    def uninstall_autostart(self) -> None:
        if IS_WINDOWS:
            self.run(["reg", "delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", RUN_KEY_NAME, "/f"], check=False, capture_output=True)
        elif sys.platform == "darwin":
            plist = Path.home() / "Library" / "LaunchAgents" / LAUNCH_AGENT
            if plist.exists() and not self.args.dry_run:
                plist.unlink()

    def remove_agents(self) -> None:
        for src in AGENTS_SRC.glob("*.md"):
            dst = self.claude_dir / "agents" / src.name
            if dst.exists() and dst.read_bytes() == src.read_bytes():
                self.say(f"Profil entfernen: {dst}")
                if not self.args.dry_run:
                    dst.unlink()

    # -- Abläufe

    def install(self) -> None:
        if not self.args.skip_venv:
            self.ensure_venv()
        token = self.ensure_token()
        self.copy_agents()
        self.install_hooks(token)
        if not self.args.no_mcp:
            self.register_mcp(token)
        if not self.args.no_autostart:
            self.install_autostart()
        self.say("")
        self.say("Fertig. Service starten:  " + " ".join(self.autostart_command()).replace("pythonw", "python"))
        self.say(f"Cockpit: http://127.0.0.1:{self.args.port}   |   danach VS-Code-Fenster neu laden (Hooks und MCP werden beim Sitzungsstart gelesen).")

    def uninstall(self) -> None:
        self.uninstall_hooks()
        self.unregister_mcp()
        self.uninstall_autostart()
        self.remove_agents()
        self.say(f"Daten bleiben erhalten: {self.home} (Datenbank, Token). Zum vollständigen Entfernen den Ordner löschen.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Team-Manager installieren")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--rotate-token", action="store_true", help="neues Token erzeugen (Hooks und MCP werden neu geschrieben)")
    parser.add_argument("--force-agents", action="store_true", help="vorhandene Agentenprofile überschreiben (Backup als .md.bak)")
    parser.add_argument("--skip-venv", action="store_true")
    parser.add_argument("--no-mcp", action="store_true")
    parser.add_argument("--no-autostart", action="store_true")
    args = parser.parse_args()
    installer = Installer(args)
    installer.uninstall() if args.uninstall else installer.install()


if __name__ == "__main__":
    main()
