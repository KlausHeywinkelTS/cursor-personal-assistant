---
name: journal-monatsauswertung
description: Erzeugt eine Monats-Rückschau aus allen Tagesjournals eines Kalendermonats und speichert sie unter journal/monats-rueckschau/. Nutze diesen Skill bei „Monatsrückschau“, „Monatsauswertung“, „Erzeuge die Monatsrückschau“, „Fasse den Monat zusammen“ oder wenn der Nutzer eine Monatszusammenfassung aus den Journals will.
---

# Skill: Journal-Monatsauswertung

Ziel: Aus allen Tagesjournals eines Kalendermonats eine verdichtete Monats-Rückschau erzeugen – mit Fokus auf Erfolge und Wirkung, nicht auf Ticket-Nacherzählung. Die Ausgabe wird als Datei gespeichert und bei erneutem Aufruf idempotent aktualisiert.

Referenzbeispiele im Projekt:

- `journal/monats-rueckschau/monats-rueckschau-2026-07.md`
- `journal/monats-rueckschau/monats-rueckschau-2026-05.md`
- `journal/monats-rueckschau/monats-rueckschau-2026-04.md`

## Zeitraum bestimmen

1. Wenn der Nutzer einen Monat nennt (z. B. „Juli 2026“, „2026-05“): diesen verwenden.
2. Sonst: aktueller Kalendermonat.
3. Den ermittelten Monat kurz nennen, damit der Nutzer korrigieren kann. Bei eindeutigem Default direkt weitermachen.

## Datenquelle: Tagesjournale

1. Alle vorhandenen Dateien `journal/<YYYY-MM>/journal-<YY-MM-DD>.md` des Zielmonats lesen.
2. Fehlende Werktage überspringen – kein Journal erfinden.
3. Falls eine Datei vorhanden ist, aber `## Generierter Inhalt (Jira)` fehlt oder vollständig leer wirkt:
   - `py src/update_daily_journal.py --date YYYY-MM-DD --journal-dir journal` ausführen.
   - Datei danach neu lesen.
4. Tagesjournal-Dateien **nicht** verändern – außer dem explizit erlaubten Aktualisieren fehlender Jira-Teile (Schritt 3).

## Aus den Journals extrahieren

Pro Tag folgende Abschnitte auswerten (sofern vorhanden):

| Quelle | Wofür nutzen |
| --- | --- |
| `## Manueller Inhalt` | Themen, Arbeitsmodus, Abstimmungen, Frustrationen, Erfolge in eigener Worte |
| `## Termine` | Termindichte, Zusammenarbeit, Meeting-lastige vs. Fokus-Tage |
| `## Auswertung (Agent)` | Tages-Muster: inhaltlicher Fokus, Arbeitsmodus, Risiken |
| `## Erfolg & Stolz` | direkte Erfolg-Kandidaten |
| `## Positives Feedback` | Wirkung und Zusammenarbeit |
| `## Stimmungslage` | Belastung, Momentum, Kontrast zu Jira-Bewegung |
| `### Statuswechsel` | Abschlüsse (`Done`, bewusst `Rejected`) |
| `### Kommentare` | Zusammenarbeit, Blocker, Lob |
| `### Ticket-Änderungen` | tiefe Arbeit an Issues ohne Statuswechsel |
| `### Neu angelegte Tickets` | neue Stränge, Exploration |
| `### In Bearbeitung` | offene Kanten, Ping-Pong |

### Muster über den Monat verdichten

- **Themen:** Cluster aus wiederkehrenden Stichwörtern, Issue-Gruppen oder Tages-Auswertungen (≥ 2 Tage oder mehrere Tickets).
- **Arbeitsmodus:** Wechsel zwischen Umsetzung, Exploration, Abstimmung, Abschluss; Kontrast „viel Jira-Bewegung vs. viel manuelle/technische Arbeit“.
- **Zusammenarbeit:** Personen, Teams, Workshops, Enablement – aus manuellem Inhalt, Feedback und Kommentaren.
- **Offene Kanten:** bewusst geparkte Themen, wiederkehrende Blocker, unentschiedene Punkte.
- **Erfolge:** Abschlüsse, produktiv übergebene Artefakte, gelöste Blocker, positives Feedback – nicht nur „Ticket auf Done“.
- **Wirkung:** 2–4 Punkte, woran Nutzen sichtbar wurde (weniger manuelle Arbeit, klarere Prozesse, bessere Entscheidungsgrundlage, entlastete Kollegen).

## Ausgabedatei

Speichern unter:

`journal/monats-rueckschau/monats-rueckschau-YYYY-MM.md`

Bei erneutem Aufruf: bestehende Datei ersetzen (idempotent).

## Ausgabeformat

Template (an den Referenzbeispielen orientieren):

```markdown
# Monats-Rückschau <Monatsname> <Jahr>

## Auswertung (Agent)

<1–3 Sätze Einordnung des Monats als Fließtext>

- **Themen:** <dominierende Schwerpunkte verdichtet>. Relevante Tickets: PROPS-123, PROPS-456.
- **Arbeitsmodus:** <wie gearbeitet wurde, inkl. Kontrast Jira vs. manuell/technisch>. Relevante Tickets: PROPS-123.
- **Zusammenarbeit:** <mit wem, welche Formate, Feedback>. Relevante Tickets: PROPS-123.
- **Offene Kanten:** <was bewusst offen blieb oder hängt>. Relevante Tickets: PROPS-123.

## Erfolge

- <konkreter Erfolg mit Wirkung in 1–2 Sätzen>. Relevante Tickets: PROPS-123, PROPS-456.
- ...

## Wirkung

- <sichtbarer Nutzen, 1–2 Sätze>. Relevante Tickets: PROPS-123.
- ...

## Fokus-Impuls

- <genau ein rückblickender Verbesserungsimpuls für den nächsten Monat, konkret und konstruktiv>. Relevante Tickets: PROPS-123.

## Monatsüberblick

| Woche | Schwerpunkt | wichtigste Erfolge | offene Punkte |
| --- | --- | --- | --- |
| <Mo>–<Fr> <Monat> | <Kurzbeschreibung> | <1–2 Erfolge> | <1–2 offene Punkte> |
| ... | ... | ... | ... |
```

### Abschnittsregeln

- **`## Auswertung (Agent)`:** Einleitung als Fließtext, danach vier Bullets (Themen, Arbeitsmodus, Zusammenarbeit, Offene Kanten). Keine reine Ticketliste.
- **`## Erfolge`:** Schwerpunkt der Datei; 4–6 Bullets, wo möglich nach Wirkung gruppiert.
- **`## Wirkung`:** 2–4 Bullets; Nutzen für andere oder für Prozesse benennen.
- **`## Fokus-Impuls`:** **Genau ein** Bullet. Nicht zwei, nicht drei. Einer.
- **`## Monatsüberblick`:** Eine Zeile pro Kalenderwoche (Mo–Fr) mit Journal-Einträgen im Monat; Wochen ohne Journal weglassen oder als „kein Journal“ notieren, wenn die Woche sonst relevant wäre.

## Schreibregeln

- Sprache: Deutsch. Stil: präzise, sachlich, Siegfried-Tonalität. Erfolge im Vordergrund; Risiken knapp einordnen.
- Keine Erfindungen: jede Aussage muss auf Journal-Inhalt zurückführbar sein.
- Keine Ticket-Nacherzählung als Kern – Tickets dienen als Belege.
- Jeder Bulletpoint endet mit `Relevante Tickets: PROPS-123, PROPS-456`. Fehlt ein eindeutiger Ticket-Bezug: kein Bullet, sondern Fließtext in `## Auswertung (Agent)`.
- Markdown-linterkonform: nach jeder Überschrift genau eine Leerzeile.
- Nach Abschluss kurze Bestätigung im Chat mit Dateipfad.

## Do / Don't

### Do

- Monat als Geschichte erzählen: Aufbau, Wendepunkte, Abschlusswellen.
- Wiederkehrende Themen über mehrere Tage zusammenfassen.
- Kontrast benennen, wenn sichtbar (z. B. „viel technische Arbeit, wenig Jira-Bewegung“).
- Bei dünnem Monat ehrlich bleiben und kürzer schreiben.

### Don't

- Keine Tagesjournal-Dateien ändern (außer fehlender Jira-Teil).
- Keine mehrfachen Fokus-Impulse.
- Keine Bewertung jenseits der Daten („du solltest …“).
- Keine Rohdaten aus Event-Listen duplizieren.
