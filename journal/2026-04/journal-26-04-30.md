# Journal 2026-04-30

## Auswertung (Agent)

- **Generell:** Ein ungewöhnlich produktiver Tag mit hohem Closure-Anteil – der manuelle Vormittag (Ticket-Übertrag, Webhook-Fix, All-Hands) und der Prio-Meeting-getriebene Nachmittag spiegeln sich sauber in Jira wider (9 abgeschlossene Issues, 6 neu angelegt). Manueller Teil und Jira-Bewegung laufen heute parallel, kein Auseinanderdriften erkennbar.
- **Inhaltlicher Fokus:** Vor- und Nachbereitung des Prio-Meetings der Business Domain (Epic-Pflege, One-Pager, Backlog-Spalte) plus parallele Beendigung mehrerer älterer Threads (Webhook 401, Wishlist-Taxonomie, Stakeholder-Summary).
- **Arbeitsmodus:** Abarbeitung mit klarer Closure-Logik – Tickets werden über mehrere Status (`To Do → In Progress → Done`) am selben Tag durchgezogen, gleichzeitig wird neuer Backlog aus dem Prio-Meeting direkt operationalisiert.
- **Zusammenarbeit:** Viele Touchpoints in unterschiedlichen Richtungen (PMs, Vincent, Ramona, Sara, Sabrina, Stella) – die Kommentare dokumentieren überwiegend positives Feedback und geklärte Verantwortlichkeiten.
- **Risiko/Offene Punkte:** Der Webhook-Fix (PROPS-1050/1032) ist erst nach der nächsten echten Nachricht real verifiziert – bis dahin offener Verifizierungsschritt; zusätzlich steht das Umsetzen des Prio-Meeting-Feedbacks noch aus.
- **Nächster sinnvoller Schritt:** Prio-Meeting-Feedback in den frisch angelegten Tickets (PROPS-1051, 1053, 1055) konkretisieren und Webhook-Verifizierung im Auge behalten.

## Manueller Inhalt

- Vormittag:
  - Zunächst habe ich mich darum gekümmert, Input von gestern in Jira-Tickets zu überführen
  - Dann einen Bug im TBI-AI-Webhook gesucht und auch gefunden: Das Signing Secret, welches im Power Automation Flow genutzt wurde, war falsch.
  - Eine Stunden All-Hands am Vormittag

- Nachmittag:
  - Habe mit der Orga der von den ACTs gewünschten Traingssession begonnen und PMs, Sabrina sowie Stella angeschrieben. Außerdem schriftlicher Austausch mit Auftraggeberin Sara.
  - Dann war das Prio-Meeting der Business Domain mit Feedback, welches ich nun umsetzen muss.
  - Aus dem Prio-Meeting sind auch noch Tasks entanden, die ich angelegt und zum Teil auch schon angefangen habe.

## Generierter Inhalt (Jira)

### In Bearbeitung

- [PROPS-1010](https://trustedshops.atlassian.net/browse/PROPS-1010) - Implement Standardized Stakeholder Summary for Epics (Manual)
- [PROPS-1032](https://trustedshops.atlassian.net/browse/PROPS-1032) - Create AWS Automation: Teams Messages to Confluence Pages for Trustbadge AI+
- [PROPS-1035](https://trustedshops.atlassian.net/browse/PROPS-1035) - Track blockers during Estelle's vacation
- [PROPS-1036](https://trustedshops.atlassian.net/browse/PROPS-1036) - Share some insights of the wishlist dashboard
- [PROPS-1043](https://trustedshops.atlassian.net/browse/PROPS-1043) - Take care that all epics in the business domain are maintained properly for meeting on 30.04.
- [PROPS-1047](https://trustedshops.atlassian.net/browse/PROPS-1047) - Create a Miro frame or PPTX to explain the goal of the prio-meeting
- [PROPS-1048](https://trustedshops.atlassian.net/browse/PROPS-1048) - AWS Amortized Cost Report for 2025 SW Capitalization - Split by DEV/QA and Prod
- [PROPS-1049](https://trustedshops.atlassian.net/browse/PROPS-1049) - Create One-Pager for all new initiatives in Next/Backlog for prio-meeting of Business Domain
- [PROPS-1050](https://trustedshops.atlassian.net/browse/PROPS-1050) - Investigate TBAI+ webhook 401 Unauthorized rejections
- [PROPS-1052](https://trustedshops.atlassian.net/browse/PROPS-1052) - Wishlist: Create the value-driver for all new wishes
- [PROPS-1056](https://trustedshops.atlassian.net/browse/PROPS-1056) - Gather all information and align with all involved people
- [PROPS-1057](https://trustedshops.atlassian.net/browse/PROPS-1057) - Add Backlog column on the board and inform all PMs about it

### Statuswechsel

- [PROPS-1051](https://trustedshops.atlassian.net/browse/PROPS-1051) - Research | Should we make P2M mandatory? - To be refined → To Do
- [PROPS-1053](https://trustedshops.atlassian.net/browse/PROPS-1053) - Create agenda draft and miro-board for monthly PM Workspace - To be refined → To Do
- [PROPS-1052](https://trustedshops.atlassian.net/browse/PROPS-1052) - Wishlist: Create the value-driver for all new wishes - To be refined → To Do → In Progress → Done
- [PROPS-1050](https://trustedshops.atlassian.net/browse/PROPS-1050) - Investigate TBAI+ webhook 401 Unauthorized rejections - To Do → In Progress → Done
- [PROPS-1032](https://trustedshops.atlassian.net/browse/PROPS-1032) - Create AWS Automation: Teams Messages to Confluence Pages for Trustbadge AI+ - In Progress → On Hold
- [PROPS-1036](https://trustedshops.atlassian.net/browse/PROPS-1036) - Share some insights of the wishlist dashboard - In Progress → To Do → Backlog
- [PROPS-1043](https://trustedshops.atlassian.net/browse/PROPS-1043) - Take care that all epics in the business domain are maintained properly for meeting on 30.04. - In Progress → Done
- [PROPS-1010](https://trustedshops.atlassian.net/browse/PROPS-1010) - Implement Standardized Stakeholder Summary for Epics (Manual) - In Progress → Done
- [PROPS-1055](https://trustedshops.atlassian.net/browse/PROPS-1055) - Automate Stakeholder Summary Population for Epics - To be refined → To Do
- [PROPS-1047](https://trustedshops.atlassian.net/browse/PROPS-1047) - Create a Miro frame or PPTX to explain the goal of the prio-meeting - In Progress → Done
- [PROPS-1048](https://trustedshops.atlassian.net/browse/PROPS-1048) - AWS Amortized Cost Report for 2025 SW Capitalization - Split by DEV/QA and Prod - To Do → In Progress → Done
- [PROPS-1046](https://trustedshops.atlassian.net/browse/PROPS-1046) - Clarify ownership for TL training sessions on newly launched products - On Hold → Done
- [PROPS-1049](https://trustedshops.atlassian.net/browse/PROPS-1049) - Create One-Pager for all new initiatives in Next/Backlog for prio-meeting of Business Domain - Backlog → In Progress → Done
- [PROPS-1056](https://trustedshops.atlassian.net/browse/PROPS-1056) - Gather all information and align with all involved people - To be refined → In Progress
- [PROPS-1028](https://trustedshops.atlassian.net/browse/PROPS-1028) - Jira Automation: Parent task follows sub-task status - To Do → Backlog
- [PROPS-949](https://trustedshops.atlassian.net/browse/PROPS-949) - Establish and align a standard taxonomy for wishlist classification - On Hold → Done
- [PROPS-1045](https://trustedshops.atlassian.net/browse/PROPS-1045) - Create new Views in Jira for "What has changed" - Backlog → To Do
- [PROPS-1057](https://trustedshops.atlassian.net/browse/PROPS-1057) - Add Backlog column on the board and inform all PMs about it - To be refined → In Progress

### Kommentare

- [PROPS-1050](https://trustedshops.atlassian.net/browse/PROPS-1050) - Investigate TBAI+ webhook 401 Unauthorized rejections - Klaus Heywinkel: "The Power Automation Flow used the wrong Signing Secret in the call of the Lambda. Fixed it - but can only be verified with the next real-life message in the channel."
- [PROPS-1032](https://trustedshops.atlassian.net/browse/PROPS-1032) - Create AWS Automation: Teams Messages to Confluence Pages for Trustbadge AI+ - Klaus Heywinkel: "Fixed the error (hopefully). Next : Wait for the next message in the channel."
- [PROPS-1043](https://trustedshops.atlassian.net/browse/PROPS-1043) - Take care that all epics in the business domain are maintained properly for meeting on 30.04. - Klaus Heywinkel: "Received a thumbs up from all PMs."
- [PROPS-1048](https://trustedshops.atlassian.net/browse/PROPS-1048) - AWS Amortized Cost Report for 2025 SW Capitalization - Split by DEV/QA and Prod - Klaus Heywinkel: "Splitted costs in Betriebskosten and Amortized Costs and updated so the only amortized costs are included. Informed Vincent about it."
- [PROPS-1046](https://trustedshops.atlassian.net/browse/PROPS-1046) - Clarify ownership for TL training sessions on newly launched products - Klaus Heywinkel: "Has been clarified - I take over the coordination"
- [PROPS-1049](https://trustedshops.atlassian.net/browse/PROPS-1049) - Create One-Pager for all new initiatives in Next/Backlog for prio-meeting of Business Domain - Klaus Heywinkel: "As a first pilot I have sent the slides for only 4 initiatives yesterday to all stakeholder. One feedback from Ramona was positive."
- [PROPS-1056](https://trustedshops.atlassian.net/browse/PROPS-1056) - Gather all information and align with all involved people - Klaus Heywinkel:
- [PROPS-949](https://trustedshops.atlassian.net/browse/PROPS-949) - Establish and align a standard taxonomy for wishlist classification - Klaus Heywinkel: "Had a call with CSM Teamlead Tobi. He gave positive feedback on the taxonomy. I call this task done."
- [PROPS-1057](https://trustedshops.atlassian.net/browse/PROPS-1057) - Add Backlog column on the board and inform all PMs about it - Klaus Heywinkel: "Column is added and all PMs of the Business Domain are informed. I’ll keep this task open for the moment to maybe follow up."

### Ticket-Änderungen

- [PROPS-1051](https://trustedshops.atlassian.net/browse/PROPS-1051) - Research | Should we make P2M mandatory? - Geändert: IssueParentAssociation, description
- [PROPS-1052](https://trustedshops.atlassian.net/browse/PROPS-1052) - Wishlist: Create the value-driver for all new wishes - Geändert: IssueParentAssociation, resolution
- [PROPS-1053](https://trustedshops.atlassian.net/browse/PROPS-1053) - Create agenda draft and miro-board for monthly PM Workspace - Geändert: IssueParentAssociation, description, summary
- [PROPS-1050](https://trustedshops.atlassian.net/browse/PROPS-1050) - Investigate TBAI+ webhook 401 Unauthorized rejections - Geändert: Link, Rank, resolution
- [PROPS-1032](https://trustedshops.atlassian.net/browse/PROPS-1032) - Create AWS Automation: Teams Messages to Confluence Pages for Trustbadge AI+ - Geändert: Link, Remind date
- [PROPS-1043](https://trustedshops.atlassian.net/browse/PROPS-1043) - Take care that all epics in the business domain are maintained properly for meeting on 30.04. - Geändert: resolution
- [PROPS-1010](https://trustedshops.atlassian.net/browse/PROPS-1010) - Implement Standardized Stakeholder Summary for Epics (Manual) - Geändert: description, summary, resolution, Link
- [PROPS-1055](https://trustedshops.atlassian.net/browse/PROPS-1055) - Automate Stakeholder Summary Population for Epics - Geändert: description, IssueParentAssociation, assignee, Link
- [PROPS-1047](https://trustedshops.atlassian.net/browse/PROPS-1047) - Create a Miro frame or PPTX to explain the goal of the prio-meeting - Geändert: description, resolution
- [PROPS-1048](https://trustedshops.atlassian.net/browse/PROPS-1048) - AWS Amortized Cost Report for 2025 SW Capitalization - Split by DEV/QA and Prod - Geändert: resolution
- [PROPS-1046](https://trustedshops.atlassian.net/browse/PROPS-1046) - Clarify ownership for TL training sessions on newly launched products - Geändert: resolution
- [PROPS-1049](https://trustedshops.atlassian.net/browse/PROPS-1049) - Create One-Pager for all new initiatives in Next/Backlog for prio-meeting of Business Domain - Geändert: description, summary, resolution
- [PROPS-1056](https://trustedshops.atlassian.net/browse/PROPS-1056) - Gather all information and align with all involved people - Geändert: IssueParentAssociation, description, assignee
- [PROPS-949](https://trustedshops.atlassian.net/browse/PROPS-949) - Establish and align a standard taxonomy for wishlist classification - Geändert: resolution
- [PROPS-1057](https://trustedshops.atlassian.net/browse/PROPS-1057) - Add Backlog column on the board and inform all PMs about it - Geändert: IssueParentAssociation, description, assignee

### Neu angelegte Tickets

- [PROPS-1051](https://trustedshops.atlassian.net/browse/PROPS-1051) - Research | Should we make P2M mandatory?
- [PROPS-1052](https://trustedshops.atlassian.net/browse/PROPS-1052) - Wishlist: Create the value-driver for all new wishes
- [PROPS-1053](https://trustedshops.atlassian.net/browse/PROPS-1053) - Create agenda draft and miro-board for monthly PM Workspace
- [PROPS-1055](https://trustedshops.atlassian.net/browse/PROPS-1055) - Automate Stakeholder Summary Population for Epics
- [PROPS-1056](https://trustedshops.atlassian.net/browse/PROPS-1056) - Gather all information and align with all involved people
- [PROPS-1057](https://trustedshops.atlassian.net/browse/PROPS-1057) - Add Backlog column on the board and inform all PMs about it
