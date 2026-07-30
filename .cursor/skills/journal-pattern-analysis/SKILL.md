---
name: journal-pattern-analysis
description: Erstellt eine kurze inhaltliche Auswertung der Journal-Abschnitte "Generierter Inhalt (Jira)" + "Manueller Inhalt", erhebt vorher per Interview zwei Reflexionsfragen (Erfolg/Stolz, positives Feedback) und schreibt alles als eigene Sektionen in dieselbe Journal-Datei.
---

# Skill: Journal Pattern Analysis

Ziel: Aus den Abschnitten  `## Termine`, `## Manueller Inhalt` (falls vorhanden und nicht leer) **und** `## Generierter Inhalt (Jira)` eine gemeinsame, knappe Interpretation erzeugen und direkt in derselben Journal-Datei dokumentieren. Wo manueller und Jira-Teil auseinanderlaufen (z. B. viel Tätigkeit nur im Manuellen, Jira still), das explizit einordnen. Wenn besonders viele oder besonders wenig Termine, das berücksichtigen. Zusammenhang der Termine mit sonstiger Tätigkeit berücksichtigen, wenn ersichtlich.

Zusätzlich werden vor der Auswertung zwei Reflexionsfragen gestellt und ihre Antworten als eigene Journal-Sektionen verschriftlicht.

## Prinzipien

- Keine reine Kennzahlenliste.
- Keine Wiederholung einzelner Tickets als Hauptinhalt.
- Fokus auf Bedeutung der Bewegungen:
  - thematische Schwerpunkte
  - Arbeitsmodus (Umsetzung, Feinschliff, Rueckschleifen, Exploration)
  - Stimmungslage (wenn ersichtlich)

## Ablauf

1. Journal-Datei lesen.
2. **Reflexions-Interview** durchführen (max. eine Frage pro Agenten-Nachricht):
   - **Frage 1:** "Was siehst du heute als besonderen Erfolg – oder worauf bist du stolz oder glücklich?"
   - Antwort abwarten.
   - **Frage 2:** "Welches positive Feedback hast du heute bekommen?"
   - Antwort abwarten.
   - Bei "nichts", "nichts Besonderes" o. Ä. die jeweilige Sektion mit einer kurzen, ehrlichen Notiz ("Heute kein besonderer Punkt" / "Heute kein erinnerbares positives Feedback") füllen statt die Sektion wegzulassen.
   - Falls eine Sektion bereits in der Datei existiert: kurz nachfragen, ob ergänzt oder ersetzt werden soll.
3. `## Termine` auswerte: Dauer, Anzahl, was Besonderes oder eher Regeltermin, Zusammenhang mit anderen Aktivitäten falls ersichtlich.
4. `## Manueller Inhalt` auswerten: Themen, Arbeitsmodus, Abstimmungen, Frustrationen/Blocker, nur soweit dort beschrieben.
5. Vier Unterabschnitte unter `## Generierter Inhalt (Jira)` auswerten:
   - `### Statuswechsel`
   - `### Kommentare`
   - `### Ticket-Änderungen`
   - `### Neu angelegte Tickets`
   - sowie `### In Bearbeitung` fuer den Kontext "was haengt offen".
   - Jeder Eintrag in diesen Abschnitten beginnt mit einer Uhrzeit in Backticks (z. B. `` `09:15` ``). Diese Uhrzeiten nutzen, um den zeitlichen Ablauf des Tages zu rekonstruieren: Wann wurde aktiv gearbeitet? Gibt es erkennbare Schübe oder Unterbrechungen? Konzentrierte Arbeit vs. verteilte Aktivität über den Tag?
6. Muster verdichten: Termine + manuell + Jira + Reflexionsantworten zusammen denken (z. B. "viel passiert, Jira leer"; "Erfolg passt zu konzentrierter Arbeit am Vormittag"), nicht mehrere getrennte Mini-Auswertungen. Zeitliche Muster aus den Uhrzeiten in die Arbeitsmodus-Einschätzung einbeziehen.
7. Reflexionsantworten anreichern: Wo es sich aus den Daten ergibt, die Antworten mit konkreten Jira-Issues (Key + Summary), Terminen oder Hinweisen aus dem manuellen Inhalt verknüpfen. Verknüpfung nur, wenn der Bezug eindeutig aus den vorhandenen Journaldaten ableitbar ist – nicht raten.
8. Zwei Sektionen in dieselbe Journal-Datei schreiben (idempotent, neu anlegen oder bestehenden Inhalt ersetzen) in folgender Reihenfolge oberhalb von `## Manueller Inhalt`:
   1. `## Auswertung (Agent)`
   2. `## Stimmungslage`
   3. `## Positives Feedback`
9. Kurze Bestätigung im Chat geben.

## Ausgabeformat

### `## Auswertung (Agent)`

Verwende diesen Stil:

- **Generell**: <2 Sätze zu einer generellen Bewertung dieses Tages; manueller und Jira-Teil zusammenfassen wo sinnvoll>
- **Inhaltlicher Fokus:** <1 Satz zum dominanten Thema>
- **Arbeitsmodus:** <1 Satz zum Arbeitsmuster, inklusive zeitlicher Verteilung der Aktivität falls erkennbar>

### `## Stimmungslage`

- 1–3 Bullet-Points oder kurzer Fließtext, der Informationen in allen Bereichen bezüglich Stimmung zusammenfasst.

### `## Positives Feedback`

- 1–3 Bullet-Points oder kurzer Fließtext mit dem genannten Feedback.

## Schreibregeln fuer die Journal-Datei

- Die vorhandenen Abschnitte `## Manueller Inhalt` und `## Generierter Inhalt (Jira)` nicht veraendern.
- Ausschliesslich `## Auswertung (Agent)`, `## Stimmungslage` und `## Positives Feedback` neu anlegen oder aktualisieren.
- Reihenfolge der Sektionen oben in der Datei: `## Auswertung (Agent)` → `## Stimmungslage` → `## Positives Feedback` → `## Manueller Inhalt` → `## Generierter Inhalt (Jira)`.
- Keine Rohdaten aus den Event-Listen duplizieren; Fokus bleibt Interpretation.
- Manuellen Inhalt nicht wörtlich abschreiben; nur für Muster und Einordnung nutzen (Kohärenz/Kontrast zu Jira).
- Markdown-Linter-konform: nach jeder Überschrift genau eine Leerzeile.

## Do / Don't

**Do**

- Bewegungen interpretieren, nicht nur zaehlen.
- Wenn noetig vorsichtige Sprache: "deutet darauf hin", "spricht fuer".
- Aussagen nur aus vorhandenen Journaldaten und den im Interview gegebenen Antworten ableiten.
- Reflexionsfragen einzeln stellen und auf die Antwort warten.

**Don't**

- Keine erfundenen Ursachen.
- Keine erfundenen Verknüpfungen zwischen Reflexionsantwort und Jira-Issue.
- Keine langen Ticketlisten.
- Keine Metrik-zentrierte Zusammenfassung als Kern der Antwort.
- Keine Sektion `## Positives Feedback` ohne vorherige Frage erzeugen.
