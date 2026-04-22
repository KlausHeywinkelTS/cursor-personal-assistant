---
name: journal-stub
description: Leere Tagesjournal-Datei anlegen (Markdown-Vorlage ohne Jira-Abruf). Workspace-Root, Ablage in journal/<YYYY-MM>/.
disable-model-invocation: true
---

# Journal-Vorlage (Stub)

## Wann

Der Nutzer will eine neue leere Journal-Datei für einen Tag – schnell, ohne Jira-Daten.

## Was der Agent tun soll

1. Arbeitsverzeichnis: **Projektroot** dieses Repos (`cursor-personal-assistant`).

2. **Terminalbefehl ausführen** (nicht die Datei von Hand schreiben):

   - Heute (kein Datum genannt):

     `py src/update_daily_journal.py --stub-only`

   - Bestimmtes Datum (Nutzer nennt `YYYY-MM-DD`):

     `py src/update_daily_journal.py --stub-only --date YYYY-MM-DD`

   - Anderer Journal-Ordner nur wenn der Nutzer ihn nennt:

     `py src/update_daily_journal.py --stub-only --journal-dir <Pfad>`

3. Wenn die Ausgabe meldet, die Datei existiere bereits: Kurz mitteilen, kein Überschreiben – Nutzer kann Datum ändern oder Datei entfernen.

4. Erfolg: Kurz den ausgegebenen Pfad bestätigen (das Skript legt den Monatsordner `journal/<YYYY-MM>/` bei Bedarf selbst an).

## Kurzreferenz

| Situation | Befehl |
| --- | --- |
| Vorlage für heute | `py src/update_daily_journal.py --stub-only` |
| Vorlage für Datum D | `py src/update_daily_journal.py --stub-only --date D` |
