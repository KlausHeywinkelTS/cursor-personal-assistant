# Monats-Rückschau Juli 2026

## Auswertung (Agent)

Der Juli war ein Umsetzungsmonat mit zwei verbundenen Schwerpunkten: Du hast operative PrOps-Arbeit durch konkrete Automatisierungen entlastet und parallel die Grundlage für belastbarere Prozesse rund um Software-Aktivierung und Aufwandserfassung gelegt. Die Arbeit wechselte dabei sinnvoll zwischen tiefen Fokusphasen für technische Umsetzung und gezielter Abstimmung mit Fachbereichen, PMs und Stakeholdern.

- **Themen:** Product Cast, die automatisierte Prio-Vorbereitung und der Jira Self-Service Assistant zeigen einen klaren Fokus auf skalierbare Self-Service- und Dokumentationsprozesse. Parallel wurden die SW-Capitalization mit einem Business-Case-Generator und die Aufwandserfassung durch Prototyping und App-Recherche operationalisiert. Relevante Tickets: PROPS-1143, PROPS-1153, PROPS-1157, PROPS-1166.
- **Arbeitsmodus:** Du hast technische Probleme nicht nur analysiert, sondern bis zu nutzbaren Ergebnissen weitergeführt: von der Rating-Extraktion über Product Cast bis zur automatisierten Erstellung von Business Cases. Die sichtbare Jira-Bewegung war dabei teilweise kleiner als die tatsächliche technische Arbeit. Relevante Tickets: PROPS-1152, PROPS-1163, PROPS-1166.
- **Zusammenarbeit:** Der Monat enthält viel konkrete Befähigung und Beziehungspflege: Jira-Einführungen für Field Experts, Workshops mit Support sowie Zusammenarbeit mit Viv, Judith, André, Vincent und Accounting. Positives Feedback kam sowohl für technische Ergebnisse als auch für deine Beiträge in Workshops und im Sparring. Relevante Tickets: PROPS-1135, PROPS-1148, PROPS-1161.
- **Offene Kanten:** Die Entscheidung zur datenschutzkonformen Aufwandserfassung ist noch nicht getroffen; die Lösungssuche brachte zwar eine getestete Option, aber auch relevante Kosten und Abstimmungsbedarf. Der Jira Self-Service Assistant ist fachlich und technisch vorbereitet, die eigentliche LLM-Umsetzung blieb jedoch im Backlog. Relevante Tickets: PROPS-1149, PROPS-1157, PROPS-1159.

## Erfolge

- Die Product-Cast-Automatisierung wurde vom Prototyp und den Power-Automation-Flows bis zu einer lauffähigen AWS-Lambda-Lösung entwickelt und abgeschlossen. Damit ist ein zuvor aufwendiger Dokumentationsprozess technisch deutlich besser skalierbar. Relevante Tickets: PROPS-1131, PROPS-1163.
- Das Script zur Extraktion von Reputation Ratings wurde produktiv an Beate übergeben und spart dort unmittelbar manuelle Arbeit. Das ist ein Ergebnis mit direktem Nutzen statt lediglich sauberer Dokumentation über einen möglichen Nutzen. Relevante Tickets: PROPS-1152.
- Für die SW-Capitalization entstanden zwei wiederverwendbare Werkzeuge: ein Generator für Business Cases und ein Skript zur Bewertung der Aktivierbarkeit. Die Business Cases wurden erstellt, geprüft und mit den PMs geteilt. Relevante Tickets: PROPS-1166, PROPS-1167.
- Der Jira Self-Service Assistant wurde von der Idee zu einer fachlichen und technischen MVP-Spezifikation weiterentwickelt; dadurch liegt eine belastbare Grundlage für die spätere Implementierung vor. Relevante Tickets: PROPS-1153, PROPS-1154, PROPS-1155, PROPS-1156.

## Wirkung

- Die Prio-Vorbereitung und Product Cast reduzieren wiederkehrende manuelle Kommunikations- und Dokumentationsarbeit und wurden von Beteiligten sichtbar positiv aufgenommen. Relevante Tickets: PROPS-1143, PROPS-1163.
- Das Ratings-Script liefert Beate direkt verwertbare Daten und senkt ihren manuellen Erfassungsaufwand. Relevante Tickets: PROPS-1152.
- Die Business-Case-Automatisierung schafft für die Software-Aktivierung eine breitere, überprüfbare Entscheidungsgrundlage über alle betroffenen Epics hinweg. Relevante Tickets: PROPS-1166, PROPS-1167.
- Jira-Enablement, Governance-Arbeit und die Vorbereitung des Self-Service-Assistenten verlagern Unterstützung schrittweise von einzelnen Ad-hoc-Anfragen in nachvollziehbare Prozesse. Relevante Tickets: PROPS-1135, PROPS-1153, PROPS-1170.

## Fokus-Impuls

- Die Aufwandserfassung jetzt auf eine klare Entscheidungsvorlage mit Datenschutz, Kosten, fachlichem Nutzen und einem verbindlichen nächsten Entscheidungstermin verdichten. Die Recherche ist weit genug; weitere parallele Optionen würden vor allem neue Vergleichstabellen erzeugen. Relevante Tickets: PROPS-1149, PROPS-1157.

## Monatsüberblick

| Woche | Schwerpunkt | Wichtigste Erfolge | Offene Punkte |
| --- | --- | --- | --- |
| 01.–03. Juli | Prototyping für Aufwandserfassung, Prio-Kommunikation und Workflow-Automatisierung | Time-Tracking-Prototyp, Prio-Mail-Weboberfläche und 48-Stunden-Alert abgeschlossen | Klärung zu Pflichtfeldern für PRL-Automatisierung und Worklog-Konzept |
| 06.–10. Juli | Reputation Ratings, Worklog-Datenschutz und Jira Self-Service | Rating-Spikes, Dashboard-Korrektur sowie fachliche und technische MVP-Spezifikation erstellt | Entscheidung zur Worklog-Lösung und Umsetzung des LLM-Zweigs |
| 13.–17. Juli | Product-Cast-Workshop, Enablement und SW-Capitalization | Ratings-Script produktiv übergeben, Jira-Einführung durchgeführt, CA-Daten rekonstruiert | AWS- und Forge-Build-Probleme sowie weitere F&E-Anforderungen |
| 20.–24. Juli | Tiefenfokus auf Product Cast und technische Entscheidungsfindung | Product-Cast-Automatisierung bis zum nahezu fertigen Stand gebracht | Entscheidung zur Aufwandserfassung weiterhin offen |
| 27.–31. Juli | SW-Capitalization automatisieren und Product Cast abschließen | Business-Case-Generator produktiv genutzt; Product-Cast-Lambda und Automatisierungs-Fokusthema abgeschlossen | Auswertung der Aktivierbarkeits-Ergebnisse mit Accounting; Jira Self-Service weiter priorisieren |
