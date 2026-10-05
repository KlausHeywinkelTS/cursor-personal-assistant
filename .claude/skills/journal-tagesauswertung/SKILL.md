---
name: journal-tagesauswertung
description: Stellt sicher, dass das heutige Tagesjournal existiert, und stößt anschließend die inhaltliche Journal-Zusammenfassung mit Reflexions-Interview an. Verwenden bei „Tagesjournal auswerten“, „Journal für heute zusammenfassen“, „Tagesabschluss“ oder wenn Journal-Vorlage und Zusammenfassung gemeinsam erstellt werden sollen.
---

# Journal-Tagesauswertung

## Ablauf

1. Sicherstellen, dass das heutige Journal existiert (legt nur an, wenn es fehlt):

   ```powershell
   py src/update_daily_journal.py --date YYYY-MM-DD --journal-dir journal --stub-only-if-missing
   ```

   `YYYY-MM-DD` durch das heutige Datum ersetzen.

2. Die Journal-Datei `journal/YYYY-MM/journal-YY-MM-DD.md` lesen.

3. Danach den Skill `.claude/skills/journal-pattern-analysis/SKILL.md` lesen und vollständig befolgen.

4. Das Reflexions-Interview starten. Dabei nur die erste Frage stellen und die Antwort abwarten:

   > Was siehst du heute als besonderen Erfolg – oder worauf bist du stolz oder glücklich?

5. Nach Abschluss des Interviews die drei Auswertungssektionen gemäß dem Journal-Pattern-Analysis-Skill in dieselbe Journal-Datei schreiben.

## Grenzen

- Das Journal wird nur angelegt, wenn es fehlt; bestehende Dateien bleiben unverändert.
- `## Reflektion: Mein Tag heute` bleibt unverändert.
- Für die Auswertung gelten die Interview- und Schreibregeln des Journal-Pattern-Analysis-Skills.
