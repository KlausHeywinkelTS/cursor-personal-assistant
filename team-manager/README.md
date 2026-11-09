# Team-Manager für Claude-Code-Agenten

Lokaler Dienst, der ein kleines, festes Team von KI-Agenten (Karla, Yasmin, Lotta) verwaltet, die als Claude-Code-Subagenten in VS Code arbeiten. Er beantwortet jederzeit:

- Wer ist beschäftigt, wer ist frei?
- Woran arbeitet wer, und seit wann?
- Welche Ergebnisse warten auf deine Prüfung?
- Was ist blockiert, fehlgeschlagen oder abgebrochen?

Er funktioniert mit mehreren gleichzeitig geöffneten VS-Code-Fenstern und über Projekte hinweg. Agentenprofile und Dienst werden einmal installiert, nicht pro Projekt.

Die technische Grundlage (was Claude Code tatsächlich liefert und was nicht) steht in [docs/feasibility.md](docs/feasibility.md). Grenzen und Ausbaumöglichkeiten stehen in [docs/limitations.md](docs/limitations.md).

## So funktioniert es

```text
 VS-Code-Fenster A        VS-Code-Fenster B
 Claude Code + Karla      Claude Code + Yasmin
        |  Hooks (HTTP) + MCP (HTTP)  |
        v                             v
   +------------------------------------------+
   |  Team-Manager  127.0.0.1:8765            |
   |  FastAPI  |  MCP /mcp  |  SQLite (WAL)   |
   +------------------------------------------+
        |                    |
   Cockpit im Browser    Desktop-Benachrichtigung
```

Die Arbeit der Agenten läuft ausschließlich in Claude Code in VS Code. Der Dienst startet keine Claude-Prozesse.

**Zuverlässigkeit kommt von den Hooks, nicht vom guten Willen des Modells.**

| Moment | Quelle | Wirkung |
|---|---|---|
| Du beauftragst `@agent-karla` | Hook `PreToolUse` auf `Agent` | Atomare Reservierung, ist Karla beschäftigt, wird der Start abgelehnt |
| Der Subagent läuft an | Hook `SubagentStart` | Erst jetzt gilt der Auftrag als angenommen (`IN_PROGRESS`) |
| Fortschritt, Blocker, Ergebnis | MCP-Werkzeuge | Inhalte des Agenten, Zuordnung über `tool_use_id` |
| Der Subagent endet | Hook `SubagentStop` | Fehlt die Abschlussmeldung: `REVIEW_REQUIRED` mit Hinweis „Ergebnis unvollständig“ |
| Fenster geschlossen | Hook `SessionEnd` und Watchdog | Auftrag wird als verwaist markiert und nach einer Frist `FAILED`, nie als erfolgreich |

## Voraussetzungen

- Windows 11 (getestet) oder macOS (Anleitung ungetestet)
- Python 3.12 oder neuer (unter Windows mit dem `py`-Launcher)
- Claude Code als VS-Code-Extension (getestet mit 2.1.319)

## Installation (Windows)

Im Projektroot (`personal-assistant`):

```text
py team-manager/scripts/install.py --dry-run     # zeigt nur, was passieren würde
py team-manager/scripts/install.py               # installiert
```

Das Skript ist idempotent und macht Folgendes:

1. Legt `team-manager/.venv` an und installiert das Paket.
2. Erzeugt `~/.team-manager/` mit einem zufälligen Token.
3. Kopiert die Profile aus [agents/](agents/) nach `~/.claude/agents/` (vorhandene Dateien bleiben unangetastet, außer mit `--force-agents`).
4. Mischt den Hook-Block aus [hooks/settings-hooks.json](hooks/settings-hooks.json) in `~/.claude/settings.json`. Fremde Hooks bleiben unberührt, ein Backup liegt als `settings.json.team-backup` daneben.
5. Registriert den MCP-Server `team` im User-Scope (`claude mcp add`).
6. Trägt den Autostart bei der Anmeldung ein (Registry-Schlüssel `HKCU\...\Run`).

Dienst jetzt starten, ohne neu anzumelden:

```text
team-manager\.venv\Scripts\python -m team_manager
```

Aus VS Code: Dieses Repo bringt den Task **Team-Manager: Dienst starten** mit ([.vscode/tasks.json](../.vscode/tasks.json)). Er startet beim Öffnen des Ordners automatisch (`task.allowAutomaticTasks` steht in [.vscode/settings.json](../.vscode/settings.json) auf `on`) und lässt sich über *Terminal > Task ausführen* auch von Hand starten. Läuft der Dienst schon (Autostart, anderes Fenster), beendet sich der Task mit einer Meldung, statt einen Portfehler zu werfen (`--skip-if-running`). Beim echten Start öffnet er außerdem das Cockpit im Standardbrowser (`--open-browser`); beim Autostart über die Anmeldung geschieht das bewusst nicht.

Cockpit: <http://127.0.0.1:8765>. Danach die VS-Code-Fenster neu laden, denn Claude Code liest Hooks, Agenten und MCP beim Sitzungsstart.

**Wichtig:** Der Dienst muss laufen. Wenn nicht, wird der Start eines Team-Agenten bewusst abgelehnt (siehe unten), und alle anderen Hooks melden nicht blockierende Fehler.

### macOS (ungetestet)

Dieselben Befehle mit `python3` statt `py`. Der Installer schreibt eine LaunchAgent-Datei nach `~/Library/LaunchAgents/de.teammanager.service.plist` und nennt den Befehl `launchctl load ...`. Desktop-Benachrichtigungen laufen über `osascript`. Es wurde nichts davon auf einem Mac geprüft.

### Deinstallation

```text
py team-manager/scripts/install.py --uninstall
```

Entfernt Hooks, MCP-Eintrag, Autostart und unveränderte Profil-Kopien. Datenbank und Token in `~/.team-manager/` bleiben liegen.

## Benutzung

Im Chat einer Claude-Code-Session:

```text
@agent-karla Prüfe die Epics der Software-Aktivierung auf fehlende Release Briefs
```

Auch `@"karla (agent)"` funktioniert. Ein schlichtes `@karla` erkennt der `UserPromptSubmit`-Hook und weist die Hauptsession an, an Karla zu delegieren. Der `@`-Typeahead der Extension bietet die Agenten vermutlich nicht an (nicht geprüft), die ausgeschriebene Form genügt.

Ist Karla beschäftigt, sagt dir die Hauptsession, woran sie arbeitet. Sie soll den Auftrag nicht selbst erledigen. Das ist eine Anweisung an das Modell und keine technische Sperre (siehe Einschränkungen).

### Cockpit

- **Agenten:** Status, aktueller Auftrag, Projekt, Beginn, letzte Aktualisierung
- **Wartet auf dich:** offene Reviews und Blocker, mit direkten Aktionen
- **Aufträge:** Filter Alle, In Arbeit, Review erforderlich, Blockiert, Abgeschlossen, Fehlgeschlagen (inklusive Abgebrochen)
- **Detail:** Zusammenfassung, Ergebnisverweis, vollständiges Ereignisprotokoll. Direktlink: `http://127.0.0.1:8765/#task-12`

Aktionen: *Als erledigt markieren* (nur bei `REVIEW_REQUIRED`), *Fehlgeschlagen*, *Blocker gelöst*, *Abbrechen*. Der Wechsel auf `DONE` ist ausschließlich hier möglich.

Das Cockpit aktualisiert sich selbst (Server-Sent Events, alle 10 s zusätzlich Polling).

## Auftragslebenszyklus

```text
REGISTERED --Start bestätigt--> IN_PROGRESS --complete_task--> REVIEW_REQUIRED --Benutzer--> DONE
    |                            |     ^                            |
    |                       report_blocker  Blocker gelöst           +--Benutzer--> FAILED
    |                            v     |
    |                          BLOCKED -+
    +--> FAILED / CANCELLED  (Fehlstart, Watchdog, Abbruch durch den Benutzer)
```

Beschäftigt ist ein Agent in `REGISTERED`, `IN_PROGRESS` und `BLOCKED`. `REVIEW_REQUIRED` gibt ihn frei. Unzulässige Übergänge werden abgelehnt (`INVALID_TRANSITION`) und als Ereignis protokolliert. Die vollständige Tabelle steht in [src/team_manager/lifecycle.py](src/team_manager/lifecycle.py).

Fehlercodes: `AGENT_BUSY`, `AGENT_UNKNOWN`, `TASK_NOT_FOUND`, `INVALID_TRANSITION`, `NOT_TASK_OWNER`, `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_INPUT`.

## MCP-Werkzeuge

In Claude Code heißen sie `mcp__team__<name>` (Punkte wie in `team.list_agents` erlaubt das Namensschema nicht).

| Werkzeug | Zweck |
|---|---|
| `list_agents` | Alle Agenten mit Verfügbarkeit und aktuellem Auftrag |
| `start_task(agent, title, description, project_path)` | Reserviert einen Agenten, lehnt ab, wenn er beschäftigt ist |
| `get_task(task_id)` | Details samt Ereignisprotokoll |
| `update_task(task_id, status, message)` | Fortschrittsmeldung |
| `complete_task(task_id, summary, result_reference)` | Meldet das Ergebnis, der Auftrag geht auf `REVIEW_REQUIRED` |
| `report_blocker(task_id, reason)` | Meldet einen Blocker |

Es gibt kein Werkzeug, um andere Agenten zu beauftragen. Aufrufe von `start_task` aus einem Subagenten blockiert der Hook zusätzlich.

## Agentenprofile konfigurieren

Die Dateien in `~/.claude/agents/` sind die einzige Quelle. Der Dienst nimmt jede Datei mit `team_member: true` ins Team auf:

```yaml
---
name: karla
description: Wofür Karla zuständig ist (Claude Code nutzt das zur Auswahl)
team_member: true
display_name: Karla
competencies:
  - Analyse von Code und Dokumenten
tools: Read, Glob, Grep, mcp__team__update_task, mcp__team__complete_task, mcp__team__report_blocker
disallowedTools: Agent, mcp__team__start_task
model: sonnet
---
```

Kompetenzen stehen nur hier, nie im Code. Die mitgelieferten Profile in [agents/](agents/) sind **Beispiele** und sollten angepasst werden. Änderungen werden beim Neustart des Dienstes eingelesen. Wird ein Profil entfernt oder `team_member` zurückgenommen, wird der Agent deaktiviert, seine Aufträge bleiben erhalten.

Wichtig: Ohne `model` im Profil lief ein Subagent im Test auf Haiku.

## Konfiguration

Umgebungsvariablen (alle optional):

| Variable | Standard | Bedeutung |
|---|---|---|
| `TEAM_MANAGER_HOME` | `~/.team-manager` | Datenbank, Token, Log |
| `TEAM_MANAGER_PORT` | `8765` | HTTP-Port (der Dienst bindet immer nur an 127.0.0.1) |
| `TEAM_MANAGER_AGENTS_DIR` | `~/.claude/agents` | Ort der Agentenprofile |
| `TEAM_MANAGER_REGISTERED_TIMEOUT_S` | `120` | Frist bis zum bestätigten Start, sonst `FAILED` |
| `TEAM_MANAGER_ORPHAN_TIMEOUT_S` | `900` | Ohne Aktivität so lange: „möglicherweise verwaist“ |
| `TEAM_MANAGER_SESSION_END_GRACE_S` | `120` | Nach `SessionEnd` ohne Aktivität: `FAILED` |
| `TEAM_MANAGER_NOTIFICATIONS` | `1` | `0` schaltet Desktop-Benachrichtigungen ab |
| `TEAM_MANAGER_LOG_LEVEL` | `INFO` | Strukturierte JSON-Logs auf stderr (ohne Konsole in `service.log`) |

## Fehlerbehandlung

| Situation | Verhalten |
|---|---|
| Agent bereits beschäftigt | Start wird abgelehnt, der Grund nennt den aktiven Auftrag, dieser bleibt unverändert |
| Service nicht erreichbar | Start eines Team-Agenten wird abgelehnt (fail-closed), andere Subagenten laufen normal |
| Fenster geschlossen | Auftrag wird nie als erfolgreich gezeigt: erst „möglicherweise verwaist“, nach der Frist `FAILED` |
| Abschlussmeldung vergessen | `SubagentStop` setzt `REVIEW_REQUIRED` mit „Abschluss erkannt, Ergebnis unvollständig“ |
| Service-Neustart | Alles steht in SQLite und ist sofort wieder da |
| Veraltete Session meldet Status | Abgelehnt (`NOT_TASK_OWNER`), der Auftrag bleibt unverändert |
| Start nicht bestätigt | Nach 120 s `FAILED`, der Agent ist wieder frei |
| Verwaister Auftrag blockiert Karla | Im Cockpit *Abbrechen* |

## Sicherheit

- Der Dienst bindet nur an `127.0.0.1`. Der Host-Header wird geprüft (Schutz gegen DNS-Rebinding).
- Hook- und MCP-Endpunkte verlangen ein Bearer-Token. Es liegt in `~/.team-manager/token`, in `~/.claude/settings.json` und in `~/.claude.json` (alles Dateien deines Benutzers). Neues Token: `install.py --rotate-token`.
- Cockpit-Aktionen verlangen Origin und CSRF-Token und senden keine CORS-Header. Fremde Webseiten können nichts verändern.
- Das Token berechtigt **nicht** zu Cockpit-Aktionen. Ein Agent kann damit seinen Review nicht selbst bestätigen.
- Grenze: Ein lokaler Prozess mit deinen Benutzerrechten kann das nachbauen. Das Modell schützt vor Webseiten, nicht vor beliebigem lokalem Code.

## Entwicklung und Tests

```text
cd team-manager
.venv\Scripts\python -m pytest
```

Die Tests decken ab: die vollständige Übergangsmatrix, 20 parallele Reservierungen (genau eine gewinnt), Hook-Payloads in der im Spike gemessenen Form, einen Ende-zu-Ende-Lauf mit echtem Server und echtem MCP-Client, Neustart, Sicherheit (Host, Token, Origin, CSRF) und den Installer.

Die manuellen Abnahmetests 1 bis 7 stehen in [docs/acceptance.md](docs/acceptance.md). Der Spike aus Phase 1 liegt in [spike/](spike/).

Das MCP-SDK ist auf `mcp>=1.26,<2` festgelegt, weil Version 2 die API ändert (`FastMCP` heißt dort `MCPServer`).
