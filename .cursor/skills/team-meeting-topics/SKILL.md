---
name: team-meeting-topics
description: Schlägt Themen aus den Tagesjournals einer Arbeitswoche (Mo–Fr) für ein wöchentliches Team-Meeting vor, gruppiert in Erfolge, Misserfolge/Blocker und größere Themen, inklusive Empfehlung welche drei Punkte zu teilen sind. Nutze diesen Skill wenn der Nutzer Themen zum Teilen im Team-Meeting, Wochenmeeting, Team-Sync, Team-Update, Weekly oder Team-Jour-fixe sucht oder fragt "Was teile ich im Team-Meeting?".
---

# Skill: Team-Meeting Themen

Ziel: Aus den Tagesjournals einer Arbeitswoche (Mo–Fr) drei Kategorien an Gesprächsthemen fürs wöchentliche Team-Meeting ableiten – mit Empfehlung am Ende, welche drei Punkte (einer pro Kategorie) der Nutzer tatsächlich teilen sollte.

Kategorien:

- **Erfolge** – besondere Abschlüsse, Stolz-Punkte, positives Feedback.
- **Misserfolge / Blocker** – mehrfach abgebrochene Versuche, externe Abhängigkeiten, Frustrationen.
- **Größere Themen** – mehrtägige Schwerpunkte, dominierende Themenstränge.

## Zeitraum bestimmen

1. Wenn der Nutzer ein Datum oder einen Zeitraum nennt: diesen verwenden.
2. Sonst Default ableiten aus dem heutigen Wochentag:
   - **Mo** → vergangene Mo–Fr-Woche.
   - **Di–Fr** → diese Woche Mo bis gestern.
   - **Sa/So** → die gerade vergangene Mo–Fr-Woche.
3. Den ermittelten Zeitraum **vor** der Auswertung nennen, damit der Nutzer kurz korrigieren kann. Beispiel: "Ich nehme KW 19, Mo 04.05. – Fr 08.05. – ok?". Bei eindeutigem Default nicht warten, sondern direkt weitermachen.

## Datenquelle: Journale

1. Pro Werktag (Mo–Fr) die Datei `journal/<YYYY-MM>/journal-<YY-MM-DD>.md` lesen.
2. Falls eine Datei fehlt: überspringen und im Output beim entsprechenden Tag "kein Journal" notieren.
3. Falls eine Datei vorhanden ist, aber `## Generierter Inhalt (Jira)` fehlt oder vollständig leer wirkt:
   - `py src/update_daily_journal.py --date YYYY-MM-DD` ausführen.
   - Datei danach neu lesen.
4. Journal-Dateien werden **nicht** verändert – nur gelesen.

## Aus dem Journal extrahieren

Pro Tag folgende Abschnitte auswerten (sofern vorhanden):

| Quelle | Wofür nutzen |
| --- | --- |
| `## Manueller Inhalt` | Erfolge, Frust, Themen mit eigener Bewertung des Nutzers |
| `## Auswertung (Agent)` → "Inhaltlicher Fokus" | Themenstränge der Woche |
| `## Auswertung (Agent)` → "Risiko/Offene Punkte" | Misserfolge / Blocker |
| `## Erfolg & Stolz` | direkte Erfolg-Kandidaten |
| `## Positives Feedback` | direkte Erfolg-Kandidaten (mit Quelle/Person, falls genannt) |
| `### Statuswechsel` | Erfolg (→ Done), Misserfolg (Ping-Pong wie In Progress → On Hold mehrfach) |
| `### Kommentare` | Kontext zu Erfolgen/Blockern, oft Hinweise auf externe Hängepartien |
| `### Neu angelegte Tickets` | neue Themen, manchmal Beginn eines größeren Strangs |
| `### In Bearbeitung` | Kandidaten für "größere Themen" über mehrere Tage |

### Erfolge erkennen

- Status-Wechsel auf `Done` oder `Rejected` (sofern bewusst rejected) in `### Statuswechsel`.
- Einträge unter `## Erfolg & Stolz` oder `## Positives Feedback`.
- Im manuellen Inhalt Begriffe wie "geschafft", "abgeschlossen", "fertig", "endlich".
- Issue mit mehreren positiven Kommentaren oder explizitem Lob im Kommentartext.

### Misserfolge / Blocker erkennen

Einzelne Hinweise reichen meist nicht – Kombinationen verstärken den Befund:

- Mehrfacher Status-Ping-Pong (z. B. `On Hold → In Progress → On Hold` in einer Woche).
- Issue, das über die ganze Woche "In Bearbeitung" steht, aber keine Done-Transition erreicht.
- Manueller Inhalt mit Begriffen wie "kein Fortschritt", "leider", "abgesagt", "verschoben", "nicht geschafft", "frustrierend", "blockiert".
- Auswertung (Agent) markiert dasselbe Risiko an mehreren Tagen.
- Kommentar deutet externe Abhängigkeit an ("warte auf X", "noch keine Antwort", "hängt bei …").

### Größere Themen erkennen

- Issue oder Stichwort taucht an **≥ 2 Tagen** der Woche in den Journals auf.
- Mehrere Issues mit gemeinsamem Kontext (z. B. mehrere `Wishlist`-Tickets, mehrere `P2M`-Tickets).
- Ein Issue mit hohem Kommentaraufkommen oder vielen Feld-Updates über die Woche.
- "Inhaltlicher Fokus" der Tages-Auswertung benennt dasselbe Thema an mehreren Tagen.

## Ausgabe (im Chat, keine Datei schreiben)

Reihenfolge: Erfolge → Misserfolge / Blocker → Größere Themen → Empfehlung.

Pro Vorschlag genau **eine** Zeile Überschrift + 1–2 Sätze Kontext + Quellenhinweis in Klammern (Datum + Jira-Keys).

Pro Kategorie **2–4** Vorschläge. Wenn weniger erkennbar: weniger anbieten und in einem Satz erklären warum (z. B. "Keine Misserfolge erkennbar – Woche lief glatt").

Template:

```markdown
## Themen für Team-Meeting (KW <NN>, <Mo-Datum> – <Fr-Datum>)

### Erfolge

- **<Kurzer Titel>** — 1–2 Sätze Kontext: was, mit wem, warum erwähnenswert. *(<YYYY-MM-DD>, <PROPS-Keys>)*
- ...

### Misserfolge / Blocker

- **<Kurzer Titel>** — 1–2 Sätze, was nicht funktioniert hat oder hängt, und woran es liegt (falls erkennbar). *(<YYYY-MM-DD>, <PROPS-Keys>)*
- ...

### Größere Themen

- **<Themen-Stichwort>** — 1–2 Sätze: an welchen Tagen, welche Tickets, aktueller Stand. *(<Tage>, <PROPS-Keys>)*
- ...

### Empfehlung

Logisch betrachtet würde ich diese drei teilen:

1. <Titel aus Erfolge> — weil <Grund>.
2. <Titel aus Misserfolge> — weil <Grund>.
3. <Titel aus Größere Themen> — weil <Grund>.
```

## Schreibregeln

- Sprache: Deutsch. Stil: nüchtern, kurz, Siegfried-Tonalität ("Logisch betrachtet…"). Keine Wertung außer dort, wo der Nutzer im manuellen Inhalt selbst gewertet hat.
- Keine Erfindungen: jeder Punkt muss auf einen konkreten Eintrag in einem Journal zurückführbar sein – Quelle in Klammern ist Pflicht.
- Mehrere Tage zu einem Punkt zusammenfassen, wenn sich das Thema wiederholt – nicht pro Tag duplizieren.
- Jira-Keys als Kurzform `PROPS-1234`; mehrere Keys kommagetrennt.
- Markdown-linterkonform: nach jeder Überschrift genau eine Leerzeile.

## Do / Don't

### Do

- Erfolge zuerst, dann Misserfolge, dann größere Themen – die Reihenfolge ist bewusst.
- Bei Misserfolgen den Grund nennen, wenn ableitbar (extern blockiert, eigene Termindichte, fehlender Fokus).
- Bei "Größere Themen" das Themenstichwort (Cluster) nennen, nicht nur einen einzelnen Jira-Key.
- Empfehlung am Ende immer geben – auch wenn die Kandidaten dünn sind.

### Don't

- Keine reine Ticketliste.
- Keine Punkte ohne Quellenangabe.
- Keine Bewertung jenseits der Empfehlung ("Du solltest XY anders machen" → nicht).
- Keine Datei schreiben – Output bleibt im Chat.
- Keine Journal-Datei verändern.
