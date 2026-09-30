# Jira Cloud: Kann der Typ eines Spaces nachträglich geändert werden?

Recherchestand: 2026-09-30. Grundlage sind Atlassian-Support-Seiten. Die Seiten wurden über ein Fetch-Tool mit Zusammenfassung abgerufen, nicht als Volltext gelesen. Einzelne Formulierungen sollten vor einer Migration direkt auf der Quellseite geprüft werden.

## Kurzantwort

- Ein direkter In-Place-Wechsel des Typs (team-managed <-> company-managed) ist laut Atlassian nicht vorgesehen. Der dokumentierte Weg: neuen Space anlegen, Work Items per Bulk Move verschieben. Atlassian nennt das einen "manuellen, komplexen Prozess" [1].
- Ein "Change template"-Button für bestehende Spaces wurde in den Atlassian-Dokus nicht gefunden. Die Doku "Convert a space to a different template or type" beschreibt ebenfalls nur Neuanlage plus Bulk Move [2]. Ob es 2026 eine neue In-Place-Funktion gibt, konnte nicht belegt werden (unsicher).
- Software <-> Business <-> Service (JSM) <-> Product Discovery: ebenfalls nur über neuen Space plus Move [2][6]. Ausnahme: Ein bestehender JSM-Service-Space kann um ITSM-Work-Categories erweitert werden [5].
- Berechtigung: für die Konvertierung laut [2] globale Berechtigung "Administer Jira"; für die Migration laut [1] Space-Admin-Rechte im Quell-Space.
- Risiken: Issue-Keys ändern sich, Custom-Field-Daten, Sprints, Versionen, Subtasks und Links können verloren gehen.

## Details je Szenario

### 1. Team-managed <-> company-managed

- Es gibt keine direkte Konvertierung. Vorgehen laut [1]: neuen Ziel-Space (team- oder company-managed) anlegen, dann Suche -> Bulk change work items -> Move work items, Ziel-Space und Work Type wählen, Pflichtfelder füllen, bestätigen.
- Berechtigung laut [1]: Space-Admin mit "Administer spaces" und "Browse spaces".
- Team-managed -> company-managed laut [1]:
  - Ein Jira-Admin muss Custom Fields, Workflows/Status, Work-Type-Schema und Berechtigungsschema manuell einrichten.
  - Verloren gehen Story-Point-Schätzungen (abweichende Feldstruktur) und Report-Daten.
  - Custom-Field-Daten müssen neu erstellt werden.
- Company-managed -> team-managed laut [1] und [2]:
  - Sprints werden nicht mitgenommen.
  - Komponenten-Daten, Versionen/Releases, Story Points und Report-Historie (Velocity, Burnup) gehen verloren.
  - Work Items landen im Backlog; Custom Fields erscheinen leer.
  - Laut [2]: Work-Item-Links existieren im neuen Space nicht mehr, Subtasks gehen verloren.
  - Parallele Sprints werden in team-managed nicht unterstützt.
- Workaround für Custom-Field-Daten laut KB [3]:
  1. Daten aus dem team-managed Space exportieren.
  2. Bulk Move durchführen.
  3. Aus dem Ziel exportieren, CSV mit den neuen Keys aktualisieren.
  4. Custom-Field-Daten per CSV-Import wieder einspielen.
  - Bulk Move überträgt laut [3] Systemfelder, Kommentare und Anhänge, aber keine Custom-Field-Daten. Erst mit kleinem Testdatensatz probieren.
- Atlassian empfiehlt einen Test in einer Sandbox [1] bzw. ein Backup vor Bulk-Operationen [2].

### 2. Wechsel zwischen Templates und Projekttypen

- Doku [2]: Ein Wechsel zwischen Templates/Typen (z. B. company-managed Scrum -> team-managed Kanban, Jira Software <-> Jira Service Management, Vereinfachung auf Basic-Template) läuft in drei Schritten: neuen Space mit Ziel-Template anlegen, Work Items in der Listenansicht filtern, Bulk Move mit Status-Mapping. Hinweis: Die Doku listet nicht explizit, welche Konvertierungen unterstützt sind.
- Software <-> Business: Nicht direkt umschaltbar; neuen Space anlegen und Work Items verschieben [4].
- JSM: Bei Service-Spaces kann ITSM-Funktionalität über "Add a work category" ergänzt werden. Laut Navigation der Seite [5] sind team- und company-managed Service-Spaces gelistet, die Kategorie ist wieder entfernbar (Seite "Remove a work category"). Schritte und Rechte standen im abgerufenen Auszug nicht (unsicher).
- Product Discovery: Community-Antworten (Staff-Status nicht geprüft, daher nur Hinweis) sagen, ein bestehendes Projekt lasse sich nicht in Product Discovery umwandeln, wegen abweichender Issue-Hierarchie [6]. Ideen lassen sich per Bulk Move in andere Projekte verschieben (Beschreibung, Insights, Kommentare bleiben laut dieser Quelle erhalten, Felder müssen neu gesetzt werden) [6]. Nicht primärquellen-belegt.
- Ein eigenes Feature "Change template" für bestehende Spaces: nicht gefunden. In [1] steht "Change" unter "Template" nur bei der Neuanlage eines company-managed Spaces (Suchergebnis zu [7]).

### 3. Nötige Berechtigungen

- Globale Berechtigung "Administer Jira" für Konvertierung/Neuanlage company-managed Spaces [2][7].
- Space-Admin ("Administer spaces", "Browse spaces") für die Migration laut [1].
- Bulk Move: "Move work items" im Quell-Space und "Create work items" im Ziel-Space [8].
- KB [3] verlangt für den gesamten Transfer Administratorzugriff.

### 4. Nachbereitung

Custom Fields, Workflows, Schemes und Boards im Ziel-Space konfigurieren. Custom-Field-Daten wie oben per CSV nachziehen [1][3].

## Fallstricke

- Issue-Keys: Die Quellen widersprechen sich. [1] nennt automatische Aktualisierung mit Weiterleitung, [2] und [3] sagen, Keys ändern sich (neuer Space-Prefix). Praktisch: mit neuen Keys rechnen, Verweise in Confluence, Dokumenten und Automationen prüfen. Ob alte Links dauerhaft weiterleiten, ist nach den Quellen nicht abschließend geklärt.
- Workflows: Bei unterschiedlichen Workflows kann Datenverlust auftreten; Status müssen gemappt werden [9].
- Custom Fields: Werte bleiben nur bei gleichem Typ und Namen erhalten [9]; sonst neu anlegen bzw. per CSV nachladen [3].
- Subtasks: müssen mit in den Ziel-Space verschoben werden [9]; beim Wechsel auf team-managed gehen sie laut [2] verloren.
- Boards/Sprints: Sprints wandern nicht in team-managed Spaces; Report-Historie geht verloren [1]. Board-Konfiguration ist space-spezifisch und wird nicht migriert (aus [1]/[2] abgeleitet, nicht explizit belegt).
- Links und Epic-Verknüpfungen: Work-Item-Links können verloren gehen [2].
- Story Points: Schätzungsdaten gehen verloren, Feature kann neu aktiviert werden [1][2].
- JSM-Requests/Portal: nicht in den abgerufenen Seiten behandelt (unbekannt).
- Vorab Backup/Sandbox und kleiner Testlauf [1][2][3].

## Quellen

1. Migrate between team-managed and company-managed spaces: https://support.atlassian.com/jira-software-cloud/docs/migrate-between-team-managed-and-company-managed-projects/
2. Convert a space to a different template or type: https://support.atlassian.com/jira-cloud-administration/docs/convert-a-project-to-a-different-template-or-type/
3. Transfer data from team-managed to company-managed Jira spaces (KB): https://support.atlassian.com/jira/kb/transfer-data-from-team-managed-to-company-managed-jira-spaces/
4. Create a business space: https://support.atlassian.com/jira-software-cloud/docs/create-a-business-project/
5. Move an existing service space to the ITSM template: https://support.atlassian.com/jira-service-management-cloud/docs/can-i-move-my-existing-project-to-the-new-itsm-template/
6. Community, Product Discovery vs Jira Project (nur Hinweis, Staff-Status ungeprüft): https://community.atlassian.com/forums/Jira-Product-Discovery/Product-Discovery-Project-vs-Jira-Project/td-p/2178202
7. Create and edit a space: https://support.atlassian.com/jira-cloud-administration/docs/create-and-edit-a-project/
8. Move multiple work items (Berechtigungen laut Suchauszug): https://support.atlassian.com/jira-software-cloud/docs/move-multiple-issues/
9. Move multiple work items (Limitierungen): https://support.atlassian.com/jira-software-cloud/docs/move-multiple-issues/
