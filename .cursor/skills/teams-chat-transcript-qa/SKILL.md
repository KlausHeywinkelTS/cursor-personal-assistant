---
name: teams-chat-transcript-qa
description: Extracts questions and answers from a Microsoft Teams chat plus a pasted meeting transcript, then creates an English Q/A artifact as HTML. Use when the user asks to read the last Teams messages, combine them with a transcript, list all questions and answers, or create Q/A output files from Teams meeting content.
---

# Skill: Teams Chat + Transcript Q/A

Ziel: Aus einem Teams-Chat und einem zusätzlich eingefügten Transcript eine übersichtliche englische Q/A-Liste erzeugen. Der Standard-Output ist eine HTML-Datei mit eingerückten Antworten.

## Eingaben klären

Der Nutzer sollte liefern:

- Teams-Chat-URL.
- Anzahl der zu lesenden Nachrichten, falls nicht explizit genannt: nachfragen. Wenn der Nutzer "letzte 50 Nachrichten" sagt, verwende 10 Fetch-Loops.
- Transcript oder Pfad zu einer Transcript-Datei.
- Gewünschtes Ausgabeformat: HTML

Wenn die Anfrage eindeutig ist, nicht unnötig nachfragen. Logisch betrachtet ist das ein einfacher Pipeline-Job, kein philosophisches Kolloquium.

## Teams-Chat lesen

- Lies zuerst den Skill `read-teams-messages`.
- Berechne die Fetch-Loops: `ceil(message_count / 5)`.
- Führe den Export aus:

```powershell
py "$env:USERPROFILE\.cursor\plugins\cache\props-cursor-skills\props-cursor-skills\80d7d7c856311608a487d9d0bb0a227393bb3f6c\skills\read-teams-messages\src\request_messages.py" --url "<teams_url>" --output "export" --loops <loops>
```

- Lies die ausgegebene JSON-Datei.
- Ignoriere Chat-Einträge mit `msg: null`, außer sie haben sinnvolle Replies.
- Replies in `replies` zuerst als mögliche Antworten auf die Parent-Nachricht prüfen.

## Fragen und Antworten extrahieren

Erfasse Fragen aus beiden Quellen:

- Explizite Fragen mit Fragezeichen.
- Implizite Fragen oder Requests, zum Beispiel "Can you give an outlook..." oder "I want to understand...".
- Follow-up-Fragen, wenn sie inhaltlich eigenständig sind.
- Nur Fragen aufnehmen, die direkt mit dem Inhalt der Session, dem Produkt, Feature-Fragen, Kundenpositionierung, Entscheidungen, offenen Punkten oder fachlichen Follow-ups zu tun haben.

Antworten zuordnen:

1. Erst direkte Replies im Chat nutzen.
2. Dann chronologisch folgende Chat-Nachrichten prüfen.
3. Dann passende Stellen im Transcript prüfen.
4. Wenn keine klare Antwort existiert: `No answer provided.`

Nicht aufnehmen:

- Reine Begrüßungen, Verabschiedungen, Moderationsfragen, technische Smalltalk-Hinweise oder Meeting-Orga-Fragen.
- Fragen, die nur den Ablauf der Session steuern und keinen fachlichen Inhalt tragen.
- Medien, GIFs, Reaktionen oder leere Chat-Einträge ohne Fragebezug.
- Doppelte Fragen, wenn Transcript und Chat denselben Punkt enthalten. In dem Fall zusammenführen.

Beispiele, die nicht aufgenommen werden:

- "Can everyone see my screen?"
- "Annika, do you have a question?"
- "Are there any other final questions?"

## Sprache und Format

Die Ausgabe ist immer Englisch.

Basisformat:

```text
Q: <question>
A: <answer>
```

Regeln:

- `Q:` und `A:` müssen fett sein, wenn das Zielformat HTML ist.
- Antworten im HTML nach rechts einrücken.
- Unbeantwortete Fragen klar markieren.
- Antworten verdichten, aber keine inhaltlichen Details erfinden.
- Wenn die Antwort aus mehreren Quellen stammt, die Informationen zu einer kompakten Antwort zusammenführen.

Verbindliche Tonvorgaben für Antworten:

- Schreibe mit forward-looking tone: Antworten sollen auf nächsten Nutzen, Entwicklung, Einordnung oder mögliche nächste Schritte ausgerichtet sein, sofern der Inhalt das hergibt.
- Vermeide starre oder ausschließende Formulierungen. Keine unnötig harten Aussagen wie "never", "only", "not possible", wenn die Quelle eine vorsichtigere Einordnung zulässt.
- Formuliere neutral und objektiv. Keine emotionalisierende, werbliche oder überdramatische Sprache.
- Verbessere Lesefluss und Verständlichkeit: kurze, klare Sätze; zusammengehörige Informationen bündeln; keine wörtliche Transcript-Nacherzählung, wenn eine präzise Zusammenfassung genügt.

## HTML erzeugen

Standardpfad:

`output/<YYYY-MM-DD>_<topic-slug>-qa.html`

HTML-Struktur:

```html
<section class="qa">
  <p class="question"><span class="label">Q:</span> Question text</p>
  <p class="answer"><span class="label">A:</span> Answer text</p>
</section>
```

CSS-Mindestanforderungen:

```css
.answer {
  margin-left: 42px;
  margin-top: 8px;
}

.label {
  font-weight: 700;
}
```

## Qualitätscheck

Nach dem Schreiben:

1. Prüfe, dass die Datei existiert.
2. Bei HTML: `ReadLints` auf die HTML-Datei ausführen.
3. Im Chat nur kurz bestätigen:
   - erzeugte Datei(en)
   - Anzahl der Q/A-Blöcke
   - ob unbeantwortete Fragen enthalten sind

Keine Jira- oder Confluence-Schreibvorgänge durchführen. Dieser Skill arbeitet nur mit Teams-Export, Transcript und lokalen Output-Dateien.
