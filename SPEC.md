# Spezifikation: Persönlicher Arbeitsassistent (Cursor Agent)

**Version:** 1.0  
**Datum:** 2026-03-12  
**Erstellt aus:** Interview mit dem Nutzer (Process Manager, PrOps)

---

## 1. Zielbild

Ein Cursor-Agent, der als persönlicher Arbeitsassistent auf Basis von Jira und Confluence dient. Der Agent unterstützt bei der täglichen Selbstorganisation, der Pflege von Issues und dem Umgang mit Wartezeiten. Er kommuniziert auf Deutsch, reagiert nur auf explizite Anfragen (Pull-Prinzip) und hält Antworten mittellang - präzise, aber mit Kontext.

---

## 2. Rahmenbedingungen


| Parameter             | Wert                                                             |
| --------------------- | ---------------------------------------------------------------- |
| **Nutzer-Rolle**      | Process Manager, Product Operations (PrOps)                      |
| **Teamgröße**         | 4 Personen (überwiegend unabhängige Aufgabenbereiche)            |
| **Jira-Projekte**     | Mehrere (v.a. PROPS, KH) - kein Projekt-Filter, nur per Assignee |
| **Confluence**        | Aktiv genutzte Wissensbasis; teils in Issues verlinkt            |
| **Zulässige Quellen** | Nur Jira und Confluence (keine E-Mail, Kalender, Chat)           |
| **Interface**         | Cursor IDE (Agent / Cursor Rule / Skill)                         |
| **LLM**               | Nur Cursor-internes LLM - kein externes LLM                      |
| **Sprache**           | Deutsch                                                          |
| **Interaktionsmodus** | Pull (Agent handelt nur auf Nutzeranfrage)                       |
| **Credentials**       | `ATLASSIAN_USER` + `ATLASSIAN_TOKEN` (Umgebungsvariablen)        |
| **Atlassian-Domain**  | `https://trustedshops.atlassian.net`                             |


---

## 3. Jira-Datenmodell (Referenz)

### 3.1 Issue-Workflow-Status


| Status-Gruppe      | Status-Werte                                        |
| ------------------ | --------------------------------------------------- |
| Neu / Unbearbeitet | `To be refined`                                     |
| Geplant            | `Backlog`, `Next`, `To Do`, `ToDo`, `Ready to pull` |
| Aktiv              | `In Progress`, `Ongoing`                            |
| Wartend            | `Waiting`, `Blocked`, `On Hold`                     |
| Abgeschlossen      | `Done`, `Rejected`                                  |


**Persönliche Warteschlange:** Status `Next` = vom Nutzer manuell als "als nächstes angehen" markiert.

### 3.2 Issue-Description-Struktur (ADF Info-Panels)

Jedes Issue hat eine strukturierte Description mit folgenden Blöcken (je als ADF `panel` vom Typ `info`):


| Block                                          | Inhalt                                                                 |
| ---------------------------------------------- | ---------------------------------------------------------------------- |
| **Background / Problem Description**           | Ausgangssituation, Problem, warum dieses Issue existiert               |
| **Goal**                                       | Outcome (höheres Ziel, dem der Output dient) - nicht der Output selbst |
| **Acceptance Criteria**                        | "We call this task done when ..."                                      |
| **Additional Information**                     | Links zu Miro, Confluence, Stakeholder-Input, etc.                     |
| **Stakeholder / Dependencies / Prerequisites** | Beteiligte Personen/Teams, Abhängigkeiten, Voraussetzungen             |


### 3.3 Relevante Custom Fields


| Feld            | Bedeutung                                                         | Jira-Field-ID       |
| --------------- | ----------------------------------------------------------------- | ------------------- |
| **Remind date** | Datum, zu dem ein wartendes Issue wieder aufgegriffen werden soll | `customfield_10246` |


---

## 4. Bestehende technische Infrastruktur

Die folgenden Python-Skripte in `src/` sind bereits implementiert und bilden die Grundlage:


| Skript                        | Funktion                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| `src/read_jira_issue.py`      | Liest ein einzelnes Issue per Key, ADF→Markdown, cached in `cache/<key>.md`                |
| `src/search_jira_issues.py`   | Sucht Issues per JQL, cached Ergebnisse als JSON                                           |
| `src/read_confluence_page.py` | Liest Confluence-Seite per URL oder ID, ADF→Markdown, cached in `cache/confluence-<id>.md` |


**Gemeinsame Utilities (in `read_jira_issue.py`):**

- `_jira_search(jql, fields, max_results)` - paginierte JQL-Suche
- `_jira_get(path)` / `_jira_post(path, payload)` - authentifizierte REST-Calls
- `adf_to_markdown(adf_doc)` - ADF→Markdown-Konvertierung inkl. Info-Panel-Rendering
- `_render_adf_or_text(value)` - ADF oder Plain Text → Markdown

---

## 5. Feature-Spezifikationen

### Feature A: Issue-Refinement-Assistent *(Must-have)*

**Zweck:** Der Agent führt den Nutzer durch ein strukturiertes Interview und befüllt ein Jira-Issue mit der definierten Description-Struktur (5 ADF-Info-Panels). Anschließend zeigt er den Entwurf zur Bestätigung, bevor er in Jira schreibt.

**Trigger-Varianten:**


| Variante                             | Beschreibung                                                                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Bestehendes Issue verfeinern (A)** | Nutzer nennt Issue-Key (z.B. `PROPS-123`) - Agent liest vorhandene Description als Vorbefüllung und interviewt den Nutzer zur Ergänzung/Korrektur |
| **Bestehendes Issue verfeinern (B)** | Agent nimmt alle issues im Status "To be refined" als Input und verfährt Schritt-für-Schritt wie in Variante A                                    |
| **Neues Issue von Grund auf**        | Nutzer startet ohne vorhandenes Issue - Agent fragt zunächst nach Summary und Projekt, legt Issue an, dann Refinement                             |


**Interview-Ablauf:**

Der Agent befragt den Nutzer zu jedem Block nacheinander. Er nutzt vorhandene Informationen (aus der rohen Description oder Nutzerantworten) als Vorschlag und fragt nur nach, was fehlt oder unklar ist. Blöcke, die der Nutzer explizit überspringen möchte, bleiben leer.

1. **Summary** - Kurztitel des Issues (wenn noch nicht vorhanden)
2. **Background / Problem Description** - Was ist der Kontext? Welches Problem soll gelöst werden?
3. **Goal** - Welchem höheren Ziel (Outcome) dient dieses Issue? (Nicht: was wird geliefert)
4. **Acceptance Criteria** - Wann gilt das Issue als abgeschlossen?
5. **Additional Information** - Gibt es Links, Anhänge oder weiteren Stakeholder-Input?
6. **Stakeholder / Dependencies / Prerequisites** - Wer ist beteiligt? Was muss vorher erledigt sein?

**Ausgabe (Vorschau vor dem Schreiben):**

Der Agent zeigt die fertige Description in lesbarem Format (Markdown mit Panel-Kennzeichnung) und fragt:

> "Soll ich das Issue PROPS-123 mit dieser Description aktualisieren? [Ja / Nein / Ändern]"

**Nur nach Bestätigung:** Update per Jira REST API `PUT /rest/api/3/issue/{issueKey}` mit ADF-formatierten Panels.

**API-Anforderungen:**

- `GET /rest/api/3/issue/{issueKey}` - vorhandene Description lesen
- `POST /rest/api/3/issue` - neues Issue anlegen (bei Variante "von Grund auf")
- `PUT /rest/api/3/issue/{issueKey}` - Description + ggf. Summary aktualisieren
- ADF-Generierung: Info-Panel pro Block mit `panelType: "info"`

---

### Feature B: Remind-Date-Assistent *(Must-have)*

**Zweck:** Wenn der Nutzer nachfragt, zeigt der Agent alle Issues, deren `Remind date` heute oder früher liegt. Für jedes Issue bereitet er Kontext auf und schlägt Handlungsoptionen vor.

**Trigger:** Explizite Anfrage des Nutzers, z.B.:

- "Was sind heute meine fälligen Remind-Dates?"
- "Zeig mir meine Erinnerungen"

**Ablauf:**

1. JQL-Abfrage: Issues des Nutzers mit `cf[10246] <= now() AND status NOT IN (Done, Rejected)`
2. Für jedes fällige Issue wird angezeigt:
  - Issue-Key + Summary + aktueller Status
  - Wie lange wartet das Issue bereits (Differenz zwischen letztem Status-Wechsel zu Waiting/Blocked und heute)?
  - Bisheriger Verlauf aus Kommentaren als Zusammenfassung. Nennung eines konkreten next steps aus dem jüngsten Kommentar wenn vorhanden.
  - Ansprechpartner (aus Block "Stakeholder / Dependencies")
3. Handlungsoptionen (der Nutzer wählt pro Issue):
  - **Remind-Date verschieben** → Agent fragt nach neuem Datum, updated das Custom Field
  - **Follow-up Text formulieren** → Agent generiert eine kurze Nachfass-Nachricht (für manuellen Versand)
  - **Status ändern** → Agent fragt nach Zielstatus und updated das Issue
  - **Als Kommentar dokumentieren** → Agent schreibt kurzes "Stand heute"-Update als Jira-Kommentar
  - **Überspringen** → Issue wird ignoriert (Remind-Date bleibt)

**API-Anforderungen:**

- `POST /rest/api/3/search/jql` - Issues nach Remind-Date-Feld suchen
- `GET /rest/api/3/issue/{issueKey}/comment` - letzten Kommentar lesen
- `PUT /rest/api/3/issue/{issueKey}` - Remind-Date updaten, Status ändern
- `POST /rest/api/3/issue/{issueKey}/comment` - Kommentar hinzufügen
- `GET /rest/api/3/issue/{issueKey}/transitions` + `POST /rest/api/3/issue/{issueKey}/transitions` - Status-Transition

---

### Feature C: Tagesstart-Briefing *(Should-have)*

**Zweck:** Auf Anfrage gibt der Agent eine priorisierte Übersicht der aktuell relevanten Issues und schlägt vor, womit der Nutzer starten könnte.

**Trigger:** Explizite Anfrage, z.B.:

- "Was liegt heute an?"
- "Gib mir mein Tagesbriefing"

**Priorisierungslogik (in dieser Reihenfolge):**


| Priorität | Kriterium                                 | Begründung                                            |
| --------- | ----------------------------------------- | ----------------------------------------------------- |
| 1         | Status `In Progress` / `Ongoing`          | Bereits angefangen → Kontinuität                      |
| 2         | Status `Next` / `To Do` / `Ready to pull` | Vom Nutzer manuell priorisiert                        |
| 3         | Remind-Date = heute                       | Heute fällige Wartezeiten                             |
| 4         | Vorschlag aus `Backlog`                   | Agent wählt älteste oder relevant erscheinende Issues |


**Ausgabe:**

- Gruppe 1-2: Vollständige Liste mit Status und kurzem Summary
- Gruppe 3: Hinweis "X Issues haben heute ihr Remind-Date - Details mit 'Zeig Remind-Dates'"
- Gruppe 4: 1-3 Vorschläge aus dem Backlog mit kurzer Begründung (z.B. "liegt seit 30 Tagen unbearbeitet")
- Abschluss: Kurze Empfehlung "Ich würde heute mit [Issue X] starten, weil..."

**API-Anforderungen:**

- `POST /rest/api/3/search/jql` mit Filter `assignee = currentUser() AND status NOT IN (Done, Rejected)`
- Felder: `summary`, `status`, `created`, `updated`, `priority`, Custom Field Remind-Date

---

### Feature D: Wiedereinsteiger-Modus *(Nice-to-have)*

**Zweck:** Nach Abwesenheit (Urlaub, Krankheit, längerer Pause) verschafft der Agent einen schnellen Überblick über Veränderungen.

**Trigger:** "Was hat sich seit [Datum] verändert?" oder "Wiedereinsteiger-Modus"

**Ausgabe:**

- Neu zugewiesene Issues seit dem Datum
- Issues mit Status-Änderungen seit dem Datum
- Issues mit neuen Kommentaren seit dem Datum
- Kompakte Zusammenfassung: "Das Wichtigste auf einen Blick"

---

### Feature E: Confluence-Recherche zu einem Issue *(Should-have)*

**Zweck:** Für ein gegebenes Issue sucht und fasst der Agent verlinkte oder thematisch passende Confluence-Seiten zusammen.

**Trigger:** "Was gibt es in Confluence zu PROPS-123?" oder "Erkläre mir den Hintergrund zu [Issue]"

**Ablauf:**

1. Issue lesen - Links in "Additional Information"-Block extrahieren
2. Explizit verlinkte Confluence-Seiten abrufen und zusammenfassen (`read_confluence_page.py`)
3. Wenn keine Links vorhanden: Confluence-Suche per REST API mit Issue-Summary als Suchbegriff
4. Zusammenfassung der gefundenen Seiten mit Titel, Link und Key-Informationen

**API-Anforderungen:**

- `GET /wiki/api/v2/pages/{pageId}` - Seite lesen (bereits implementiert)
- `GET /wiki/rest/api/content/search?cql=...` - Confluence CQL-Suche

---

### Feature F: Teamleitungs-Update *(Nice-to-have)*

**Zweck:** Auf Wunsch generiert der Agent eine informelle Zusammenfassung des aktuellen Arbeitsstands für die Teamleitung.

**Trigger:** "Erstelle ein Update für meine TL"

**Ausgabe (informelles Format, kein festes Schema):**

- Was ist aktuell in Bearbeitung?
- Was wartet auf Zuarbeit von wem?
- Was wurde zuletzt abgeschlossen?
- Optional: Gibt es Blockaden oder Eskalationsbedarf?

---

### Feature G: Tagesjournal *(Should-have)*

**Zweck:** Der Nutzer kann pro Tag ein Journal führen. Das Journal besteht aus einem optionalen manuellen Abschnitt und einem automatisch generierten Abschnitt auf Basis aller relevanten Jira-Bewegungen des Tages.

**Trigger:** Explizite Anfrage des Nutzers, z.B.:

- "Erstelle heute mein Journal"
- "Zeig mir mein Journal von heute"
- "Aktualisiere den Jira-Teil im Journal"
- "Erstelle mir eine Wochenzusammenfassung"
- "Erstelle mir eine Monatszusammenfassung"

**Ablage & Dateinamen:**

- Ablageverzeichnis: `journal/<YYYY-MM>/`, ein Unterordner pro Kalendermonat (Beispiel: `journal/2026-04/`)
- Eine Datei pro Kalendertag
- Dateinamensschema: `journal-YY-MM-DD.md` (Beispiel: `journal/2026-03/journal-26-03-26.md`)
- Wenn die Datei für den Tag bereits existiert, wird sie aktualisiert statt neu angelegt
- Wochen-/Monatsrückschauen liegen separat unter `journal/wochen-rueckschau/`, damit Monatsordner reine Tagesjournale bleiben

**Dateistruktur pro Tag:**

```markdown
# Journal 2026-03-26

## Manueller Inhalt
<!-- Optional durch Nutzer gepflegt -->

## Generierter Inhalt (Jira)
### Statuswechsel
- PROPS-123 - To Do -> In Progress

### Kommentare
- PROPS-456 - Kommentar von Max: "..."

### Ticket-Änderungen
- PROPS-789 - Summary/Description aktualisiert

### Neu angelegte Tickets
- PROPS-999 - Summary
```

**Regeln:**

- **Manueller Inhalt ist optional**: Der Abschnitt darf leer bleiben.
- Beim Aktualisieren des Journals darf der Agent nur den Bereich `## Generierter Inhalt (Jira)` neu erzeugen; der manuelle Abschnitt bleibt unverändert.
- Der generierte Abschnitt enthält alle Jira-Bewegungen des Tages in vier Kategorien:
  - **Statuswechsel**
  - **Kommentare**
  - **Ticket-Änderungen**
  - **Neu angelegte Tickets**
- `Epic`-Issues werden ignoriert.
- Falls es in einer Kategorie keine Einträge gibt, wird dies explizit als "keine Einträge" ausgewiesen.

**Ermittlung der Jira-Bewegungen für den generierten Abschnitt (Tagesbasis):**

- Betrachtungszeitraum ist der konkrete Kalendertag des Journals (`00:00` bis `23:59`).
- Die vier Kategorien werden getrennt ermittelt:
  - **Statuswechsel:** Issues mit mindestens einer Transition am Tag.
  - **Kommentare:** Issues mit mindestens einem neuen Kommentar am Tag.
  - **Ticket-Änderungen:** Issues, die am Tag aktualisiert wurden (ohne reine Kommentar-Events), z.B. Summary/Description/Assignee/Priority.
  - **Neu angelegte Tickets:** Issues mit `created` am Tag.
- JQL-Basis pro Kategorie ist stets auf den Nutzer eingeschränkt: `assignee = currentUser()`.
- Ausgabe pro Eintrag mindestens: `Key`, `Summary`, Event-Typ; optional zusätzlich Zeitstempel und Link.

**Zusammenfassungen auf Anfrage (Wochen-/Monatsbasis):**

- Der Agent kann aus bestehenden Dateien unterhalb von `journal/<YYYY-MM>/` eine **Wochenzusammenfassung** oder **Monatszusammenfassung** erstellen.
- Die Zusammenfassung ist rein lesend/aggregierend und verändert keine Tagesjournal-Dateien.
- Standardmäßig berücksichtigt die Auswertung:
  - Bei Woche: die letzten 7 Kalendertage
  - Bei Monat: den aktuellen Kalendermonat (alternativ auf Anfrage: letzter voller Monat)

**Inhalt einer Zusammenfassung:**

- Kurzer Überblick (Anzahl berücksichtigter Journale, Zeitraum)
- Wichtigste Punkte aus `Manueller Inhalt` (nur wenn vorhanden)
- Konsolidierte Sicht auf Jira-Bewegungen der Periode (Statuswechsel, Kommentare, Änderungen, neue Tickets)
- Optionaler Abschluss: 2-5 Bullet-Points "Was wurde geschafft / was ist aufgefallen"

**Dateiquellen & Dateiformat für Aggregation:**

- Es werden ausschließlich Dateien mit Muster `journal-YY-MM-DD.md` aus den Monatsordnern `journal/<YYYY-MM>/` berücksichtigt (rekursiv über alle Monate). Dateien direkt in `journal/` oder in `journal/wochen-rueckschau/` zählen nicht.
- Tagesjournale ohne Inhalt in `Manueller Inhalt` bleiben für den Jira-Teil trotzdem voll gültig.

---

## 6. Implementierungsarchitektur

### 6.1 Cursor-Integration

Der Agent wird als **Cursor Rule** (`RULE.md` oder `.cursor/rules/`) implementiert, die:

- Dem LLM erklärt, welche Python-Skripte als Tools verfügbar sind
- Die Interaktionsmuster (Interview-Flow, Bestätigungspflicht vor Schreiboperationen) definiert
- Die Sprach- und Stilregeln festlegt (Deutsch, mittellang)

Für komplexe Flows (z.B. Issue-Refinement-Interview) wird zusätzlich ein **Cursor Skill** (`SKILL.md`) erstellt.

### 6.2 Neue Python-Skripte (zu entwickeln)


| Skript                         | Zweck                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------ |
| `src/update_jira_issue.py`     | Issue-Description (ADF) + Custom Fields updaten                                |
| `src/add_jira_comment.py`      | Kommentar zu Issue hinzufügen                                                  |
| `src/transition_jira_issue.py` | Status-Transition eines Issues ausführen                                       |
| `src/search_confluence.py`     | Confluence per CQL durchsuchen                                                 |
| `src/list_my_issues.py`        | Alle Issues des aktuellen Nutzers mit konfigurierbaren Feldern abrufen         |
| `src/update_daily_journal.py`  | Tages-Journal in `journal/<YYYY-MM>/` erstellen/aktualisieren (manuell + Jira) |
| `src/summarize_journals.py`    | Wochen- und Monatszusammenfassung aus `journal/<YYYY-MM>/` erzeugen            |


### 6.3 ADF-Generierung für Issue-Refinement

Die bestehende `adf_to_markdown()`-Funktion konvertiert ADF → Markdown (Lesen). Für das Schreiben wird eine inverse Funktion benötigt:

```python
def build_adf_info_panel(title: str, content: str) -> dict:
    """Erzeugt einen ADF info-Panel-Block mit Überschrift und Textinhalt."""
    ...

def build_issue_description_adf(blocks: dict[str, str]) -> dict:
    """
    Erzeugt die vollständige ADF-Description aus den 5 Blöcken.
    blocks = {
        "background": "...",
        "goal": "...",
        "acceptance_criteria": "...",
        "additional_information": "...",
        "stakeholder": "..."
    }
    """
    ...
```

---

## 7. Offene Punkte / Nächste Schritte


| #   | Thema                        | Aktion                                                                             |
| --- | ---------------------------- | ---------------------------------------------------------------------------------- |
| 1   | **Remind-Date Field-ID**     | ✅ Ermittelt: `customfield_10246`                                                   |
| 2   | **Cursor Rule erstellen**    | Agenten-Verhalten, verfügbare Tools und Interaktionsstil definieren                |
| 3   | **Skill: Issue-Refinement**  | Interview-Flow als Cursor Skill implementieren                                     |
| 4   | `**update_jira_issue.py`**   | ADF-Generierung + Jira-Write-API implementieren                                    |
| 5   | `**list_my_issues.py`**      | Vollständige Issue-Liste mit Remind-Date-Feld für Briefing und Remind-Date-Feature |
| 6   | `**update_daily_journal.py**`| Tagesjournal-Datei erzeugen, Jira-Teil aktualisieren, manuellen Teil erhalten      |
| 7   | `**summarize_journals.py**`  | Wochen-/Monatsjournal aus Tagesdateien aggregieren                                 |
| 8   | **Testen mit echten Issues** | End-to-End-Test mit PROPS-Issues im Cursor-Agent                                   |


---

## Anhang A: JQL-Referenz für dieses System

```
# Alle offenen Issues des Nutzers
assignee = currentUser() AND status NOT IN ("Done", "Rejected")

# Aktive Issues
assignee = currentUser() AND status IN ("In Progress", "Ongoing")

# Persönliche Warteschlange
assignee = currentUser() AND status IN ("Next", "To Do", "ToDo", "Ready to pull")

# Wartende Issues
assignee = currentUser() AND status IN ("Waiting", "Blocked", "On Hold")

# Issues mit fälligem Remind-Date
assignee = currentUser() AND cf[10246] <= now() AND status NOT IN ("Done", "Rejected")

# Backlog
assignee = currentUser() AND status = "Backlog" ORDER BY created ASC

# To be refined
assignee = currentUser() AND status = "To be refined" ORDER BY created ASC
```

