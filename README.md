# Cursor Personal Assistant

A personal work assistant running inside Cursor IDE, built for a Process Manager (PrOps). It connects to **Jira** and **Confluence** (Atlassian Cloud) and helps with daily self-organization, issue maintenance, and handling waiting periods — all without leaving the editor.

The assistant communicates in German and only acts on explicit request (pull principle). It comes with a personality: meet **Siegfried**, a logical, dry-humored nerd in his early thirties who'd rather weigh options than express feelings.

---

## Features

| Feature | Trigger | Description |
|---|---|---|
| **A – Issue Refinement** | Issue key or "neues Issue anlegen" | Structured interview to fill a Jira issue with a 5-block description (Background, Goal, Acceptance Criteria, Additional Info, Stakeholder) |
| **B – Remind-Date Assistant** | "Remind-Dates", "Was ist fällig?" | Lists overdue remind-dates for waiting issues and offers actions: reschedule, follow-up text, status change, or comment |
| **C – Daily Briefing** | "Was liegt an?", "Was mache ich heute?" | Prioritized overview: active issues → queue → remind-date hint → backlog suggestions. Ends with a start recommendation |
| **D – Re-entry Mode** | "Was hat sich seit [Datum] geändert?" | Catch-up summary after absence: new assignments, status changes, new comments |
| **E – Confluence Research** | "Was gibt es in Confluence zu PROPS-123?" | Reads linked Confluence pages from an issue or searches by topic |
| **F – Team Lead Update** | "Update für meine TL" | Informal summary of current work, blockers, and recent completions |

---

## Architecture

```
cursor-personal-assistant/
├── .cursor/
│   └── rules/
│       ├── personal-assistant.mdc   # Agent behavior, tools, features, Jira data model
│       └── siegfried-personality.mdc # Personality layer
├── skills/
│   └── issue-refinement/
│       └── SKILL.md                 # Step-by-step interview flow for issue refinement
├── src/
│   ├── list_my_issues.py            # Fetch issues by mode (active, next, backlog, ...)
│   ├── read_jira_issue.py           # Read a single issue (ADF → Markdown)
│   ├── update_jira_issue.py         # Update or create issues (ADF panels + custom fields)
│   ├── add_jira_comment.py          # Add a comment to an issue
│   ├── transition_jira_issue.py     # Change issue status
│   ├── search_jira_issues.py        # JQL search
│   ├── read_confluence_page.py      # Read a Confluence page by URL or ID
│   └── search_confluence.py         # CQL search in Confluence
├── cache/                           # Temporary API responses (gitignored)
└── SPEC.md                          # Full feature specification
```

The Cursor Rules (`*.mdc`) define what the agent knows and how it behaves. The Python scripts in `src/` are the actual tools the agent runs via the terminal. The agent never writes to Jira without explicit user confirmation.

---

## Setup

### 1. Prerequisites

- [Cursor IDE](https://www.cursor.com/)
- Python 3.x
- An Atlassian account with API token access to `trustedshops.atlassian.net`

### 2. Environment Variables

Set the following in your shell environment (e.g. in your PowerShell profile or `.env`):

```powershell
$env:ATLASSIAN_USER = "your-email@example.com"
$env:ATLASSIAN_TOKEN = "your-atlassian-api-token"
```

Generate an API token at: [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

### 3. Open in Cursor

Open the repository folder in Cursor. The rules in `.cursor/rules/` are picked up automatically.

---

## Usage

Just talk to the Cursor Agent in natural language (German). Examples:

```
Was liegt an?
Was habe ich letzte Woche erledigt?
Remind-Dates bitte
PROPS-930 refinen
Neues Issue anlegen
Was gibt es in Confluence zu PROPS-948?
Update für meine TL
```

Before any write operation (create, update, comment, status change), the agent will always show a preview and ask for confirmation.

---

## Jira Data Model

**Status groups used:**

| Group | Statuses |
|---|---|
| Active | `In Progress`, `Ongoing` |
| Queue | `Next`, `To Do`, `ToDo`, `Ready to pull` |
| Waiting | `Waiting`, `Blocked`, `On Hold` |
| Backlog | `Backlog` |
| New | `To be refined` |
| Done | `Done`, `Rejected` |

**Custom field:** Remind date → `customfield_10246` (format: `YYYY-MM-DD`)

**Excluded:** `Epic` issue type is ignored in all lists and briefings.

---

## Issue Description Structure

Each issue uses a standardized 5-block ADF description:

1. **Background / Problem Description** – Context and why the issue exists
2. **Goal** – Outcome, not output ("what improves", not "what is delivered")
3. **Acceptance Criteria** – "We call this task done when ..."
4. **Additional Information** – Links to Miro, Confluence, Slack, etc.
5. **Stakeholder / Dependencies / Prerequisites** – People, teams, dependencies

Issue contents are always written to Jira in **English**, regardless of the language used during the interview.
