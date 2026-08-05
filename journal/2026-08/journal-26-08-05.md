# Journal 2026-08-05

## Termine

- 14:00 - 14:25: Natalie x PrOps
- 15:30 - 15:55: PrOps x Raj
- 16:00 - 16:15: PrOps Daily
- 18:45 - 19:45: Abf. Oz

## Top 3 scored Jira Tasks

- PROPS-1158 - Proactive, filtered bug communication process from Product to CSM/AM/Sales (Ongoing minor adaptions to processes and templates)
- PROPS-1159 - Implement LLM branch: local chat CLI and system-instructions library (Build a Jira self-service assistant for high-quality admin requests)
- PROPS-721 - Jira maintenance | Archive old and unused projects (Jira support)

## Auswertung (Agent)

- **Generell**: Der Tag wirkt wie ein Umschalten von Nachlauf auf Steuerung. Vormittags wurden mehrere offene Fäden geschlossen bzw. geparkt; Nachmittags lag der Fokus auf Bug Communication und dem Jira-Service-Bot, trotz Dashboard-Ausfall und kurzer Abstimmungsfenster.
- **Inhaltlicher Fokus:** Product/Bug-Communication (Dashboard und Abstimmung) plus paralleler Feinschliff am Jira-Service-Bot, nachdem P2M und verwandte Themen am Vormittag weitgehend abgeräumt waren.
- **Arbeitsmodus:** Konzentrierter Abschluss-Schub am Vormittag (ca. 08:20–10:30), danach Feedback-Schleifen und Umsetzung am Nachmittag, unterbrochen durch Termine und den Grafana-Datenfix – die Restzeit ging bewusst in den Bot statt in Leerlauf.

## Stimmungslage

- Du beschreibst Freiraum vor den eigenen Aufgaben statt Hinterherlaufen – das passt zum Vormittagsbild mit mehreren Abschlüssen und On-Hold-Parken statt offener Schleifen.
- Trotz Blockade an den Dashboards (Taha, Daten-Reload) blieb die Einordnung „zufriedenstellend vorangekommen“; Umsteuerung auf den Bot statt Frustfokus.
- Der spontane Call mit Lars wirkt eher als klarer, hilfreicher Impuls denn als Belastung.

## Positives Feedback

- Lars fand den Input zur GDPR-konformen Verarbeitung anonymisierter Jira-Ticket-Daten in Claude brauchbar – spontaner Call, klarer Nutzen für ihn.

## Manueller Inhalt

- Am Vormittag aus Prdouct Communication fokussiert (PROPS-1073)
- Nachmittags den Fokus auf Bug Communication Process gelegt und weiter an den Grafana Dashboards gearbeitet. Da wurde ich zwischendurch ausgebremst, weil Taha einen Bug bei der Belieferung der Jira Daten nach Postgres fixt und die Dashboards gerade nicht zur Verfügung stehen.
- Habe die retsliche Zeit genutzt, um an dem Jira-Service Bot weiterzumachen
- Zwischendurch spontaner Call mit Lars. Ich konnte ihm helfen bei der Frage, wie er GDPR-konform anonymisierte Jira-Ticket-Daten in Claude verarbeiten kann. Fand er gut.
- Bin insgesamt ganz zufriedenstellend vorangekommen.

## Generierter Inhalt (Jira)

### In Bearbeitung

- [PROPS-1151](https://trustedshops.atlassian.net/browse/PROPS-1151) - Plan & conduct a second Jira-training for Field Experts (for those not being able to attend the first one)
- [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales
- [PROPS-1161](https://trustedshops.atlassian.net/browse/PROPS-1161) - Introduce active ACT Coordinators
- [PROPS-1177](https://trustedshops.atlassian.net/browse/PROPS-1177) - Adapt the P2M Task for Product Marketing
- [PROPS-1178](https://trustedshops.atlassian.net/browse/PROPS-1178) - Add Jira epics as source for product cast
- [PROPS-1179](https://trustedshops.atlassian.net/browse/PROPS-1179) - Present recent changes of P2M in the BRM

### Statuswechsel

- `08:24` [PROPS-1151](https://trustedshops.atlassian.net/browse/PROPS-1151) - Plan & conduct a second Jira-training for Field Experts (for those not being able to attend the first one) - In Progress → Done
- `09:10` [PROPS-1161](https://trustedshops.atlassian.net/browse/PROPS-1161) - Introduce active ACT Coordinators - In Progress → Done
- `09:33` [PROPS-1179](https://trustedshops.atlassian.net/browse/PROPS-1179) - Present recent changes of P2M in the BRM - In Progress → On Hold
- `09:33` [PROPS-1177](https://trustedshops.atlassian.net/browse/PROPS-1177) - Adapt the P2M Task for Product Marketing - To Do → In Progress → On Hold → Done
- `10:33` [PROPS-1178](https://trustedshops.atlassian.net/browse/PROPS-1178) - Add Jira epics as source for product cast - To Do → In Progress → Done

### Kommentare

- `08:25` [PROPS-1161](https://trustedshops.atlassian.net/browse/PROPS-1161) - Introduce active ACT Coordinators - Klaus Heywinkel: "Laura was on vacation yesterday (without declining the appointment …). I’ll remove the P2M Task for her and delete her as Core Contributor in the confluence page and do not longer "
- `09:27` [PROPS-1179](https://trustedshops.atlassian.net/browse/PROPS-1179) - Present recent changes of P2M in the BRM - Klaus Heywinkel: "Did the last changes and have sent the slides to Damien. Next : Present on the BRM on 12.08.26"
- `10:07` [PROPS-1177](https://trustedshops.atlassian.net/browse/PROPS-1177) - Adapt the P2M Task for Product Marketing - Klaus Heywinkel: "Created the task in the automation and texted Mansuav to get his ok for the text"
- `13:13` [PROPS-1177](https://trustedshops.atlassian.net/browse/PROPS-1177) - Adapt the P2M Task for Product Marketing - Klaus Heywinkel: "Received feedback from Mansuav and adapted accordingly → Task done"
- `13:59` [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales - Klaus Heywinkel: "Hi Ich habe mal ein Dashboard angelegt, um zu diesem Thema ein paar Zahlen zu visualisieren. Hier ein Screenshot: Was würdest du davon halten, wenn wir uns für den Anfang für das B"
- `14:17` [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales - Jenny Haas: "Hi , der Fokus würde auf frisch erstellten Tickets liegen, ja. Die Prios passen für mich erst mal (oder werden Showstopper generell als Incident behandelt und können daher außen vo"
- `14:39` [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales - Jenny Haas: "and if I remember correctly, you wanted to work on an AI solution within the team goals for the same topic. Is that correct? It might make sense to join forces with Klaus and work "
- `14:50` [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales - Klaus Heywinkel: "Taha fixed a bug and needs to refill the data completely. The dashboards will be unusable for about 24 hours."

### Ticket-Änderungen

- `08:24` [PROPS-1151](https://trustedshops.atlassian.net/browse/PROPS-1151) - Plan & conduct a second Jira-training for Field Experts (for those not being able to attend the first one) - Geändert: resolution
- `09:10` [PROPS-1161](https://trustedshops.atlassian.net/browse/PROPS-1161) - Introduce active ACT Coordinators - Geändert: description, resolution
- `09:33` [PROPS-1179](https://trustedshops.atlassian.net/browse/PROPS-1179) - Present recent changes of P2M in the BRM - Geändert: Remind date, Link
- `10:07` [PROPS-1177](https://trustedshops.atlassian.net/browse/PROPS-1177) - Adapt the P2M Task for Product Marketing - Geändert: Remind date, resolution
- `13:12` [PROPS-1178](https://trustedshops.atlassian.net/browse/PROPS-1178) - Add Jira epics as source for product cast - Geändert: resolution
- `13:59` [PROPS-1158](https://trustedshops.atlassian.net/browse/PROPS-1158) - Proactive, filtered bug communication process from Product to CSM/AM/Sales - Geändert: Attachment, description, RemoteWorkItemLink

### Neu angelegte Tickets

- Keine Einträge.
