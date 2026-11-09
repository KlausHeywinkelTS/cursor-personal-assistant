"""Verarbeitung der Claude-Code-Hook-Ereignisse. Reine Logik ohne HTTP, damit gut testbar.

Payload-Felder und Antwortformate sind in docs/feasibility.md belegt (empirisch aus dem Spike).
"""

from __future__ import annotations

import logging
import re

from .bridge import ToolUseBridge
from .errors import AgentBusy, AgentUnknown, ServiceError
from .service import TaskService

log = logging.getLogger("team_manager.hooks")

MCP_PREFIX = "mcp__team__"


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _context(event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


class HookHandler:
    def __init__(self, service: TaskService, bridge: ToolUseBridge, *, cockpit_url: str) -> None:
        self.service = service
        self.bridge = bridge
        self.cockpit_url = cockpit_url

    # ------------------------------------------------------------------ Einstieg

    def handle(self, payload: dict) -> dict:
        event = payload.get("hook_event_name")
        try:
            match event:
                case "UserPromptSubmit":
                    return self._on_prompt(payload)
                case "PreToolUse":
                    return self._on_pre_tool(payload)
                case "PostToolUse":
                    self._touch(payload)
                case "PostToolUseFailure":
                    self._on_tool_failure(payload)
                case "SubagentStart":
                    return self._on_subagent_start(payload)
                case "SubagentStop":
                    self._on_subagent_stop(payload)
                case "SessionEnd":
                    if payload.get("session_id"):
                        self.service.session_ended(payload["session_id"])
        except Exception:
            log.exception("hook_failed", extra={"event": event})
        return {}

    def _touch(self, payload: dict) -> None:
        if payload.get("agent_id"):
            self.service.touch_activity(payload["agent_id"])

    # ------------------------------------------------------------------ UserPromptSubmit

    def _on_prompt(self, payload: dict) -> dict:
        names = self.service.team_agent_names()
        if not names:
            return {}
        alternatives = "|".join(re.escape(n) for n in names)
        pattern = re.compile(rf'(?<![\w@])@(?:agent-)?"?({alternatives})(?:\s*\(agent\))?"?(?![\w-])', re.IGNORECASE)
        found: list[str] = []
        for match in pattern.finditer(payload.get("prompt") or ""):
            name = match.group(1).lower()
            if name not in found:
                found.append(name)
        if not found:
            return {}
        lines = [
            f'Der Benutzer hat {n.capitalize()} beauftragt. Delegiere den Auftrag über das Agent-Tool mit '
            f'subagent_type "{n}" und erledige ihn nicht selbst.'
            for n in found
        ]
        lines.append(
            "Wird die Delegation abgelehnt (Agent beschäftigt oder Team-Manager nicht erreichbar), "
            "sage dem Benutzer Bescheid und arbeite nicht selbst weiter."
        )
        return _context("UserPromptSubmit", "[Team-Manager] " + " ".join(lines))

    # ------------------------------------------------------------------ PreToolUse

    def _on_pre_tool(self, payload: dict) -> dict:
        tool = payload.get("tool_name") or ""
        agent_id = payload.get("agent_id")
        tool_use_id = payload.get("tool_use_id")

        if tool == "Agent":
            return self._gate_delegation(payload)
        if tool.startswith(MCP_PREFIX):
            return self._on_team_tool(tool.removeprefix(MCP_PREFIX), agent_id, tool_use_id)
        if tool == "SubagentHandback" and agent_id:
            message = (payload.get("tool_input") or {}).get("message") or ""
            self.service.record_handback(agent_id, message)
            return {}
        self._touch(payload)
        return {}

    def _gate_delegation(self, payload: dict) -> dict:
        tool_input = payload.get("tool_input") or {}
        subagent = str(tool_input.get("subagent_type") or "").strip().lower()
        if subagent not in self.service.team_agent_names():
            return {}  # fremder Subagent, nicht unsere Sache
        try:
            self.service.reserve_for_delegation(
                subagent,
                tool_input.get("description") or "",
                tool_input.get("prompt") or "",
                payload.get("cwd"),
                payload.get("session_id"),
                payload.get("tool_use_id"),
            )
        except AgentBusy as exc:
            hint = ""
            if exc.details.get("orphan_suspected"):
                hint = " Der Auftrag ist möglicherweise verwaist und kann im Cockpit abgebrochen werden."
            return _deny(
                f"{exc.message}{hint} Erledige den Auftrag NICHT selbst: sage dem Benutzer, dass "
                f"{subagent.capitalize()} beschäftigt ist (Cockpit: {self.cockpit_url})."
            )
        except AgentUnknown as exc:
            return _deny(f"{exc.message} Erledige den Auftrag nicht selbst, sondern informiere den Benutzer.")
        except Exception:
            log.exception("delegation_gate_failed")
            return _deny("Der Team-Manager hat einen internen Fehler gemeldet. Starte den Agenten nicht und informiere den Benutzer.")
        return {}

    def _on_team_tool(self, tool: str, agent_id: str | None, tool_use_id: str | None) -> dict:
        if tool == "start_task" and agent_id:
            return _deny("Agenten dürfen keine Aufträge an andere Agenten vergeben.")
        self.bridge.put(tool_use_id, agent_id)
        if agent_id:
            self.service.touch_activity(agent_id)
        return {}

    # ------------------------------------------------------------------ Tool-Fehler, Subagent-Lebenszyklus

    def _on_tool_failure(self, payload: dict) -> None:
        if payload.get("tool_name") == "Agent" and payload.get("tool_use_id") and not payload.get("agent_id"):
            self.service.start_failed(payload["tool_use_id"], str(payload.get("error") or "unbekannter Fehler"))
        else:
            self._touch(payload)

    def _on_subagent_start(self, payload: dict) -> dict:
        agent_id, agent_type = payload.get("agent_id"), payload.get("agent_type")
        if not agent_id or not agent_type:
            return {}
        result = self.service.confirm_start(payload.get("session_id"), agent_type, agent_id)
        task = result.get("task")
        if task:
            return _context(
                "SubagentStart",
                f"[Team-Manager] Du bearbeitest Auftrag #{task['id']} „{task['title']}“. Verwende immer task_id={task['id']}. "
                "Melde Fortschritt mit mcp__team__update_task, Blocker mit mcp__team__report_blocker und "
                "dein Ergebnis zum Schluss mit mcp__team__complete_task (summary, result_reference). "
                "Beauftrage keine anderen Agenten.",
            )
        if result.get("untracked"):
            return _context(
                "SubagentStart",
                f"[Team-Manager] Dieser Lauf ist nicht registriert: {result['untracked']} "
                "Brich die Arbeit sofort ab und melde dem Benutzer, dass der Agent beschäftigt ist.",
            )
        return {}

    def _on_subagent_stop(self, payload: dict) -> None:
        if payload.get("agent_id"):
            self.service.subagent_stopped(payload["agent_id"], payload.get("agent_transcript_path"))


__all__ = ["HookHandler", "ServiceError"]
