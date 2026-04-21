# Plan zur Verbesserung der Domain Prio Meetings

**Status:** Arbeitsfassung
**Erstellt:** 2026-04-21
**Ziel:** Aus dem vorliegenden Feedback und den bestehenden Proposal-Seiten einen nachvollziehbaren Verbesserungsplan mit klaren `next steps` ableiten.

## Ausgangslage

Die aktuellen Domain Prio Meetings erzeugen offenbar Nutzen, aber ihr eigentlicher Zweck und ihre Verbindlichkeit sind nicht sauber geklaert. Im Feedback tauchen dieselben Muster mehrfach auf: unklarer Meeting-Charakter, fehlende oder falsche Stakeholder, zu wenig explizite Value- und KPI-Diskussion, schwache Dokumentation der Ergebnisse und Medienbruch zwischen `Jira` und `Miro`.

Zur Adressierung dieser Punkte wurden einige Verbesserungsvorschlaege vorbereitet. Besonders relevant ist dabei die spaetere Standards-Seite, die den `one-pager` nicht nur als Hilfsmittel, sondern als zentrales Betriebsartefakt positioniert: fuer Vorbereitung, Vergleichbarkeit, Decision Ask, Wiederverwendung in Folgeartefakten und als `single source of truth`.

## Executive Summary

Die Rueckmeldungen zeigen kein isoliertes Tool-Problem, sondern ein Systemproblem. Das Meeting bewegt sich heute zwischen Priorisierung, Transparenz-Sync und Status-Update. Dadurch entstehen widerspruechliche Erwartungen und Entscheidungen verlieren an Verbindlichkeit.

Das Proposal adressiert bereits viele operative Probleme: bessere Vorbereitung, klarere Agenda, Decision Log, staerkere Einbindung von Abhaengigkeiten und weniger Fokus auf Miro. Die wichtigste Ergaenzung aus der Standards-Seite ist, dass der `one-pager` als zentrales Eingangsartefakt verstanden werden soll. Das ist logisch, weil damit mehrere Probleme gleichzeitig adressiert werden: unvorbereitete Stakeholder, inkonsistente Inputs, schwache Vergleichbarkeit und aufwendige Nachpflege in Folgeartefakten.

Trotzdem bleibt der `one-pager` nur ein starker Hebel, kein Wundermittel. Vor einer breiteren Einfuehrung muessen mindestens vier Designfragen geklaert werden: Welchen verbindlichen Zweck hat das Meeting? Wann sind Entscheidungen bindend - und wer hat ein Veto-Recht? Nach welchen Kriterien wird priorisiert? Und welches Artefakt ist kuenftig der offizielle Referenzstand?

## Themencluster und Bewertung

### 1. Zweck des Meetings und erwarteter Output

- **Problem / Evidenz aus Feedback:** Mehrere Rueckmeldungen beschreiben das Format als Mischung aus Priorisierung, Transparenz-Sync und Status-Update. Zudem wurde explizit hinterfragt, welchen Wert Stakeholder aus dem Meeting mitnehmen.
- **Aktueller Proposal-Ansatz:** Eine kurze Purpose-Folie zu Beginn der naechsten Runden und eine staerkere Fokussierung auf priorisierungsrelevante Themen statt auf reine Readouts.
- **Beitrag des One-Pagers:** `unterstuetzend`
- **Bewertung:** `teilweise`
- **Implikation fuer das Zielmodell:** Das Format braucht eine klare Betriebsdefinition. Solange nicht feststeht, ob hier priorisiert, informiert oder beides nach festen Regeln gemacht wird, bleiben Agenda und Erwartungshaltung unscharf.

### 2. Entscheidungsverbindlichkeit und Governance

- **Problem / Evidenz aus Feedback:** Entscheidungen werden offenbar nicht durchgaengig als verbindlich verstanden. Ein zentrales Risiko ist, dass Beschluesse spaeter durch fehlende oder anders priorisierende Stakeholder wieder relativiert werden.
- **Aktueller Proposal-Ansatz:** Bessere Dokumentation ueber Decision Log und AI-basierte Zusammenfassung.
- **Beitrag des One-Pagers:** `unterstuetzend`
- **Bewertung:** `offen`
- **Implikation fuer das Zielmodell:** Dokumentation verbessert Nachvollziehbarkeit, ersetzt aber keine Governance. Es fehlt weiterhin eine explizite Regel, wann eine Entscheidung gueltig ist, wer sie mittraegt und was passiert, wenn notwendige Entscheider fehlen.

### 3. Teilnehmerkreis, Rollen und Abhaengigkeiten

- **Problem / Evidenz aus Feedback:** In mehreren Beispielen fehlten entscheidende Stakeholder oder Abhaengigkeiten, insbesondere Business Stakeholder und `PlatOps`. Zudem war teils unklar, wer moderiert und welche Rolle einzelne Teilnehmende haben.
- **Aktueller Proposal-Ansatz:** Pro Initiative sollen Abhaengigkeiten vorab benannt und je benoetigtem Team Stakeholder eingeladen werden. `PlatOps` soll regulaerer Teil der Runde werden. In der Standards-Seite wird das durch RACI-light und Rollenlogik weiter gestuetzt.
- **Beitrag des One-Pagers:** `unterstuetzend`
- **Bewertung:** `teilweise`
- **Implikation fuer das Zielmodell:** Die Richtung stimmt, aber es fehlt noch eine verbindliche Mindestbesetzung und eine klare Rollenlogik. Ein gutes Artefakt hilft wenig, wenn die falschen Personen am Tisch sitzen.

### 4. Priorisierungslogik, Value-Basis und Entscheidungsgrundlage

- **Problem / Evidenz aus Feedback:** Stakeholder vermissen klare Kriterien, KPI-Bezug und sichtbare Trade-offs. Ein konkretes Beispiel zeigt, dass Business Value und Teamprioritaeten auseinanderlaufen koennen. Auch Discovery-Arbeit ist bisher schwer sichtbar zu machen.
- **Aktueller Proposal-Ansatz:** Vorbereitungsmaterial soll Problem, Loesung, Outcome und KPI-Benefit enthalten. Die Standards-Seite ergaenzt das um ein kalibrierbares Priorisierungsmodell, etwa ueber feste Bewertungsdimensionen.
- **Beitrag des One-Pagers:** `Kernhebel`
- **Bewertung:** `teilweise`
- **Implikation fuer das Zielmodell:** Der `one-pager` verbessert die Qualitaet der Inputs deutlich, aber es braucht zusaetzlich ein abgestimmtes Bewertungsmodell. Erst dann sind Themen wirklich vergleichbar und priorisierbar.

### 5. Vorbereitung, Pre-Read und Meeting-Ablauf

- **Problem / Evidenz aus Feedback:** Stakeholder wirken unvorbereitet, die Frequenz erscheint teils zu hoch und das Meeting verliert Fokus, wenn keine echten Priorisierungskonflikte vorliegen.
- **Aktueller Proposal-Ansatz:** Pre-read vorab versenden, Fokus auf Themen in der Priorisierungsspalte, laufende Initiativen weitgehend aus dem Termin nehmen, Meeting-Rhythmus auf vier Wochen umstellen und kurzfristige Entscheidungen asynchron behandeln. Die Standards-Seite ergaenzt Submission Gate, Pre-read-SLA und Cut-off-Regeln.
- **Beitrag des One-Pagers:** `Kernhebel`
- **Bewertung:** `ausreichend`
- **Implikation fuer das Zielmodell:** Dieser Bereich ist am weitesten ausgearbeitet. Die wesentliche Aufgabe ist hier weniger Konzeptentwicklung als saubere Einfuehrung und Disziplin in der Anwendung.

### 6. Dokumentation, Transparenz und Rueckfluss

- **Problem / Evidenz aus Feedback:** `Miro` wird als Snapshot wahrgenommen, nicht als verlaesslicher Entscheidungsnachweis. Zusaetzlich fehlt ein strukturierter Rueckfluss der gewonnenen Klarheit in Domain und weitere Kommunikationsformate.
- **Aktueller Proposal-Ansatz:** Decision Log, AI-generierte Zusammenfassungen und zentrale Ablage in `Confluence`. Die Standards-Seite ergaenzt Outcome Tags, Follow-up-Logik und Wiederverwendung in weiteren Artefakten.
- **Beitrag des One-Pagers:** `unterstuetzend`
- **Bewertung:** `teilweise`
- **Implikation fuer das Zielmodell:** Es braucht einen offiziellen Referenzstand nach dem Meeting und eine klare Rueckflusslogik. Sonst wird zwar dokumentiert, aber nicht wirksam kommuniziert.

### 7. Tooling und Artefaktlandschaft

- **Problem / Evidenz aus Feedback:** Der Medienbruch zwischen `Jira` und `Miro` wird als unnoetig manuell und umstaendlich beschrieben. Gleichzeitig sollen aus denselben Informationen weitere Artefakte entstehen.
- **Aktueller Proposal-Ansatz:** Im Meeting eher `Jira` fuer die Uebersicht nutzen und Details ueber vorbereitete Unterlagen vermitteln. Die Standards-Seite positioniert den `one-pager` als kanonische Quelle fuer BRM, SACT und Product Updates.
- **Beitrag des One-Pagers:** `Kernhebel`
- **Bewertung:** `teilweise`
- **Implikation fuer das Zielmodell:** Das kuenftige System braucht ein klares Artefaktmodell: Wo wird welche Information gepflegt, welches System ist fuehrend und was wird nur daraus abgeleitet.

## Rolle des One-Pagers im Zielmodell

Der `one-pager` ist in den vorliegenden Standards sinnvollerweise das zentrale Eingangsartefakt fuer priorisierungsrelevante Themen. Er loest nicht nur ein Vorbereitungsproblem, sondern strukturiert den gesamten Informationsfluss:

- Er macht Themen vergleichbar, weil Problem, Impact, Metriken, Optionen, Risiken, Abhaengigkeiten und `decision ask` in derselben Logik vorliegen.
- Er reduziert Vorbereitungsaufwand fuer Stakeholder, weil nicht erst im Meeting zusammengesucht werden muss, worum es eigentlich geht.
- Er verbessert die Dokumentationsfaehigkeit, weil Folgeartefakte nicht neu erfunden, sondern aus derselben Quelle gespeist werden koennen.
- Er erzwingt eine Mindestqualitaet der Inputs, wenn er an Submission Gate, Pre-read-SLA, Review und Versionierung gekoppelt wird.

Wichtig ist dabei die Unterscheidung zwischen `Content Standard` und `Operating Model`. Ein gutes Template allein reicht nicht. Erst durch Regeln fuer Pflichtfelder, Freigabe, Fristen, Archivierung und Verlinkung wird der `one-pager` zum tragfaehigen Element des Meeting-Systems.

## Offene Designentscheidungen

Vor einer breiteren Einfuehrung sollten diese Punkte explizit entschieden werden:

1. **Meeting-Typ und Governance**
   Soll das Format eine echte Priorisierungsrunde, ein Transparenzformat oder ein Hybrid mit klaren Regeln sein?

2. **Entscheidungsverbindlichkeit**
   Wann gilt eine Entscheidung als bindend? Welche Rollen muessen vertreten sein? Gibt es Veto- oder Eskalationslogiken?

3. **Bewertungsmodell**
   Nach welchen festen Kriterien werden Themen gegeneinander abgewogen? Welche Metriken sind verpflichtend, welche optional?

4. **Teilnehmer- und Rollenlogik**
   Wer muss bei welchen Abhaengigkeiten zwingend dabei sein? Wer moderiert, wer entscheidet, wer wird nur informiert?

5. **Fuehrendes Artefakt**
   Was ist kuenftig der offizielle Referenzstand zwischen `Jira`, `one-pager`, Decision Log und Folgeformaten?

6. **Rueckfluss in die Organisation**
   Wie werden Ergebnisse systematisch in Domains, Leadership und Folgeformate zurueckgespielt?

## Priorisierte Next Steps

### Designentscheidungen vor Umsetzung

1. **Meeting-Zweck verbindlich festlegen**
   Eine kurze, explizite Definition beschliessen, ob das Format priorisiert, informiert oder beides nach klaren Regeln tut.

2. **Governance-Regeln definieren**
   Festlegen, unter welchen Voraussetzungen Entscheidungen gueltig sind und wie mit fehlenden Schluesselrollen umgegangen wird.

3. **Minimalen Priorisierungsrahmen beschliessen**
   Ein schlankes Bewertungsmodell mit Pflichtdimensionen festlegen, zum Beispiel Business Impact, KPI-Bezug, Abhaengigkeiten, Aufwand und Risiken.

4. **One-Pager-Content-Standard finalisieren**
   Pflichtfelder des `one-pagers` an der tatsaechlichen Entscheidungslogik ausrichten, inklusive klarer `decision ask`.

5. **Fuehrendes Artefaktmodell festlegen**
   Bestimmen, wie `Jira`, `one-pager`, Decision Log und Folgeartefakte zusammenspielen und welches Artefakt im Zweifel fuehrend ist.

### Einfuehrungsschritte fuer Pilot und Roll-out

1. **One-Pager-Operating-Model einrichten**
   Submission Gate, Pre-read-Fenster, Cut-off, Review-Checkliste, Versionierung und Archivierung definieren.

2. **Meeting-Ablauf anpassen**
   Agenda auf priorisierungsrelevante Themen zuschneiden, Statusinhalte asynchron verlagern und Moderation sichtbar verankern.

3. **Teilnehmerlogik operationalisieren**
   Pro Thema Abhaengigkeiten und benoetigte Stakeholder vorab pruefen, insbesondere bei `PlatOps` und Business-Bezug.

4. **Decision Log und Rueckfluss standardisieren**
   Einheitliches Ergebnisartefakt festlegen und definieren, wie Beschluesse in Domains und weitere Kommunikationsformate zurueckgespielt werden.

5. **Pilot in wenigen Zyklen testen**
   Das neue Modell in zwei bis drei kommenden Runden anwenden und gezielt beobachten, ob Vorbereitung, Entscheidungsqualitaet und Nachvollziehbarkeit steigen.

## Vorschlag fuer Pilotierung

Ein sinnvoller Pilot waere klein genug fuer Lernen, aber gross genug fuer echte Reibung. Daher bietet sich an:

- den `one-pager` zunaechst nur fuer neue oder priorisierungsrelevante Themen verpflichtend zu machen
- das neue Modell in zwei bis drei kommenden Review-Zyklen zu testen
- den Pilot explizit auf Themen mit echten Abhaengigkeiten und moeglichen Kapazitaetskonflikten anzuwenden

Beobachtungspunkte im Pilot:

- Sind Stakeholder besser vorbereitet?
- Werden Entscheidungen im Meeting klarer und spaeter seltener relativiert?
- Ist schneller erkennbar, worin Problem, Impact und `decision ask` eines Themas bestehen?
- Reduziert sich die Doppelpflege zwischen `Jira`, Meeting-Unterlagen und Folgeartefakten?
- Wird Discovery-Arbeit sichtbarer und besser diskutierbar?

Ein Pilot ist erfolgreich, wenn nicht nur die Unterlagen besser aussehen, sondern Entscheidungen schneller verstanden, sauberer dokumentiert und stabiler getragen werden. Der Unterschied ist subtil, aber relevant. Wie bei vielen Meetings ist die Formatkosmetik selten das eigentliche Problem.

## Quellenbasis

- Feedback-Seite: [cache/confluence-1766850575.md](cache/confluence-1766850575.md)
- Proposal-Seite: [cache/confluence-1782939650.md](cache/confluence-1782939650.md)
- Standards-/Proposal-Seite mit One-Pager-Fokus: [cache/confluence-1782054944.md](cache/confluence-1782054944.md)

Originale Confluence-Links:

- [Prio Meetings of the domains](https://trustedshops.atlassian.net/wiki/x/DwBQaQ)
- [Proposal Klaus - April 2026](https://trustedshops.atlassian.net/wiki/x/AoBFag)
- [Meeting Process Improvement Proposals and Standards](https://trustedshops.atlassian.net/wiki/x/IAA4ag)
