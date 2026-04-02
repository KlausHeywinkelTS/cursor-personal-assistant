---
name: journal-pattern-analysis
description: Erstellt eine kurze inhaltliche Auswertung der Journal-Abschnitte "Generierter Inhalt (Jira)" + "Manueller Inhalt". Fokus auf Muster statt Metriken oder Ticket-Nacherzaehlung.
---

# Skill: Journal Pattern Analysis

Ziel: Aus dem Abschnitt `## Manueller Inhalt` (falls vorhanden und nicht leer) **und** `## Generierter Inhalt (Jira)` eine gemeinsame, knappe Interpretation erzeugen und direkt in derselben Journal-Datei dokumentieren. Wo manueller und Jira-Teil auseinanderlaufen (z. B. viel Tätigkeit nur im Manuellen, Jira still), das explizit einordnen.

## Prinzipien

- Keine reine Kennzahlenliste.
- Keine Wiederholung einzelner Tickets als Hauptinhalt.
- Fokus auf Bedeutung der Bewegungen:
  - thematische Schwerpunkte
  - Arbeitsmodus (Umsetzung, Feinschliff, Rueckschleifen, Exploration)
  - Zusammenarbeit/Kommunikation
  - moegliche Risiken, Blocker oder offene Enden

## Ablauf

1. Journal-Datei lesen.
2. `## Manueller Inhalt` auswerten: Themen, Arbeitsmodus, Abstimmungen, Frustrationen/Blocker, nur soweit dort beschrieben.
3. Vier Unterabschnitte unter `## Generierter Inhalt (Jira)` auswerten:
   - `### Statuswechsel`
   - `### Kommentare`
   - `### Ticket-Änderungen`
   - `### Neu angelegte Tickets`
   - sowie `### In Bearbeitung` fuer den Kontext „was haengt offen“.
4. Muster verdichten: manuell + Jira zusammen denken (z. B. „viel passiert, Jira leer“), nicht zwei getrennte Mini-Auswertungen.
5. Auswertung im Ausgabeformat (siehe unten) formulieren und als `## Auswertung (Agent)` in dieselbe Journal-Datei schreiben oder bestehenden Inhalt ersetzen (idempotent); Position: oberhalb von `## Manueller Inhalt`.
6. Kurze Bestätigung im Chat geben.

## Ausgabeformat

Verwende diesen Stil:

- **Generell**: <2 Sätze zu einer generellen Bewertung dieses Tages; manueller und Jira-Teil zusammenfassen wo sinnvoll>
- **Inhaltlicher Fokus:** <1 Satz zum dominanten Thema>
- **Arbeitsmodus:** <1 Satz zum Arbeitsmuster>
- **Zusammenarbeit:** <1 Satz zu Abstimmung/Feedback>
- **Risiko/Offene Punkte:** <1 Satz, falls erkennbar; sonst "kein klares Risiko erkennbar">
- **Naechster sinnvoller Schritt:** <optional, 1 Satz>

## Schreibregeln fuer die Journal-Datei

- Die vorhandenen Abschnitte `## Manueller Inhalt` und `## Generierter Inhalt (Jira)` nicht veraendern.
- Ausschliesslich `## Auswertung (Agent)` neu anlegen oder aktualisieren.
- Keine Rohdaten aus den Event-Listen duplizieren; Fokus bleibt Interpretation.
- Manuellen Inhalt nicht wörtlich abschreiben; nur für Muster und Einordnung nutzen (Kohärenz/Kontrast zu Jira).

## Do / Don't

**Do**
- Bewegungen interpretieren, nicht nur zaehlen.
- Wenn noetig vorsichtige Sprache: "deutet darauf hin", "spricht fuer".
- Aussagen nur aus vorhandenen Journaldaten ableiten (manueller Abschnitt und Jira-Abschnitt gelten dabei als Datenquellen).

**Don't**
- Keine erfundenen Ursachen.
- Keine langen Ticketlisten.
- Keine Metrik-zentrierte Zusammenfassung als Kern der Antwort.
