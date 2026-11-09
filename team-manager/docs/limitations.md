# Einschränkungen und mögliche Erweiterungen

## Einschränkungen

### Bedingt durch Claude Code

1. **Delegation ist Modellverhalten.** Der Auftrag entsteht nur, wenn die Hauptsession das `Agent`-Tool für den Team-Agenten aufruft. `@agent-karla` und der `UserPromptSubmit`-Hook machen das sehr wahrscheinlich, erzwingen es aber nicht. Erledigt die Hauptsession die Arbeit selbst, entsteht kein Auftrag.
2. **Nach einer Ablehnung macht die Hauptsession eventuell selbst weiter.** Der Ablehnungstext verbietet das ausdrücklich, ein Modell kann ihn trotzdem ignorieren.
3. **Fenster schließen ist still.** Ohne `SubagentStop` und teils ohne `SessionEnd` bleibt nur der Watchdog. Ein abgebrochener Auftrag ist bis zu `session_end_grace` (Standard 2 Minuten) bzw. `orphan_timeout` (15 Minuten) als „läuft“ sichtbar, danach `FAILED` oder verwaist. Er wird nie als erfolgreich angezeigt. Gemessen mit einer Stichprobe.
4. **Das `Stop` der Hauptsession ist kein Abschlusssignal.** Subagenten laufen standardmäßig im Hintergrund. Maßgeblich ist `SubagentStop`.
5. **Kein `last_assistant_message` in `SubagentStop`.** Der Dienst nimmt ersatzweise die Nachricht aus `SubagentHandback` und verweist auf das Transkript des Agenten.
6. **`if`-Filter greifen nicht auf `subagent_type`.** Deshalb gibt es das Gate-Skript als `command`-Hook, das bei jedem Aufruf des `Agent`-Tools einen kurzen Python-Prozess startet (wenige Millisekunden).
7. **Jeder Tool-Aufruf in jeder Session löst einen lokalen HTTP-Aufruf aus** (`PostToolUse` ohne Filter, Aktivitätsnachweis). Ist der Dienst aus, melden diese Hooks nicht blockierende Fehler.
8. **`SessionStart` kam über den HTTP-Hook im Test nie an.** Der Dienst braucht es nicht.
9. **Der `@`-Typeahead der Extension bietet Agenten vermutlich nicht an.** Die ausgeschriebene Form funktioniert.
10. **Agenten- und MCP-Konfiguration wird beim Sitzungsstart gelesen.** Nach Änderungen muss das Fenster neu geladen werden.

### Bedingt durch das MVP

- **Genau ein aktiver Auftrag pro Agent.** Fortgesetzte Agentenläufe (Nachfragen an dieselbe Instanz) bekommen keinen eigenen Auftrag, V9 aus dem Spike ist ungeprüft.
- **Delegation nur von oben nach unten und nur durch Klaus.** Wer delegieren darf, steht im Profil (`can_delegate: true`). Es gibt keine Kommunikation zwischen gleichrangigen Agenten und keine Rückfragen von Karla an Klaus. Die Verschachtelung ist auf eine Ebene unter dem Manager ausgelegt. Claude Code erlaubt standardmäßig drei Ebenen (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), der Team-Manager verbietet das Delegieren für alle anderen Team-Agenten.
- **Ob Klaus auf seine Unteraufträge wartet, ist ungemessen** (Abnahmetest 8). Der Team-Manager lehnt `complete_task` ab, solange Unteraufträge laufen. Endet Klaus trotzdem früher, wird sein Auftrag unvollständig auf *Review erforderlich* gesetzt, die Unteraufträge laufen weiter.
- **Delegation durch Klaus ist wie jede andere Delegation Modellverhalten.** Der Dienst sieht nur, was über das Agent-Tool läuft. Erledigt Klaus Arbeit selbst, entsteht kein Unterauftrag.
- **Ein Nutzer, eine Maschine.** Keine Benutzerverwaltung, keine Fernzugriffe.
- **`result_reference` ist ein Text** (Pfad oder URL), das Cockpit öffnet lokale Dateien nicht.
- **Profiländerungen** wirken erst nach Neustart des Dienstes.
- **Der Dienst erkennt keine Projekte**, er speichert nur den Arbeitsordner (`cwd`) der Session.
- **Benachrichtigungen:** Windows-Toast ist umgesetzt, aber ob es erschien, hängt von Fokus-Assistent und Systemeinstellungen ab. macOS und Linux sind ungetestet.
- **macOS:** Installationsweg beschrieben, nirgends geprüft.
- **Sicherheit:** schützt vor Webseiten, nicht vor lokalem Code mit deinen Benutzerrechten. Das Token liegt im Klartext in deinen Konfigurationsdateien.

## Mögliche Erweiterungen

- **Weitere Benachrichtigungskanäle** (Discord, E-Mail) als zusätzliche Klassen hinter dem Interface `Notifier` in [notify.py](../src/team_manager/notify.py). Der Service ruft nur `notify(title, message)` auf.
- **Klick auf die Benachrichtigung öffnet das Cockpit** direkt beim Auftrag (Deep-Link `#task-ID` existiert bereits).
- **Rückfragen an einen Agenten** über das Cockpit: Auftrag zurück in die Bearbeitung statt neuem Auftrag.
- **Priorisierung und Warteschlange:** Aufträge für einen beschäftigten Agenten vormerken, statt abzulehnen.
- **Auswertung:** Durchlaufzeiten, Anteil unvollständiger Abschlüsse, Review-Dauer.
- **Projektfilter** im Cockpit und Zuordnung zu Jira-Issues.
- **Profile im Cockpit bearbeiten** und ohne Neustart neu laden.
- **Weitergehende Zusammenarbeit** zwischen Agenten (Rückfragen, mehrstufige Delegationsketten). Der Auftragsbaum (`parent_task_id`) ist seit Klaus im Datenmodell vorhanden.
- **Mehr Messungen:** V6 mit mehr Stichproben (Fenster schließen, Absturz, Ruhezustand) und V8/V9 aus dem Spike.
