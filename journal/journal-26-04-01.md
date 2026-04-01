# Journal 2026-04-01

## Auswertung (Agent)

- **Generell:** Der Tag mischt schnelle Lieferung (PROPS-1000 am selben Tag von Start bis Done) mit dem strukturierten Anlauf eines neuen Themas (PROPS-1002) und dem bewussten Pausieren der Automatisierungs-Epic nach dem letzten Script-Umbau (PROPS-912 auf On Hold). Neben den PROPS-Bewegungen fällt ein synchroner Block an Fix-Version-Änderungen im GUARANTEE-Projekt auf (Planungs-/Release-Hygiene).

- **Inhaltlicher Fokus:** Schwerpunkt Wishlist-/Confluence-Integration per Lambda und Abschluss der dafür vorgesehenen Jira-Automatisierungen; parallel Finanz-/Reporting-Arbeit (AWS-Kosten für Software Capitalization) und Abschluss der Skript-Automatisierung bis auf Monitoring.

- **Arbeitsmodus:** Fokussierte Umsetzung und Abnahme bei PROPS-1000 versus explorativer Sammel- und Koordinationsmodus bei PROPS-1002; PROPS-912 ist nach der Umstellung in einen Beobachtungs- bzw. Wartezustand gerutscht.

- **Zusammenarbeit:** Sichtbar wird aktive Ansprache von Ansprechpartnern für AWS-Accounts (Kommentar zu PROPS-1002); weitere Abstimmung erfolgt vor allem über die manuell beschriebene DevOps-Kommunikation.

- **Risiko/Offene Punkte:** Verlässlicher Betrieb der Trust-Audit-Lambda ist noch zu verifizieren; PROPS-1002 hängt an Rückmeldungen und Datenlieferung aus den angeschriebenen Kontakten.

- **Naechster sinnvoller Schritt:** Trust-Audit-Flow kurz beobachten/testen; bei PROPS-1002 eingehende Kosten- und Kontoinfos konsolidieren, sobald sie da sind.

## Manueller Inhalt

- Habe morgens die Prozessierung neuer messages im Trust-Audit Channel auf ein Lambda umgestellt (PROPS-912). Muss ich jetzt in den nächsten Tagen mal testen.
- Habe recherchiert, wie ich die Skills für PrOps am besten im Repo strukturiere, um sie mit dem /add-plugin Kommando von Cursor installieren zu können.
- Habe angeboten für die Software Aktivierung die Kosten für AWS-Accounts zusammenzutragen und damit angefangen (PROPS-1002). Dafür viele DevOps angeschrieben.
- Am Nachmittag das wishlist-Lambda aktualisiert damit auch die Confluence-Pages für neue Wishes angelegt werden (PROPS-1000). Außerdem Funktionen für update-page und delete-page eingebaut und die Jira-Automatisierungen auf dieses Lambda umgestellt.

## Generierter Inhalt (Jira)

### In Bearbeitung

- [PROPS-912](https://trustedshops.atlassian.net/browse/PROPS-912) - Take care that all pythons script that have to be executed regularly are automated
- [PROPS-1000](https://trustedshops.atlassian.net/browse/PROPS-1000) - Add creation of confluence-pages to the wishlist-lambda
- [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization

### Statuswechsel

- 10:59 - [PROPS-912](https://trustedshops.atlassian.net/browse/PROPS-912) - Take care that all pythons script that have to be executed regularly are automated - In Progress -> On Hold
- 14:34 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization - To be refined -> In Progress
- 15:16 - [PROPS-1000](https://trustedshops.atlassian.net/browse/PROPS-1000) - Add creation of confluence-pages to the wishlist-lambda - To Do -> In Progress
- 16:27 - [PROPS-1000](https://trustedshops.atlassian.net/browse/PROPS-1000) - Add creation of confluence-pages to the wishlist-lambda - In Progress -> Done

### Kommentare

- 10:59 - [PROPS-912](https://trustedshops.atlassian.net/browse/PROPS-912) - Take care that all pythons script that have to be executed regularly are automated - Klaus Heywinkel: "Als letztes Script das Trust-Audit umgestellt. Muss ich in den nächsten Tagen im Auge behalten, ob es auch richtig läuft."
- 14:56 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization - Klaus Heywinkel: "I identified these AWS Accounts a texted the contact person:"
- 16:27 - [PROPS-1000](https://trustedshops.atlassian.net/browse/PROPS-1000) - Add creation of confluence-pages to the wishlist-lambda - Klaus Heywinkel: "Implemented."

### Ticket-Änderungen

- 10:08 - [GUARANTEE-1820](https://trustedshops.atlassian.net/browse/GUARANTEE-1820) - Bring action items out of retros an the Jira board in an own swimlane - Geändert: Fix Version
- 10:08 - [GUARANTEE-1821](https://trustedshops.atlassian.net/browse/GUARANTEE-1821) - Postpone Refinement meeting by 15 minutes - Geändert: Fix Version
- 10:08 - [GUARANTEE-1822](https://trustedshops.atlassian.net/browse/GUARANTEE-1822) - Extend our ticket template with a chapter for DoR - Geändert: Fix Version
- 10:08 - [GUARANTEE-1830](https://trustedshops.atlassian.net/browse/GUARANTEE-1830) - Move Daily on Thursdays to 9:45 because of conflict with P&E Weekly - Geändert: Fix Version
- 10:08 - [GUARANTEE-1869](https://trustedshops.atlassian.net/browse/GUARANTEE-1869) - Add a checklist in each Jira-ticket for our DoD - Geändert: Fix Version
- 10:08 - [GUARANTEE-1868](https://trustedshops.atlassian.net/browse/GUARANTEE-1868) - Research for options in Jira Cloud to pre-fill tickets on creation with a template structure - Geändert: Fix Version
- 10:08 - [GUARANTEE-1891](https://trustedshops.atlassian.net/browse/GUARANTEE-1891) - Create a vote to decide if we could start retros at 3pm - Geändert: Fix Version
- 10:08 - [GUARANTEE-1892](https://trustedshops.atlassian.net/browse/GUARANTEE-1892) - Create an automation that sends a reminder in Teams to finish tests at the end of each sprint - Geändert: Fix Version
- 10:08 - [GUARANTEE-1981](https://trustedshops.atlassian.net/browse/GUARANTEE-1981) - Clarify if we could use the Jira/Git integration - Geändert: Fix Version
- 10:08 - [GUARANTEE-2208](https://trustedshops.atlassian.net/browse/GUARANTEE-2208) - enable the new reminder scheduler - Geändert: Fix Version
- 10:08 - [GUARANTEE-2187](https://trustedshops.atlassian.net/browse/GUARANTEE-2187) - Check if the updated product strategy contains something about a substitute for Excellence - Geändert: Fix Version
- 10:08 - [GUARANTEE-2209](https://trustedshops.atlassian.net/browse/GUARANTEE-2209) - PL: Check if the conversation rate for the Trustcard has increased since the new text has been implemented in October - Geändert: Fix Version
- 10:08 - [GUARANTEE-2219](https://trustedshops.atlassian.net/browse/GUARANTEE-2219) - Request test data at the Insights Team - Geändert: Fix Version
- 10:09 - [GUARANTEE-2425](https://trustedshops.atlassian.net/browse/GUARANTEE-2425) - Clarification of Buyer Protection Messaging for B2B and B2C Buyers in membershops - Geändert: Fix Version
- 10:58 - [PROPS-912](https://trustedshops.atlassian.net/browse/PROPS-912) - Take care that all pythons script that have to be executed regularly are automated - Geändert: description
- 10:59 - [PROPS-912](https://trustedshops.atlassian.net/browse/PROPS-912) - Take care that all pythons script that have to be executed regularly are automated - Geändert: Remind date
- 14:33 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization - Geändert: description
- 14:36 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization - Geändert: description
- 15:14 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization - Geändert: description
- 16:27 - [PROPS-1000](https://trustedshops.atlassian.net/browse/PROPS-1000) - Add creation of confluence-pages to the wishlist-lambda - Geändert: resolution

### Neu angelegte Tickets

- 14:33 - [PROPS-1002](https://trustedshops.atlassian.net/browse/PROPS-1002) - Compile AWS costs for all in-scope accounts for 2025 software capitalization
