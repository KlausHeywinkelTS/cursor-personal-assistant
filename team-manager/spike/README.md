# Phase-1-Spike: Hook- und MCP-Verhalten messen

## Vorbereitung

Drei Terminals, jeweils im Projektroot (`personal-assistant`).

```text
py team-manager/spike/hook_logger.py        # Terminal 1: Hook-Logger (Port 8799) -> team-manager/spike/hook_log.jsonl
py team-manager/spike/spike_mcp.py          # Terminal 2: Mini-MCP-Server (Port 8798) -> team-manager/spike/mcp_log.jsonl
py team-manager/spike/spike_ctl.py on       # Terminal 3: Hooks, env, karla.md und MCP-Server eintragen (Backup wird angelegt)
```

Danach ein **neues** VS-Code-Fenster mit einem beliebigen Testordner öffnen.

## Szenarien

| ID | Was du tust | Was ich auswerte |
|---|---|---|
| V1 | `@` tippen: Wird Karla im Typeahead angeboten? Dann `@karla lies die README und fasse sie in 2 Sätzen zusammen` | Delegiert der Hauptagent per `Agent`-Tool? |
| V2/V7 | `team-manager/spike/control.json` mit `{"deny_agent": "karla"}` anlegen, Szenario V1 wiederholen | Greift `deny`? Feuert `/hook-if-karla` nur für Karla? |
| V3 | `team-manager/spike/control.json` mit `{"subagent_start_context": "SPIKE-MARKER-42"}`, V1 wiederholen | Nennt Karla den Marker in ihrer Antwort? |
| V4 | (läuft in V1 mit) | Hat der MCP-Call im `PreToolUse` eine `agent_id`? Was sieht `mcp_log.jsonl`? |
| V5 | V1 mit Klick auf "Run in background" | Feuert `SubagentStop`? Mit welchen Feldern? |
| V6 | Auftrag starten, **Fenster mitten in der Arbeit schließen** | `SessionEnd` und `reason`? Läuft der Agent weiter? |
| V8 | Logger beenden, V1 wiederholen | Blockiert der unerreichbare Hook-Endpunkt etwas? |
| V9 | Karla weiterführen (Folgeauftrag an dieselbe Instanz) | Gleiche `agent_id`? |
| V10 | (läuft in V1 mit) | Steht in `auth_header` `Bearer spike-secret-123`? |

## Aufräumen

```text
py team-manager/spike/spike_ctl.py off      # entfernt Hooks, env, karla.md und MCP-Eintrag wieder
```

Backup der Settings: `~/.claude/settings.json.spike-backup`
