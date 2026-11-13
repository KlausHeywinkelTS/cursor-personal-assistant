---
name: cvu-export-aufbereiten
description: Exportiert den Teams-Kanal „Customer voice - uncensored / Allgemein“ für einen Zeitraum (Monat, freier Datumsbereich, „letzte Woche“, „letzte zwei Wochen“, „letzter Monat“ – immer vollständig abgeschlossene Wochen bzw. Monate), erstellt daraus die Report-Datei reports/, entfernt Postings ohne Text, setzt die Teams-Links und extrahiert pro Posting eine mögliche Produktreaktion mit Ein-Satz-Zusammenfassung für Sales. Nutzen bei „CVU-Export für …“, „Export aufbereiten“, „Produktreaktionen extrahieren“.
disable-model-invocation: true
---

# CVU-Export aufbereiten

## Wann

Der Nutzer will für einen Zeitraum den CVU-Kanal exportieren, aufbereiten und die Produktreaktionen mit Sales-Zusammenfassung haben.

Eingabe: ein **Zeitraum**. Erkannte Formen:

- `letzte Woche`: letzte vollständig abgeschlossene Woche, Montag bis Sonntag.
- `letzte zwei Wochen` (oder `letzte 3 Wochen` usw.): die letzten N vollständig abgeschlossenen Wochen. Die laufende Woche zählt nicht.
- `letzter Monat`: letzter vollständig abgeschlossener Kalendermonat.
- `YYYY-MM` (z. B. `2026-10`): ein Kalendermonat.
- Freier Zeitraum: `YYYY-MM-DD` bis `YYYY-MM-DD`, beide Tage inklusive.

„Woche“ ist Montag bis Sonntag. Falls der Nutzer Mo–Fr meint, nachfragen. Ist kein Zeitraum erkennbar: nachfragen, nicht raten.

## Kanal

- Team: Customer voice - uncensored
- Kanal: Allgemein (intern `General`)
- Link: https://teams.microsoft.com/l/channel/19%3ACb34wC_FZkgoQKEx69-5e8CizMh4P1hY4OBqH7FIBVo1%40thread.tacv2/Allgemein?groupId=4a1913cf-829b-4e64-9628-57cbb21b89e5&tenantId=38e736cd-1e05-48a5-adeb-5ae85d3376ae

IDs (Team, Kanal, Tenant) stehen auch als Konstanten in den Scripts unter `src/`. Ändert sich der Kanal, dort und hier anpassen.

## Ablauf

Alle Befehle aus dem Projektroot. Pfade mit Leerzeichen immer in Anführungszeichen.

### 1. Export aus Teams

Der Export läuft über das Script `request_messages.py` des Skills `read-teams-messages`. Das Script schickt einen Webhook an Power Automate und wartet, bis die Datei im OneDrive-Ordner erscheint (max. 3 Minuten).

```
py "C:\Users\Kl6713\.claude\skills\read-teams-messages\src\request_messages.py" --url "<Kanal-Link oben>" --output "export_<Zeitraum-Kurzname>" --loops <N>
```

- `--loops N`: Jeder Loop holt 5 Hauptposts. Der Export zählt also immer die **letzten N Hauptposts** bis heute, egal welcher Zeitraum gewählt ist.
- Richtwert: Pro Woche gibt es höchstens 15 Hauptposts, also reichen für **eine Woche 3 Loops**. Hauptposts, die nach dem Ende des gewählten Zeitraums bis heute dazugekommen sind, rutschen vorne in das Fenster und zählen mit. Dafür je 5 solcher Posts einen Loop dazurechnen (z. B. 3 Loops plus 1 Loop bei 5 neuen Posts seit Wochenende).
- Für zwei Wochen entsprechend ca. 6 Loops, für einen Monat ca. 15 Loops (Oktober 2026 hatte 47 Hauptposts).
- Schritt 2 prüft die Abdeckung. Meldet er „Export reicht nur bis …“, den Export mit mehr Loops neu starten. Die alte Rohdatei nicht weiterverwenden.
- Der Befehl dauert ca. 1–2 Minuten. Bash-Timeout auf 600000 setzen.
- Die Ausgabe enthält `File created: <Pfad>`. Diesen Pfad als **Rohdatei** merken.
- Die Rohdatei nicht umbenennen oder verschieben. Die Links brauchen die Millisekunden aus der Rohdatei.
- Fehlt das Script, dem Nutzer sagen, dass der Skill `read-teams-messages` installiert sein muss.

### 2. Report-Datei erstellen

Je nach Eingabe einer der Befehle:

```
py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --zeitraum "letzte Woche"
py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --zeitraum "letzte zwei Wochen"
py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --month 2026-10
py -B src/cvu_export_erstellen.py --raw "<Rohdatei>" --from 2026-10-26 --to 2026-11-08
```

Das Script schreibt alle Hauptpostings im Zeitraum (Zeitzone Europa/Berlin) mit allen ihren Replies. Der Dateiname ist `reports/cvu-export-<YYYY-MM>.json` für einen ganzen Kalendermonat, sonst `reports/cvu-export-<von>_bis_<bis>.json`. Mit `--output` lässt sich der Name überschreiben. Postings ohne Text bleiben hier drin, Schritt 3 entfernt sie.

Exit-Code 1 mit „Export reicht nur bis …“: Der Export geht nicht weit genug zurück. Mit höherem `--loops` ab Schritt 1 neu starten. Eine alte Rohdatei nicht weiterverwenden.

Für Tests lässt sich das heutige Datum mit `--heute YYYY-MM-DD` festlegen.

### 3. Aufbereitung

```
py -B src/cvu_export_aufbereiten.py reports/cvu-export-<Monat>.json --raw "<Rohdatei>"
```

Das Script
- entfernt Postings mit `text = null` (Reaktionen, Dateien) und aktualisiert `meta.postings_count` und `meta.replies_count`,
- setzt `teams_link` je Posting aus der Rohdatei (Erstellzeit in Millisekunden UTC als Message-ID),
- setzt `votes` je Posting: Anzahl der D-Nummern (Muster `D` + Ziffern, z. B. D564431) im Hauptposting plus in allen Replies, als eine Summe. Jedes Vorkommen zählt einzeln,
- prüft die Struktur der Felder `product-response`.

Exit-Code 1 oder „Prüfung fehlgeschlagen“: Ausgabe dem Nutzer zeigen und nicht weitermachen, bis die Ursache klar ist. Die Befehle sind idempotent, ein zweiter Lauf ändert nichts.

### 4. Produktreaktion

Der Agent liest jedes verbleibende Posting mit seinen Replies (Report-Datei) und entscheidet pro Posting.

#### Was als Produktreaktion zählt

Ein Reply zählt, wenn er eine Aussage aus dem Produktbereich enthält, z. B.:

- Roadmap-Status („nicht geplant“, „kein Zeitplan“, „kommt“, „in Planung“, „2027-Planung“)
- Backlog oder Priorisierung („im Backlog“, „keine Kapazität“, „Fokus liegt auf …“)
- Discovery oder Recherche durch ein Produkt- oder Review-Team
- Zuständigkeit für ein Thema („gehört zu unserem Team“, „liegt bei Team X“)
- Aussage zu Funktionsweise oder Paketen, die über Fakten hinausgeht (z. B. Paketwechsel, Widget-Pläne)

Zählt **nicht**:

- reines „FYI“, Tags, Dank oder Weiterleitung ohne Inhalt
- Kundenstimmen, Vertriebs- oder CSM-Berichte ohne Produktaussage
- reine Engineering-Aussagen zu Bugs, Ausfällen und Deploys (Ticket-Nummern, Fix-Zeitpunkte)
- Abstimmung mit Legal oder Support ohne Produktposition
- Links oder Dokumentation ohne Bewertung

Im Zweifel nicht aufnehmen und dem Nutzer als unsicher melden. Der Nutzer entscheidet dann.

Der Export ist anonym. Ein Produktbezug wird nur am Inhalt festgemacht, nicht an Personen. Namen nur verwenden, wenn der Text die Person selbst als Verantwortliche nennt.

#### Ergebnis je Posting

Entweder `false`, wenn keine Produktreaktion erkennbar ist. Oder ein Objekt:

```json
"product-response": {
  "replies": [3, 11],
  "reason": "Erklärung in einem Satz oder zwei, ohne R-Nummern",
  "sales_summary": "Ein Satz, der für Sales ohne Vorwissen verständlich ist."
}
```

- `replies`: Reply-Nummern, 1-basiert, in der Reihenfolge der Replies im Report. Nur die Replies, auf die sich die Aussage stützt.
- `reason`: Begründung für den Nutzer, keine R-Nummern wie „R3:“ oder „R5“ im Text.
- `sales_summary`: genau ein Satz, Deutsch, ohne interne Fachbegriffe, wenn möglich mit der Konsequenz für den Kunden. Zusagen nur schreiben, wenn der Text eine Zusage enthält. Heißt es „kein Zeitplan“ oder „nicht geplant“, genau das sagen.

#### Schreiben

Das Feld `product-response` pro Posting setzen, andere Felder nicht anfassen. Danach Schritt 3 erneut laufen lassen, damit die Struktur geprüft wird.

Die Ausgabe an den Nutzer ist eine Markdown-Tabelle, die er in eine Teams-Nachricht kopieren kann. Sie enthält **alle Postings mit Text aus dem Zeitraum**, auch die ohne Produktreaktion. Die Reihenfolge ist nach `created_at` aufsteigend (ältestes zuerst).

| Titel des Posts | Votes | Produktreaktion (sales_summary) | Link |
|---|---|---|---|
| Kurzer Titel | 1 | `sales_summary`, sonst leer | [Link to message](teams_link) |

- **Titel des Posts:** Postings haben keinen Titel. Der Agent leitet einen kurzen deutschen Titel aus dem Inhalt ab, höchstens etwa 8 Wörter. Er beschreibt das Thema, z. B. „Control Centre: nicht mehr genutzte Shops ausblenden“, und nennt keine Personen.
- **Votes:** Wert aus `votes`.
- **Produktreaktion:** `sales_summary`, wenn `product-response` ein Objekt ist. Bei `false` bleibt die Zelle leer.
- **Link:** Linktext immer „Link to message“, URL aus `teams_link`.

Unsichere Fälle stehen nicht in der Tabelle, sondern werden getrennt im Abschluss gelistet.

## Abschluss

- Dem Nutzer melden: aufgelöster Zeitraum mit Datumsangabe (z. B. „letzte zwei Wochen = 26.10.–08.11.2026“), Anzahl Loops, Anzahl Hauptpostings und Replies im Zeitraum, wie viele Null-Posts entfernt wurden, wie viele Links gesetzt wurden, wie viele Postings eine Produktreaktion haben. Die Tabelle aus Schritt 4 mit allen Postings mit Text ausgeben.
- Unsichere Fälle separat auflisten, mit Begründung, warum sie nicht aufgenommen wurden.
- Die Rohdatei im OneDrive-Ordner liegen lassen. Sie ist die Quelle für die Links.
- Keine Dateien außerhalb von `reports/` verändern.
