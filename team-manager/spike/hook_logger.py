"""Phase-1-Spike: loggt alle Claude-Code-Hook-Payloads (HTTP-Hooks) als JSONL.

Nur Standardbibliothek. Läuft auf 127.0.0.1:8799.

Steuerung der Antworten (V2/V3) über spike/control.json, wird bei jedem Request neu gelesen:
  {"deny_agent": "karla",            # PreToolUse auf Agent -> deny, wenn subagent_type passt
   "subagent_start_context": "SPIKE-MARKER-42",   # additionalContext für SubagentStart
   "prompt_context": "SPIKE-PROMPT-MARKER"}       # additionalContext für UserPromptSubmit
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

HOST, PORT = "127.0.0.1", 8799
HERE = Path(__file__).parent
LOG = HERE / "hook_log.jsonl"
CONTROL = HERE / "control.json"
_lock = Lock()


def load_control() -> dict:
    try:
        return json.loads(CONTROL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_response(payload: dict, control: dict) -> dict:
    event = payload.get("hook_event_name")
    if event == "PreToolUse" and payload.get("tool_name") == "Agent":
        wanted = control.get("deny_agent")
        if wanted and payload.get("tool_input", {}).get("subagent_type") == wanted:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"SPIKE: {wanted} ist per control.json gesperrt.",
                }
            }
    if event == "SubagentStart" and control.get("subagent_start_context"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": control["subagent_start_context"],
            }
        }
    if event == "UserPromptSubmit" and control.get("prompt_context"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": control["prompt_context"],
            }
        }
    return {}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"_unparsed": raw}
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "path": self.path,
            "auth_header": self.headers.get("Authorization"),  # V10: wurde die Env-Variable interpoliert?
            "payload": payload,
        }
        with _lock, LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        body = json.dumps(build_response(payload, load_control())).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        event = ""
        sys.stderr.write(f"[spike] {self.address_string()} {fmt % args}{event}\n")


if __name__ == "__main__":
    print(f"Hook-Logger auf http://{HOST}:{PORT}/hook, Log: {LOG}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
