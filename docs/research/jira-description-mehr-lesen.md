# Jira Cloud: Lässt sich das Kürzen der Description ("Mehr lesen") in der neuen Work-Item-Ansicht abschalten?

Recherchestand: 2026-11-23. Grundlage sind Atlassian-Changelogs, Support-Seiten, Community- und Entwickler-Community-Beiträge sowie jira.atlassian.com. Alle Seiten wurden über ein Fetch-Tool mit Zusammenfassung abgerufen oder als Suchauszug gesehen, nicht als Volltext gelesen. Der zentrale Atlassian-Community-Beitrag [1] konnte nicht abgerufen werden (nur Titel); seine Inhalte stammen aus Suchzusammenfassungen. Einzelne Aussagen sollten vor einer Entscheidung direkt auf der Quellseite geprüft werden.

Kennzeichnung: **belegt** = in einer Atlassian-Quelle gesehen. **Community-Hinweis** = Forenbeitrag oder Drittquelle. **unbekannt** = nichts gefunden.

## Kurzantwort

- **Konfigurierbar, sodass die Description immer komplett offen ist: unbekannt, vermutlich nein.** Weder in der Support-Doku zur Work-Item-Ansicht [2][3] noch in den Changelogs [4][5][6] oder auf jira.atlassian.com habe ich eine Einstellung (User, Space-Admin, Jira-Admin) gefunden, die das Kürzen der Description steuert. Auch das Verhalten selbst ("Mehr lesen" an der Description in der Hauptansicht) ist in keiner gefundenen Atlassian-Quelle beschrieben. Ein Beleg für "es gibt keine Einstellung" ist das nicht, nur ein Nichtfund.
- **Verwandtes, belegtes Verhalten:** Atlassian hat im Herbst 2026 zwei Kürzungen angekündigt. Lange Kommentare werden mit "See more"/"See less" gekürzt (Status "Rolling out") [5]. Im Tab "All" der Aktivitätsliste sind lange Descriptions und Details einklappbar (Status "Coming soon") [4][7]. Beides betrifft nicht ausdrücklich das Description-Feld im Hauptbereich.
- **Bester Workaround (Opt-out der neuen Ansicht):** Laut Atlassian lässt sich die neue Ansicht verlassen. Admins steuern sie über Einstellungen > System > Beta features > "Modern work item" [5]. Zusätzlich gibt es seit 29.09.2026 einen Admin-Schalter, mit dem die neue Ansicht verzögert werden kann [8]. Einzelne User können laut Community-Beitrag [1] (Suchzusammenfassung, Beta-Phase) über das Drei-Punkte-Menü oben rechts zur klassischen Ansicht zurück. Ob das nach dem Rollout noch gilt, ist unbelegt.
- **Roadmap/Feature Request:** Kein Ticket auf jira.atlassian.com und kein Roadmap-Eintrag zur gekürzten Description gefunden. Die Roadmap-Seite ließ sich nicht auswerten [9].
- **Unsicherheit:** Der genaue Mechanismus "Mehr lesen" an der Description ist nicht dokumentiert. Bevor du Admin-Schalter umlegst, solltest du kurz prüfen, ob die Kürzung wirklich von der neuen Ansicht kommt (klassische Ansicht testweise einschalten).

## Nachtrag: Exakter Button-Text "Show full description"

Der Button heißt in der englischen Oberfläche "Show full description" (Screenshot von PROPS-1258, Stand 2026-11-23: Description ist nach dem ersten Info-Panel abgeblendet, darunter der Link). Eine Nachsuche mit diesem Wortlaut (drei Websuchen, nur Suchauszüge) ergab:

- **Keine Treffer** in Support-Doku, Changelogs oder Community zu einem Button "Show full description" oder zu einer Einstellung, die ihn abschaltet. Die Kürzung der Description im Hauptbereich ist weiterhin in keiner Atlassian-Quelle beschrieben.
- **Verwandte, offene Anfragen (Cloud):** JRACLOUD-77108 (Description-Feld einklappbar machen) [18], JRACLOUD-80749 (Expand/Collapse-Buttons für Sections wie Description) [19], JRACLOUD-83632 (Verhalten von Expand-Makros in der Description) [20]. Alle drei sind Vorgänger-Wünsche, keiner behandelt das Kürzen mit "Show full description". Status nicht einzeln geprüft.
- **Einklappbare Sections:** Seit Juni 2025 lassen sich Sections wie Description und Activity per Chevron/Titel ein- und ausklappen [21] (Changelog-Eintrag laut Suchauszug). Das ist ein manuelles Einklappen, kein Setting für den Standardzustand. Ob die Kürzung dadurch beeinflusst wird, ist unbekannt.
- **Layout-Konfiguration** (Configure > Work item view) steuert, welche Felder wo erscheinen, nicht ob die Description gekürzt wird [2].
- **Ähnliche Fälle:** Embedded Jira Cards in Confluence kürzen die Description ebenfalls und bieten keine Option dagegen; Workaround dort ist der Preview-Button oder das Jira-Legacy-Makro [22] (Community-Hinweis, anderer Kontext).

Fazit: Der Befund aus der Kurzantwort bleibt unverändert. Eine Einstellung ist nicht belegt, der Opt-out der neuen Ansicht bleibt der einzig belegte Weg.

## Rollout-Status der neuen Ansicht

- **Beta:** Atlassian führt ein "refreshed work item experience" mit klarerem Layout ein. Der Changelog führt das als "New work item view in beta" mit Status "Rolling out". Admins aktivieren es unter Settings > System > Beta features über den Schalter "Modern work item" [5] (belegt). Beginn: laut Suchzusammenfassungen Anfang August 2026 (Changelog-Wochen 3.-10. und 10.-17. August) [6][10]. Die Wochenangaben der verschiedenen Zusammenfassungen sind nicht ganz konsistent.
- **Entwickler-Community:** Dort heißt es, das Original ("Work Item View 2.0") sei am 16.09.2026 angekündigt worden, mit Ziel "GA im Oktober-Release" und Opt-in als Open Beta. Am 23.10. berichtete ein Partner, dass einige Instanzen die neue Ansicht trotz ausgeschaltetem Feature-Flag bekommen haben [11] (Community-Hinweis von Partnern, Antworten von Atlassian-Engineering vorhanden, kein Beleg für einen Opt-out-Verlust).
- **Allgemeine Verfügbarkeit:** Der Jira-Releaseticker nennt unter dem 26.10.2026 "A clearer, more focused Jira work item": weniger Unruhe, weniger Klicks, Rollout "to all Jira Cloud sites through the end of the year", Felder/Automationen/Daten unverändert, "an option to switch back to the classic view anytime" [12] (belegt, Wortlaut aus Fetch-Zusammenfassung). Ein Drittanbieter-Tracker führt "New work item view is generally available" mit Datum 30.09.2026 und Status "Coming soon" [8] (Community-Hinweis/Drittquelle).
- **Einen eigenen Eintrag für November 2026 habe ich nicht gefunden.** "Vor ein paar Tagen" passt zum laufenden Rollout bis Jahresende, ist aber nicht einzeln belegt.
- **Admin-Steuerung:** Eintrag vom 29.09.2026 "Admin control toggle for the upcoming new work item view", Status "Generally available": Admins können wählen, ob Teams die neue Ansicht standardmäßig sehen oder verzögern, und das später ändern [8] (Drittquelle, nur Kurzbeschreibung).

## Details zu Konfiguration und Workarounds

### 1. Einstellungen für die Description selbst

- Die Doku zur Work-Item-Konfiguration sagt: Die Description kann je nach Field-Konfiguration ausgeblendet werden, lässt sich aber nicht aus dem Standard-Layout löschen. Layout lässt sich über "Configure" > "Work item view" oder über Screens > "View work item" anpassen [2] (belegt).
- Die Doku enthält nichts zu Einklappen, "Show more" bei der Description oder zu einer klassischen Ansicht [2][3] (belegt als Nichtfund in der Zusammenfassung).
- "Show x more fields" unten rechts betrifft Felder im Bereich "Hide when empty", nicht den Text der Description [2][3].

### 2. Klassische Ansicht / Opt-out

- **Admin:** Settings > System > Beta features > "Modern work item" [5] (belegt für die Beta-Phase). Seit 29.09. zusätzlich der Verzögerungs-Schalter [8].
- **User:** Zurückwechseln über das Drei-Punkte-Menü oben rechts [1] (Community-Hinweis, aus Suchzusammenfassung, Beta-Phase). Atlassians Releaseticker nennt nur "switch back to the classic view anytime", ohne Menüpfad [12].
- **Offen:** Ob der Weg nach GA bleibt oder später entfernt wird. Ein Enddatum für die klassische Ansicht habe ich nicht gefunden.
- **Nicht verwechseln:** Die Preview-Panels in Liste und Globaler Suche sind eine eigene Änderung. Dort wurde die Detail-Ansicht Mitte September 2026 abgelöst, ein Admin-Schalter "New work item layouts for List and Global Search" ist angekündigt, aber laut Ticket noch nicht verfügbar. Bis dahin gibt es ein Opt-out-Formular. Strg/Cmd-Klick öffnet Issues im neuen Tab als Vollbild [13] (belegt, Ticket JRACLOUD-96809, Status "Under Consideration"). Das betrifft nicht die Description-Kürzung.

### 3. Mögliche weitere Umgehungen (nicht geprüft)

- **Vollbild/Fokusansicht:** Direkt aufgerufene Issue-URL (statt Preview-Panel/Modal) zeigt die Vollseite. Ob dort die Description ungekürzt erscheint, ist unbekannt.
- **Link-Parameter:** Keinen gefunden.
- **Feld verlagern:** Ein älterer Community-Hinweis empfiehlt, lange Custom-Feld-Werte im Layout in den Description-Bereich statt in Context-Felder zu legen [14] (Community-Hinweis, bezieht sich auf abgeschnittene Feldwerte, nicht auf das Kürzen der Description). Ob das hier hilft, ist unbekannt.
- **Browser-Erweiterung/Userstyle:** Technisch denkbar, aber nicht recherchiert, nicht belegt und von Atlassian nicht unterstützt.

### 4. Feature Request, Bug, Roadmap

- **Gefunden, aber nur verwandt:** JRA-63617 (Activity-Tab: "show more" springt in das Editierfeld statt in-place aufzuklappen) [15] (alte Anfrage, Status nicht geprüft). JRACLOUD-70555 (Sammelticket "New Issue View in Jira Cloud") [16] (Sammelticket der früheren Umstellung, nicht dieser Änderung).
- **Nicht gefunden:** Ticket auf jira.atlassian.com oder Community-Thread, der genau "Description wird gekürzt, Mehr-lesen-Klick nötig" beschreibt. Roadmap: Die Cloud-Roadmap listet laut Suchzusammenfassung die überarbeitete Work-Item-Ansicht als Q4 2026 [17] (Suchzusammenfassung, nicht verifiziert).
- **Hinweis aus dem Community-Beitrag [1]:** Ein Kommentator (laut Suchzusammenfassung) wünschte sich, dass bei langer Description eine Zeile oben angeheftet bleibt, mit der man hochscrollen kann. Das deutet darauf hin, dass es Feedback zur Description-Länge gibt, belegt aber keine Kürzung. Der Beitrag ist laut Zusammenfassung geschlossen (35 Kommentare). Staff-Status der Kommentatoren unbekannt.

## Fallstricke

- **Quellenlage:** Ob "Mehr lesen" an der Description tatsächlich zur neuen Ansicht gehört oder aus einer App, einer Browser-Erweiterung oder einem anderen Rollout (z. B. Aktivitätsliste) stammt, ist nicht belegt.
- **Datumsangaben:** Die Zusammenfassungen nennen für Beta-Start und GA unterschiedliche Wochen und Daten (3.8., 10.8., 16.09., 30.09., 26.10.). Nur die Aussagen mit Quelle verwenden.
- **Opt-out ist temporär zu denken:** Atlassian nennt keinen Dauer-Opt-out. Der Rollout läuft laut [12] bis Jahresende. Für die preview-panel-Änderung ist der Opt-out ausdrücklich als zeitlich begrenzt beschrieben [13].
- **Nebenwirkung des Zurückschaltens:** Auch weitere Neuerungen der neuen Ansicht (Feld-Personalisierung, Aktivitätsfeed) fallen dann weg [1][12].
- **Nur Beta-Aussagen:** Der Menüpfad zum Zurückwechseln stammt aus der Beta-Ankündigung.

## Quellen

1. Atlassian Community, "A clearer, more focused Jira work item view is coming" (nicht abrufbar, nur Titel, Inhalt aus Suchzusammenfassungen; Autor-/Staff-Status unbekannt): https://community.atlassian.com/forums/Jira-articles/A-clearer-more-focused-Jira-work-item-view-is-coming/ba-p/3262002
2. Configure the work item details (Fetch-Zusammenfassung): https://support.atlassian.com/jira-software-cloud/docs/configure-the-issue-detail-view/
3. Update a work item's details (Fetch-Zusammenfassung): https://support.atlassian.com/jira-software-cloud/docs/update-a-work-items-details/
4. Atlassian Cloud changes Aug 31 to Sep 7, 2026 (Fetch-Zusammenfassung, Eintrag "A cleaner All activity tab in work items", COMING SOON): https://confluence.atlassian.com/cloud/blog/2026/09/atlassian-cloud-changes-aug-31-to-sep-7-2026
5. Atlassian Cloud changes Sep 7 to Sep 14, 2026 (Fetch-Zusammenfassung, Einträge "Comments: Truncation for long text" und "New work item view in beta", beide ROLLING OUT): https://confluence.atlassian.com/cloud/blog/2026/09/atlassian-cloud-changes-sep-7-to-sep-14-2026
6. Atlassian Cloud changes Aug 3 to Aug 10, 2026 (nur über Suchzusammenfassung gesehen): https://confluence.atlassian.com/cloud/blog/2026/08/atlassian-cloud-changes-aug-3-to-aug-10-2026
7. Atlassian Cloud changes Sep 14 to Sep 21, 2026 (Fetch-Zusammenfassung, gleicher Eintrag "A cleaner All activity tab", COMING SOON): https://confluence.atlassian.com/cloud/blog/2026/09/atlassian-cloud-changes-sep-14-to-sep-21-2026
8. Atlas-Bench, "Atlassian Cloud changes, tracked hourly" (Drittanbieter-Tracker, Fetch-Zusammenfassung, nur Titel/Kurzbeschreibung): https://www.atlas-bench.com/atlassian-cloud/changes?admin=1
9. Atlassian Cloud Roadmap (Seite nicht auswertbar, nur Navigation geliefert): https://www.atlassian.com/roadmap/cloud?selectedProduct=jsw
10. Atlassian Cloud changes Aug 10 to Aug 17, 2026 (nur über Suchzusammenfassung gesehen; Abruf lieferte den Eintrag nicht): https://confluence.atlassian.com/cloud/blog/2026/08/atlassian-cloud-changes-aug-10-to-aug-17-2026
11. Atlassian Developer Community, "Work Item View 2.0 for Ecosystem Partners" (Fetch-Zusammenfassung; Beiträge von Partnern und Jira-Engineering): https://community.developer.atlassian.com/t/work-item-view-2-0-for-ecosystem-partners/102697
12. Jira "What's new" (LaunchNotes), Eintrag 26.10.2026 (Fetch-Zusammenfassung): https://jirareleases.atlassian.com/
13. JRACLOUD-96809, Provide the ability to disable the global preview panels (Fetch-Zusammenfassung, Status Under Consideration): https://jira.atlassian.com/browse/JRACLOUD-96809
14. JRACLOUD-77950, Option to extend the width of a custom field (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRACLOUD-77950
15. JRA-63617, Expand the Show More link in Activity tab (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRA-63617
16. JRACLOUD-70555, New Issue View in Jira Cloud (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRACLOUD-70555
17. Cloud Roadmap-Eintrag laut Suchzusammenfassung (siehe [9], nicht verifiziert).
18. JRACLOUD-77108, Availability to collapse Description field (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRACLOUD-77108
19. JRACLOUD-80749, Provide expand/collapse button on sections like Description (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRACLOUD-80749
20. JRACLOUD-83632, Issue View - Description - Edit - Expand / Collapse (nur Suchzusammenfassung): https://jira.atlassian.com/browse/JRACLOUD-83632
21. Jira: Collapsible sections in work items, Juni 2025 (Drittanbieter-Changelog, nur Suchzusammenfassung): https://cloud-updates.released.so/2025-06-16
22. Community, Limit on description text of an embedded Jira item (nur Suchzusammenfassung, Staff-Status unbekannt): https://community.atlassian.com/forums/Confluence-questions/Limit-on-description-text-of-an-embedded-Jira-item/qaq-p/2935953
