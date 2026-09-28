---
name: product-priority-meeting-summary
description: Erstellt aus einem Meeting-Transcript eine prägnante englischsprachige Zusammenfassung von Priorisierungsabstimmungen zwischen Business und Produktentwicklung. Der Fokus liegt auf Entscheidungen zu aktuellem und nächstem Team-Fokus sowie auf fachlichen Fragen und ihren Antworten. Verwenden, wenn ein Meeting-Transcript zusammengefasst oder Produktteam-Prioritäten abgestimmt werden sollen.
---

# Skill: Produktprioritäten aus Meeting-Transcript

Ziel: Ein Meeting-Transcript zu einer Priorisierungsabstimmung zwischen Business und Produktentwicklung in eine kurze, entscheidungsorientierte Zusammenfassung auf Englisch überführen. Im Mittelpunkt steht, woran Produktteams arbeiten und was sie als Nächstes tun sollen.

## Eingabe

- Nutze ein eingefügtes Transcript oder lies die vom Nutzer genannte lokale Datei.
- Wenn der Kontext des Meetings nicht aus dem Transcript hervorgeht, verwende: Abstimmung von Prioritäten für Produktteams zwischen Business und Produktentwicklung.
- Bei einem unvollständigen oder offensichtlich abgeschnittenen Transcript darauf hinweisen; trotzdem die vorhandenen Entscheidungen auswerten.

## Auswertung

1. Extrahiere nur tatsächlich getroffene Entscheidungen. Vorschläge, Meinungen, Prüfaufträge und Absichtserklärungen nicht als entschieden darstellen.
2. Fasse verwandte Aussagen zu einer Entscheidung zusammen.
3. Halte bei jeder Entscheidung fest, soweit aus dem Transcript ableitbar:
   - betroffenes Team oder Produktbereich,
   - aktuelle Priorität bzw. laufende Arbeit,
   - nächste Priorität bzw. nächster Arbeitsschritt,
   - Begründung, Abhängigkeit oder Zeitpunkt.
4. Ignoriere, wer etwas gesagt hat. Keine Sprecherzuordnung, keine Gesprächschronologie.
5. Extrahiere fachliche Fragen und ordne die im Transcript gegebene Antwort zu.
6. Wenn keine klare Antwort vorliegt, als `Offen – keine Antwort im Transcript` kennzeichnen. Moderations-, Verständnis- und Organisationsfragen auslassen.
7. Keine Informationen ergänzen, die nicht im Transcript stehen. Unsichere Aussagen als unsicher markieren.

## Ausgabe

Erstelle die Zusammenfassung auf Englisch als vollständige HTML-Datei.

1. Stelle sicher, dass das Verzeichnis `tmp/` im Workspace existiert.
2. Speichere die Datei unter `tmp/product-priority-meeting-summary-YYYY-MM-DD-HHMMSS.html`.
3. Verwende UTF-8, `lang="en"` und eine semantische Struktur mit `main`, `section`, Überschriften und Listen.
4. Gib nach dem Erstellen nur den Pfad zur erzeugten HTML-Datei im Chat aus.

Nutze in der HTML-Datei diese Struktur:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Priority alignment: &lt;Title or date&gt;</title>
</head>
<body>
  <main>
    <h1>Priority alignment: &lt;Title or date&gt;</h1>

    <section>
      <h2>Summary</h2>
      <p>&lt;Two to four sentences: the most important priority shifts and overall picture.&gt;</p>
    </section>

    <section>
      <h2>Decisions</h2>
      <ul>
        <li><strong>&lt;Decision as a clear statement&gt;</strong> — &lt;Affected team or product area&gt;. Current: &lt;current focus&gt;. Next: &lt;agreed focus or step&gt;. &lt;Rationale, dependency, or date, if stated.&gt;</li>
      </ul>
    </section>

    <section>
      <h2>Questions and answers</h2>
      <dl>
        <dt><b>Question:</b> &lt;subject-matter question&gt;</dt>
        <dd><b>Answer:</b> &lt;concise answer or “Open — no answer in the transcript.”&gt;<br><br></dd>
      </dl>
    </section>

    <section>
      <h2>Open items</h2>
      <ul>
        <li>&lt;Only unresolved, relevant priority questions or dependencies.&gt;</li>
      </ul>
    </section>
  </main>
</body>
</html>
```

## Qualitätsregeln

- Entscheidungen stehen zuerst; keine Wiedergabe des Gesprächsverlaufs.
- Aussagen kurz und handlungsorientiert formulieren.
- Sind keine Entscheidungen erkennbar, das explizit schreiben statt Vorschläge als Entscheidungen umzudeuten.
- Den Abschnitt `Questions and answers` immer ausgeben; wenn es keine fachlichen Fragen gibt: `No subject-matter questions identified in the transcript.`
- Den Abschnitt `Open items` nur ausgeben, wenn es relevante offene Prioritätsfragen oder Abhängigkeiten gibt.
- Füge nach jedem `<dd>` mit einer Antwort `<br><br>` ein, damit zwischen Antworten jeweils eine Leerzeile bleibt.
- Escape HTML-Sonderzeichen aus Transcript und Zusammenfassung korrekt.
