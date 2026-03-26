---
name: journal-pattern-analysis
description: Erstellt eine kurze inhaltliche Auswertung des Journal-Abschnitts "Generierter Inhalt (Jira)". Fokus auf Muster statt Metriken oder Ticket-Nacherzaehlung.
---

# Skill: Journal Pattern Analysis

Ziel: Aus dem Abschnitt `## Generierter Inhalt (Jira)` eines Tagesjournals eine knappe, inhaltliche Interpretation erzeugen und direkt in derselben Journal-Datei dokumentieren.

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
2. Vier Unterabschnitte auswerten:
   - `### Statuswechsel`
   - `### Kommentare`
   - `### Ticket-Änderungen`
   - `### Neu angelegte Tickets`
3. Muster verdichten in 3-5 Bullet-Points.
4. Auswertung als eigenen Abschnitt in dieselbe Journal-Datei schreiben/aktualisieren:
   - Abschnittstitel: `## Auswertung (Agent)`
   - Falls Abschnitt bereits existiert: Inhalt ersetzen (idempotent).
   - Falls Abschnitt nicht existiert: am Dateiende anhaengen.
5. Danach kurze Bestätigung im Chat geben.

## Ausgabeformat

Verwende diesen Stil:

- **Inhaltlicher Fokus:** <1 Satz zum dominanten Thema>
- **Arbeitsmodus:** <1 Satz zum Arbeitsmuster>
- **Zusammenarbeit:** <1 Satz zu Abstimmung/Feedback>
- **Risiko/Offene Kante:** <1 Satz, falls erkennbar; sonst "kein klares Risiko erkennbar">
- **Naechster sinnvoller Schritt:** <optional, 1 Satz>

## Schreibregeln fuer die Journal-Datei

- Die vorhandenen Abschnitte `## Manueller Inhalt` und `## Generierter Inhalt (Jira)` nicht veraendern.
- Ausschliesslich `## Auswertung (Agent)` neu anlegen oder aktualisieren.
- Keine Rohdaten aus den Event-Listen duplizieren; Fokus bleibt Interpretation.

## Do / Don't

**Do**
- Bewegungen interpretieren, nicht nur zaehlen.
- Wenn noetig vorsichtige Sprache: "deutet darauf hin", "spricht fuer".
- Aussagen nur aus vorhandenen Journaldaten ableiten.

**Don't**
- Keine erfundenen Ursachen.
- Keine langen Ticketlisten.
- Keine Metrik-zentrierte Zusammenfassung als Kern der Antwort.
