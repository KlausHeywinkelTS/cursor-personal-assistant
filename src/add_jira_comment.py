"""Add a plain-text comment to a Jira issue (stored as ADF).

Usage:
    py src/add_jira_comment.py -i PROPS-123 --text "Kommentar Text"
    py src/add_jira_comment.py -i PROPS-123 --from-file cache/comment.txt
"""

import argparse
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import _get_jira_auth, JIRA_BASE_URL


def _build_comment_adf(text: str) -> dict:
    """Convert plain text to ADF doc. Double newlines = paragraph break."""
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
        paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
    return {"version": 1, "type": "doc", "content": paragraphs}


def add_comment(issue_key: str, text: str) -> None:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, auth=(user, token), json={"body": _build_comment_adf(text)})
    resp.raise_for_status()
    print(f"Kommentar zu {issue_key} hinzugefuegt.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Add a comment to a Jira issue")
    parser.add_argument("-i", "--issue-key", required=True, help="Issue key (e.g. PROPS-123)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Comment text (inline)")
    group.add_argument("--from-file", help="Read comment text from this file")
    args = parser.parse_args()

    text = args.text
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as fh:
            text = fh.read()

    add_comment(args.issue_key, text)


if __name__ == "__main__":
    main()
