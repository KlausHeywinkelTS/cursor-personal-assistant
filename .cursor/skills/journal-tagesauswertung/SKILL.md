---
name: journal-tagesauswertung
description: Erzeugt für heute den automatischen Jira-Teil des Tagesjournals und stößt anschließend die inhaltliche Journal-Zusammenfassung mit Reflexions-Interview an. Verwenden bei „Tagesjournal auswerten“, „Journal für heute zusammenfassen“, „Tagesabschluss“ oder wenn der automatische Journalteil und die Zusammenfassung gemeinsam erstellt werden sollen.
---

# Journal-Tagesauswertung

## Ablauf

1. Den automatischen Jira-Teil des heutigen Journals aktualisieren:

   ```powershell
   py src/update_daily_journal.py --date YYYY-MM-DD --journal-dir journal
   ```

   `YYYY-MM-DD` durch das heutige Datum ersetzen.

2. Die erzeugte bzw. aktualisierte Journal-Datei `journal/YYYY-MM/journal-YY-MM-DD.md` lesen.

3. Danach den Skill `.cursor/skills/journal-pattern-analysis/SKILL.md` lesen und vollständig befolgen.

4. Das Reflexions-Interview starten. Dabei nur die erste Frage stellen und die Antwort abwarten:

   > Was siehst du heute als besonderen Erfolg – oder worauf bist du stolz oder glücklich?

5. Nach Abschluss des Interviews die drei Auswertungssektionen gemäß dem Journal-Pattern-Analysis-Skill in dieselbe Journal-Datei schreiben.

## Grenzen

- Der automatische Teil wird vor der Auswertung immer aktualisiert.
- `## Manueller Inhalt` und `## Generierter Inhalt (Jira)` bleiben unverändert.
- Für die Auswertung gelten die Interview- und Schreibregeln des Journal-Pattern-Analysis-Skills.
