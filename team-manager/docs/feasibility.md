# Machbarkeitsbericht (Phase 1)

Stand: 2026-11-09. Getestet mit Claude Code 2.1.319 (VS-Code-Plugin, nicht CLI), Windows 11.
Messdaten: `team-manager/spike/hook_log.jsonl` und `mcp_log.jsonl`.

## Kurzfazit

Das System ist machbar. Der Lebenszyklus (Start, Aktivität, Ende) kommt zuverlässig aus Hooks, die Inhalte (Fortschritt, Ergebnis, Blocker) kommen aus MCP.
Vier Annahmen aus Doku und Plan waren falsch oder unvollständig. Sie sind unten als Design-Konsequenzen eingearbeitet.

## Ergebnisse je Prüfpunkt

Kategorien: **E** = empirisch verifiziert, **D** = dokumentiert, nicht selbst getestet, **O** = offen.

| ID | Frage | Ergebnis | Kat. |
|---|---|---|---|
| V1 | Wie wird ein Agent angesprochen? | `@agent-karla` funktioniert. Laut Parser der CLI gilt außerdem `@"karla (agent)"`. Ein schlichtes `@karla` ist eine Datei-Mention und löst nichts aus. Ob der `@`-Typeahead Agenten anbietet, ist ungetestet; die Webview scheint sie nicht zu listen. | E (Syntax), O (Typeahead) |
| V2 | Greift `deny` aus einem `http`-Hook? | Ja. Der `PreToolUse` auf `Agent` liefert `subagent_type`, `prompt`, `description`, `tool_use_id`. Nach `deny` folgt kein `SubagentStart`. Die Hauptsession erledigt die Arbeit danach selbst. | E |
| V3 | Kommt `additionalContext` aus `SubagentStart` an? | Ja. Karla hat den Marker `SPIKE-MARKER-42` genannt. | E |
| V4 | Sieht man im Hook, welcher Agent ein MCP-Tool aufruft? | Ja. `PreToolUse` auf `mcp__<server>__<tool>` trägt `agent_id`, `agent_type`, `tool_use_id`, `mcp_server`. Der MCP-Server sieht im `_meta` zusätzlich `claudecode/toolUseId` und im Header `mcp-session-id` (MCP-Verbindung, nicht Claude-Session). | E |
| V5 | Hintergrund-Subagenten? | Der Agent startet standardmäßig **asynchron** (`status: async_launched`). `SubagentStop` feuert trotzdem. Er enthält **kein** `last_assistant_message`. | E |
| V6 | Fenster mitten in der Arbeit schließen? | Der Agent wird beendet. Für seine Session kommt weder `SubagentStop` noch `SessionEnd`. Andere Sessions des Fensters melden `SessionEnd` mit `reason: other`. Eine Stichprobe. | E (n=1) |
| V7 | Filtert `if: "Agent(karla)"` auf `subagent_type`? | Nein. Der Endpunkt wurde nie getroffen. Ursache offen (Syntax?). | E (negativ) |
| V8 | Verhalten bei unerreichbarem Endpunkt? | Nicht getestet. Laut Settings-Schema ist `onFailure: continue` der Default, der Hook blockiert dann nichts. | D |
| V9 | Behält ein fortgesetzter Agent seine `agent_id`? | Nicht getestet, für das MVP nicht nötig (jeder Auftrag ist ein neuer Agentenlauf). | O |
| V10 | `env` aus `settings.json` in Header-Interpolation? | Ja, `Bearer spike-secret-123` kam an. | E |

## Weitere Beobachtungen

- Das Ergebnis eines Agenten erscheint als Tool-Aufruf `SubagentHandback` (`tool_input.message`) kurz vor `SubagentStop`.
- `PostToolUse` auf `Agent` bedeutet "gestartet", nicht "fertig". Das `Stop` der Hauptsession kommt vor dem Ende des Agenten.
- `UserPromptSubmit` enthält den kompletten Prompt im Feld `prompt`.
- Ein `SessionStart`-Event kam über den `http`-Hook nie an (Ursache offen).
- `claude.exe`-Aufrufe aus der Shell (`mcp list`) erzeugen eigene Sessions samt `SessionEnd`. Der Service muss unbekannte Sessions ignorieren.
- Ohne `model` im Frontmatter lief der Subagent auf Haiku.
- Agenten aus `~/.claude/agents/` sind in allen Projekten verfügbar (Test 7 teilweise bestätigt: zweites Projekt `sw-capitalization`).

## Konsequenzen für das Design

1. **Abschluss = `SubagentStop`.** Weder `PostToolUse(Agent)` noch das `Stop` der Hauptsession zählen. Die Zusammenfassung stammt aus dem zuletzt gesehenen `SubagentHandback` (`tool_input.message`), Fallback ist `agent_transcript_path`.
2. **Identität für MCP über `tool_use_id`.** Der Hook `PreToolUse` auf `mcp__team__*` merkt sich `tool_use_id → agent_id/task`. Das MCP-Tool schlägt `_meta["claudecode/toolUseId"]` nach. Ein Aufruf ohne Eintrag wird mit `NOT_TASK_OWNER` abgelehnt. Ob der Hook immer vor dem MCP-Aufruf eintrifft, ist nicht bewiesen, deshalb wartet das Tool bis zu 2 s auf den Eintrag.
3. **Fail-closed nur für Team-Agenten.** Da `if` nicht filtert, würde `onFailure: block` auf dem Matcher `Agent` bei Ausfall des Service jeden Subagenten sperren. Stattdessen läuft ein `command`-Hook (kleines Python-Skript): Ist `subagent_type` ein Team-Agent und der Service nicht erreichbar, gibt es `deny`. Andere Typen passieren sofort.
4. **Fenster-Schließen braucht den Watchdog.** `SessionEnd` ist nur ein Zusatzsignal. Aktive Tasks ohne Aktivität über `orphan_timeout` werden als `orphan_suspected` markiert, nie als `REVIEW_REQUIRED` oder `DONE`. Im Cockpit gibt es "Abbrechen", damit der Agent wieder frei wird.
5. **Der `deny`-Grund enthält eine Anweisung** ("Karla arbeitet an [Titel]. Erledige den Auftrag nicht selbst."). Ob die Hauptsession sie befolgt, ist Modellverhalten und nicht garantiert (Einschränkung).
6. **Profile setzen `model` explizit.**
7. **`UserPromptSubmit`-Hook** erkennt `@agent-karla`, `@"karla (agent)"` und schlichtes `@karla` und injiziert die Delegationsanweisung.

## Abweichungen der Umsetzung vom Plan

- **Kein `env`-Block in `settings.json`.** Das Token steht direkt im Hook-Header und im MCP-Header. Der Env-Weg ist für Hooks belegt (V10), für MCP-Header ungeprüft, und er würde das Token in jede Agenten-Shell tragen.
- **Das Token berechtigt nicht zu Cockpit-Aktionen.** Sonst könnte ein Agent per `curl` seinen eigenen Review auf `DONE` setzen. Cockpit-Aktionen laufen nur über Origin und CSRF-Token.
- **Desktop-Benachrichtigung ohne `desktop-notifier`.** Windows-Toast per PowerShell, macOS per `osascript`, Linux per `notify-send`, jeweils mit Text über Umgebungsvariablen (keine Interpolation in Skriptcode). Weniger Abhängigkeiten, keine Windows-Runtime-Pakete.
- **MCP-SDK auf `<2` festgelegt.** Version 2 benennt `FastMCP` um und ändert die API. Getestet mit 1.30.
- **MCP im zustandslosen Modus** (`stateless_http`). Ein Neustart des Dienstes macht keine offenen Sitzungen ungültig, mehrere Fenster teilen sich nichts.
- **Migrationen im Paket** (`src/team_manager/migrations/`), nicht im Projektroot.
- **Die Hooks für Tool-Aufrufe sind aufgeteilt:** `PreToolUse` nur für `Agent` (Gate-Skript) und für `mcp__team__.*|SubagentHandback` (HTTP), `PostToolUse` ohne Filter als Aktivitätsnachweis.

## Offen

- Typeahead in der Webview (V1), Verhalten bei Serverausfall (V8), `if`-Syntax (V7), fehlendes `SessionStart` über `http`.
- V6 mit nur einer Stichprobe: Wiederholung mit dem echten Service empfohlen.
- Race zwischen `PreToolUse` und MCP-Aufruf (siehe Punkt 2).
