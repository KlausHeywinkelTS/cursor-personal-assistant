"""Update or create a Jira issue with a structured ADF description (5 info panels).

Usage:
    # Update description from JSON blocks file:
    py src/update_jira_issue.py -i PROPS-123 --blocks-file cache/blocks.json

    # Update only summary or remind-date (blocks-file optional):
    py src/update_jira_issue.py -i PROPS-123 --summary "New title"
    py src/update_jira_issue.py -i PROPS-123 --remind-date 2026-04-01

    # Create a new issue:
    py src/update_jira_issue.py --create --project PROPS --summary "Title" --blocks-file cache/blocks.json

Blocks JSON format (cache/blocks.json):
    {
      "background": "...",
      "goal": "...",
      "acceptance_criteria": "...",
      "additional_information": "...",
      "stakeholder": "..."
    }
    Any block can be omitted or empty — it will simply be skipped.
"""

import argparse
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _get_jira_auth, JIRA_BASE_URL

REMIND_DATE_FIELD = "customfield_10246"

BLOCK_TITLES: dict[str, str] = {
    "background": "Background / Problem Description",
    "goal": "Goal",
    "acceptance_criteria": "Acceptance Criteria",
    "additional_information": "Additional Information",
    "stakeholder": "Stakeholder / Dependencies / Prerequisites",
}
BLOCK_ORDER = ["background", "goal", "acceptance_criteria", "additional_information", "stakeholder"]


# ---------------------------------------------------------------------------
# ADF builders
# ---------------------------------------------------------------------------

def _text_to_adf_paragraphs(text: str) -> list[dict]:
    """Convert plain text to ADF paragraph nodes. Double newlines = new paragraph."""
    paragraphs: list[dict] = []
    for para in text.split("\n\n"):
        lines = para.strip()
        if not lines:
            continue
        inline: list[dict] = []
        parts = lines.split("\n")
        for i, line in enumerate(parts):
            if line:
                inline.append({"type": "text", "text": line})
            if i < len(parts) - 1:
                inline.append({"type": "hardBreak"})
        if inline:
            paragraphs.append({"type": "paragraph", "content": inline})
    if not paragraphs:
        paragraphs.append({"type": "paragraph", "content": [{"type": "text", "text": ""}]})
    return paragraphs


def build_adf_info_panel(title: str, content_text: str) -> dict:
    """Build an ADF info panel node with a h3 heading and text content."""
    panel_content: list[dict] = [
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": title}],
        }
    ]
    panel_content.extend(_text_to_adf_paragraphs(content_text))
    return {
        "type": "panel",
        "attrs": {"panelType": "info"},
        "content": panel_content,
    }


def build_issue_description_adf(blocks: dict) -> dict:
    """Build the full ADF doc from up to 5 named blocks. Empty blocks are skipped."""
    doc_content: list[dict] = []
    for key in BLOCK_ORDER:
        text = (blocks.get(key) or "").strip()
        if not text:
            continue
        doc_content.append(build_adf_info_panel(BLOCK_TITLES[key], text))
    if not doc_content:
        doc_content = [{"type": "paragraph", "content": []}]
    return {"version": 1, "type": "doc", "content": doc_content}


# ---------------------------------------------------------------------------
# Jira write helpers
# ---------------------------------------------------------------------------

def _jira_put(path: str, payload: dict) -> None:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, auth=(user, token), json=payload)
    resp.raise_for_status()


def _jira_post(path: str, payload: dict) -> dict:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, auth=(user, token), json=payload)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public actions
# ---------------------------------------------------------------------------

def update_issue(
    issue_key: str,
    *,
    blocks: dict | None = None,
    summary: str | None = None,
    remind_date: str | None = None,
) -> None:
    fields: dict = {}
    if blocks is not None:
        fields["description"] = build_issue_description_adf(blocks)
    if summary:
        fields["summary"] = summary
    if remind_date:
        fields[REMIND_DATE_FIELD] = remind_date  # YYYY-MM-DD
    if not fields:
        print("Nichts zu aktualisieren — keine Felder angegeben.")
        return
    _jira_put(f"/rest/api/3/issue/{issue_key}", payload={"fields": fields})
    print(f"Issue {issue_key} erfolgreich aktualisiert.")
    print(f"URL: {JIRA_BASE_URL}/browse/{issue_key}")


def create_issue(
    project_key: str,
    summary: str,
    *,
    blocks: dict | None = None,
    issue_type: str = "Task",
) -> str:
    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if blocks:
        fields["description"] = build_issue_description_adf(blocks)
    result = _jira_post("/rest/api/3/issue", payload={"fields": fields})
    key = result.get("key", "")
    print(f"Issue erstellt: {key}")
    print(f"URL: {JIRA_BASE_URL}/browse/{key}")
    return key


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Update or create a Jira issue with structured ADF description"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-i", "--issue-key", help="Issue key to update (e.g. PROPS-123)")
    mode.add_argument("--create", action="store_true", help="Create a new issue")

    parser.add_argument("--project", help="Project key for new issue (required with --create)")
    parser.add_argument("--summary", help="Issue summary / title")
    parser.add_argument("--issue-type", default="Task", help="Issue type for --create (default: Task)")
    parser.add_argument("--blocks-file", help="JSON file with description blocks")
    parser.add_argument("--remind-date", help="Remind date in YYYY-MM-DD format")
    args = parser.parse_args()

    blocks: dict | None = None
    if args.blocks_file:
        with open(args.blocks_file, encoding="utf-8") as fh:
            blocks = json.load(fh)

    if args.create:
        if not args.project:
            parser.error("--project is required with --create")
        if not args.summary:
            parser.error("--summary is required with --create")
        create_issue(args.project, args.summary, blocks=blocks, issue_type=args.issue_type)
    else:
        update_issue(
            args.issue_key,
            blocks=blocks,
            summary=args.summary,
            remind_date=args.remind_date,
        )


if __name__ == "__main__":
    main()
