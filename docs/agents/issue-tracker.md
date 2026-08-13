# Issue Tracker

Issues for this repository live in Jira Cloud.

## Access and operations

- Use the installed `jira` skill and its bundled Python CLI scripts for all Jira operations.
- Do not use Atlassian MCP or direct Jira REST calls.
- Use the script that matches the intent: read an issue, search with JQL, list personal issues, add a comment, transition a status, or create or update an issue.
- Keep credentials in the environment variables required by the Jira skill; do not write credentials into this repository.

## Write operations

Before creating or updating an issue, adding a comment, or changing a status, show the intended change and obtain the user's explicit confirmation.

## When a skill says "publish to the issue tracker"

Create or update the Jira issue with the Jira skill after confirmation. Ask for any required Jira-specific information that is unavailable, such as the project key or issue type.

## When a skill says "fetch the relevant ticket"

Read the referenced Jira issue with the Jira skill. Include comments or history when the request concerns decisions, discussion, status evolution, or blockers.
