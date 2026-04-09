---
name: issue-refinement
description: Führt ein strukturiertes Interview zur Jira-Issue-Refinement durch. Nutze diesen Skill wenn der Nutzer ein Issue refinen möchte, ein neues Issue anlegen will, oder alle "To be refined"-Issues bearbeiten möchte.
---

# Skill: Issue-Refinement-Interview

Ziel: Ein Jira-Issue mit der definierten 5-Block-Struktur befüllen und in Jira schreiben.
Vor jedem Schreibvorgang Bestätigung einholen.

> **Sprache:** Alle Inhalte, die in Jira geschrieben werden (Summary/Titel und alle 5 Blöcke), sind **immer auf Englisch** — unabhängig davon, in welcher Sprache der Nutzer den Input geliefert hat. Vor der Vorschau (Schritt 4) alle gesammelten Texte **inklusive Summary** ins Englische übersetzen, falls sie es nicht bereits sind. Bei bestehenden Issues mit deutschem Titel: den Summary-Vorschlag ebenfalls übersetzen und den Nutzer bestätigen lassen.

---

## Schritt 1: Einstieg und Modus bestimmen

Erkenne den Trigger-Modus aus der Nutzeranfrage:

| Modus | Erkennung | Vorgehen |
|---|---|---|
| **Einzelnes Issue** | Nutzer nennt Issue-Key (z.B. `PROPS-123`) | → Schritt 2a |
| **Batch: To be refined** | "Alle offenen", "to be refined", kein Key genannt | → Schritt 2b |
| **Neues Issue** | "Neu anlegen", "von Grund auf", kein bestehendes Issue | → Schritt 2c |

---

## Schritt 2a: Bestehendes Issue vorbereiten

```
py src/read_jira_issue.py -i PROPS-123
```

Aus der Ausgabe die 5 Blöcke extrahieren (Panels in der Description):
- `background`, `goal`, `acceptance_criteria`, `additional_information`, `stakeholder`

Bereits befüllte Blöcke als Vorschlag merken. Leere oder unklare Blöcke werden im Interview nachgefragt.

Dem Nutzer kurz zeigen, was bereits vorhanden ist:
> "Ich habe PROPS-123 gelesen. Summary: *[Summary]*. Background ist bereits befüllt, Goal und Acceptance Criteria fehlen noch. Fangen wir an?"

→ Weiter mit Schritt 3.

---

## Schritt 2b: Batch-Modus (alle "To be refined")

```
py src/list_my_issues.py --mode to-be-refined
```

Issues der Reihe nach bearbeiten. Pro Issue:
1. Nutzer fragen: "Möchtest du [PROPS-123] jetzt refinen, überspringen oder abbrechen?"
2. Bei "Ja": Issue laden (Schritt 2a), dann Interview (Schritt 3)
3. Bei "Überspringen": nächstes Issue
4. Bei "Abbrechen": gesamten Batch beenden

→ Weiter mit Schritt 3.

---

## Schritt 2c: Neues Issue erstellen

Folgende Informationen erfragen, bevor das Interview startet:

1. **Projekt-Key** (z.B. `PROPS`, `KH`) — falls unklar fragen
2. **Summary** — prägnanter Kurztitel (1 Satz, kein Verb am Anfang nötig)
3. **Issue-Typ** — Standard ist `Task`, nur abweichen wenn Nutzer es nennt

Issue anlegen sobald Summary + Projekt feststehen (noch vor dem Beschreibungs-Interview):
```
py src/update_jira_issue.py --create --project PROPS --summary "Summary hier"
```

Den zurückgegebenen Issue-Key merken. → Weiter mit Schritt 3.

---

## Schritt 3: Interview – Block für Block

**Interview-Regeln (auch in `.cursor/rules/personal-assistant.mdc`):** Pro Agenten-Nachricht höchstens **eine Frage**. Werden Optionen angeboten, mit **A, B, C, …** kennzeichnen.

Die 5 Blöcke **nacheinander** befragen. Für jeden Block:
- Ist ein Wert bereits vorhanden (aus Schritt 2a/2c): als Vorschlag zeigen, kurz zusammenfassen
- Nutzer kann bestätigen ("passt so"), ergänzen oder komplett neu formulieren
- Nutzer kann Block mit "leer lassen" oder "überspringen" auslassen → Block bleibt leer

### Block 1: Background / Problem Description
> "Was ist der Ausgangssituation und das Problem? Warum existiert dieses Issue?"

Tipps:
- Kontext für jemanden, der das Issue nicht kennt
- Historische Ursache, erkannte Lücke, Anfrage von außen

### Block 2: Goal
> "Welchem höheren Ziel dient dieses Issue? Was soll sich dadurch verbessern — nicht was geliefert wird, sondern welchen Outcome es erzeugt?"

Tipps:
- Outcome, nicht Output. Falsch: "Ein Dokument erstellen". Richtig: "Teams können Prozess X eigenständig ausführen."
- Falls der Nutzer Output nennt, nachfragen: "Und was wird dadurch besser?"

### Block 3: Acceptance Criteria
> "Wann gilt das Issue als erledigt? Vervollständige: 'We call this task done when ...'"

Tipps:
- Konkret und prüfbar formulieren
- Mehrere Kriterien sind möglich (Nutzer kann Aufzählung nennen)

### Block 4: Additional Information
> "Gibt es Links zu Miro-Boards, Confluence-Seiten, Slack-Threads oder weiterem Stakeholder-Input, der hier festgehalten werden soll?"

Tipps:
- Kann auch leer bleiben
- URLs direkt übernehmen

### Block 5: Stakeholder / Dependencies / Prerequisites
> "Wer ist beteiligt? Gibt es Abhängigkeiten zu anderen Issues oder Voraussetzungen, die erfüllt sein müssen?"

Tipps:
- Beteiligte Personen oder Teams nennen lassen
- Abhängigkeiten zu anderen Jira-Issues als KEY-Referenz festhalten

---

## Schritt 4: Vorschau und Bestätigung

Vor der Vorschau: **Summary und alle Blöcke ins Englische übersetzen**, falls sie nicht bereits auf Englisch sind. Die Vorschau zeigt immer den englischen Endtext (inkl. Titel), der so in Jira landet.

Alle gesammelten Blöcke strukturiert als Vorschau zeigen:

```
📋 Vorschau für PROPS-123: [Summary]

🔹 Background / Problem Description
[Text]

🔹 Goal
[Text]

🔹 Acceptance Criteria
[Text]

🔹 Additional Information
[Text oder "(leer)"]

🔹 Stakeholder / Dependencies / Prerequisites
[Text oder "(leer)"]

Soll ich das Issue mit dieser Description aktualisieren? [Ja / Nein / Ändern]
```

Bei **"Ändern"**: Nutzer nennt welchen Block, dann nur diesen Block neu befragen. Danach erneute Vorschau.

---

## Schritt 5: In Jira schreiben (nur nach Bestätigung)

**1. Blocks-Datei schreiben** (`cache/blocks.json`):
```json
{
  "background": "...",
  "goal": "...",
  "acceptance_criteria": "...",
  "additional_information": "...",
  "stakeholder": "..."
}
```
Leere Blöcke weglassen oder als leeren String `""` eintragen.

**2. Issue aktualisieren:**
```
py src/update_jira_issue.py -i PROPS-123 --blocks-file cache/blocks.json
```

**3. Status auf Backlog setzen** (nur wenn Issue vorher "To be refined" war):
```
py src/transition_jira_issue.py -i PROPS-123 --to "Backlog"
```

**4. Abschluss-Meldung** an den Nutzer:
> "PROPS-123 wurde aktualisiert und in den Backlog verschoben. [Link]"

Im Batch-Modus: weiter mit dem nächsten Issue (zurück zu Schritt 2b).
