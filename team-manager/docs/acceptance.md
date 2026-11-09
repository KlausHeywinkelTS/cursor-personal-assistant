# Abnahmeprotokoll

Manuelle Abnahme in VS Code (Windows). Die Spalte „Automatisch“ nennt den Test, der denselben Ablauf ohne VS Code absichert. Das ersetzt die manuelle Abnahme nicht.

**Vorbereitung:** Installation laut [README](../README.md), Dienst läuft, zwei VS-Code-Fenster mit zwei verschiedenen Projekten (Fenster A und B) neu geladen, Cockpit unter <http://127.0.0.1:48765> in einem Browserfenster.

| Datum | Getestet von | Version |
|---|---|---|
| | | |

## Test 1: Auftrag an Karla

1. In Fenster A: `@agent-karla Fasse die README in zwei Sätzen zusammen`.
2. Im Cockpit prüfen: Karla ist *Beschäftigt*, der Auftrag steht auf *In Arbeit*, Projekt und Beginn sind gesetzt.

Automatisch: `test_e2e.py::test_full_flow_with_real_mcp_client`, `test_hooks.py::test_subagent_start_confirms_and_briefs_the_agent`

Ergebnis: ☑️ bestanden ☐ nicht bestanden. Notiz:

## Test 2: Doppelbeauftragung

1. Während Karla arbeitet, in Fenster B: `@agent-karla Mache etwas anderes`.
2. Erwartet: Der Start wird abgelehnt, die Hauptsession nennt den aktiven Auftrag und erledigt ihn nicht selbst. Im Cockpit bleibt der erste Auftrag unverändert.

Automatisch: `test_e2e.py::test_second_window_is_denied_and_first_task_unchanged`, `test_reservation_concurrency.py`

Ergebnis: ☑️ bestanden ☐ nicht bestanden. Notiz:

## Test 3: Parallele Agenten

1. Karla arbeitet in Fenster A. In Fenster B: `@agent-yasmin ...`.
2. Erwartet: Beide sind gleichzeitig *Beschäftigt* mit unterschiedlichen Aufträgen und Projekten.

Automatisch: `test_e2e.py::test_parallel_agents_in_two_windows`

Ergebnis: ☑️ bestanden ☐ nicht bestanden. Notiz:

## Test 4: Abschluss und Review

1. Karla beendet ihre Arbeit.
2. Erwartet: Der Auftrag steht auf *Review erforderlich*, Zusammenfassung und Ergebnisverweis sind sichtbar, Karla ist wieder *Frei*, eine Desktop-Benachrichtigung erscheint.
3. Im Cockpit *Als erledigt markieren* wählen. Erwartet: Status *Erledigt*.

Automatisch: `test_service.py::test_full_flow_to_done_frees_agent_after_review`, `test_app.py::test_done_via_cockpit_with_origin_and_csrf`

Ergebnis: ☑️ bestanden ☐ nicht bestanden. Notiz:

## Test 5: Neustart

1. Mehrere Aufträge in verschiedenen Zuständen erzeugen (Review, Blocker, laufend).
2. Dienst beenden und neu starten.
3. Erwartet: Alle Aufträge, Zustände, Zusammenfassungen und Ereignisse unverändert im Cockpit.

Automatisch: `test_service.py::test_state_survives_service_restart`

Ergebnis: ☐ bestanden ☐ nicht bestanden. Notiz:

## Test 6: Fehlerfall

1. Karla einen längeren Auftrag geben (zum Beispiel: alle `.md`-Dateien in `docs/` einzeln zusammenfassen).
2. Während der Arbeit das VS-Code-Fenster schließen.
3. Erwartet: Der Auftrag erscheint nie als *Review erforderlich* oder *Erledigt*. Er wird als *möglicherweise verwaist* markiert und nach etwa zwei Minuten *Fehlgeschlagen*. Karla ist danach wieder frei. Alternativ im Cockpit *Abbrechen*.

Automatisch: `test_service.py::test_interrupted_work_is_never_shown_as_success`, `test_hooks.py::test_session_end_flags_active_task_but_never_completes_it`

Ergebnis: ☐ bestanden ☐ nicht bestanden. Notiz:

## Test 7: Mehrere Projekte

1. Karla in Projekt A und (nach Abschluss) in Projekt B beauftragen. In keinem der Projekte wurde etwas installiert.
2. Erwartet: Beides funktioniert, das Cockpit zeigt je Auftrag das richtige Projekt.

Automatisch: nicht möglich (braucht echte Projekte). Im Spike bereits mit `sw-capitalization` und `personal-assistant` gezeigt.

Ergebnis: ☐ bestanden ☐ nicht bestanden. Notiz:

## Test 8: Klaus delegiert (nur manuell prüfbar)

Voraussetzung: `install.py` erneut ausgeführt (kopiert `klaus.md`), Dienst neu gestartet, VS-Code-Fenster neu geladen.

1. `@agent-klaus Lass Karla die README auf Lücken prüfen und Lotta daraus eine Checkliste bauen.` ausführen.
2. Erwartet im Cockpit: Auftrag von Klaus (In Arbeit) und zwei Unteraufträge für Karla und Lotta mit „Unterauftrag von #N“. In der Detailansicht von Klaus stehen die Unteraufträge, in deren Detail steht „Beauftragt von“.
3. Karla vorher per `@agent-karla` beschäftigen und Test wiederholen. Erwartet: Klaus wird die Delegation verweigert, er meldet einen Blocker oder weicht aus, er arbeitet nicht selbst.
4. Prüfen, ob Klaus mit `complete_task` auf die Unteraufträge wartet. Offen (nicht belegt): Subagenten laufen standardmäßig im Hintergrund, ob Klaus nach deren Ende wieder aufgeweckt wird oder vorher endet, ist ungemessen. Endet Klaus vorher, steht sein Auftrag auf *Review erforderlich* (unvollständig), die Unteraufträge laufen eigenständig weiter.

Automatisch: Hook- und Service-Logik in `tests/test_delegation.py`. Das Verhalten von Claude Code (verschachtelte Subagenten) ist nicht automatisch prüfbar.

Ergebnis: ☐ bestanden ☐ nicht bestanden. Notiz:

## Zusätzlich prüfen

- Dienst stoppen, `@agent-karla ...` ausführen. Erwartet: Start wird abgelehnt mit dem Hinweis, den Team-Manager zu starten. Ein `Explore`-Subagent läuft weiterhin normal. (Automatisch: `test_e2e.py::test_gate_fails_closed_for_team_agent_when_service_is_down`)
- Blocker melden lassen (Auftrag, der eine Entscheidung braucht). Erwartet: Cockpit zeigt *Blockiert* mit Grund, Benachrichtigung erscheint.
- Cockpit im Browser öffnen, zweiter Tab: Änderungen erscheinen ohne manuelles Neuladen.
