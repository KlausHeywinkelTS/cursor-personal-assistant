# Reads a Confluence page and converts it to Markdown.
# Uses environment variables for credentials: ATLASSIAN_USER and ATLASSIAN_TOKEN
# Uses the Atlassian Confluence REST API (v2 with ADF body format).
#
# Parameters:
#   -u, --url:     URL of the Confluence page (full URL or tiny link like /wiki/x/...)
#   -p, --page-id: Confluence page ID (numeric)
# Always writes output to cache/confluence-<page-id>.md

import json
import os
import re
import sys
import argparse
from typing import Any

import requests

sys.path.insert(0, os.path.dirname(__file__))
from read_jira_issue import adf_to_markdown

CONFLUENCE_BASE_URL = "https://trustedshops.atlassian.net"


def _get_auth() -> tuple[str, str]:
    user = os.getenv("ATLASSIAN_USER")
    token = os.getenv("ATLASSIAN_TOKEN")
    if not user or not token:
        raise RuntimeError(
            "Missing credentials. Please set ATLASSIAN_USER and ATLASSIAN_TOKEN environment variables."
        )
    return user, token


def _confluence_get(path: str) -> dict[str, Any]:
    user, token = _get_auth()
    url = f"{CONFLUENCE_BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, auth=(user, token))
    response.raise_for_status()
    return response.json()


def _resolve_page_id(url_or_id: str) -> str:
    """Extract a numeric Confluence page ID from various URL formats or a bare ID."""
    text = url_or_id.strip()

    if text.isdigit():
        return text

    # /wiki/spaces/{spaceKey}/pages/{pageId}  (with or without trailing title slug)
    m = re.search(r"/wiki/spaces/[^/]+/pages/(\d+)", text)
    if m:
        return m.group(1)

    # /pages/viewpage.action?pageId=123
    m = re.search(r"pageId=(\d+)", text)
    if m:
        return m.group(1)

    # Tiny-link: /wiki/x/{token} – follow the authenticated redirect to the real URL.
    if "/wiki/x/" in text:
        user, token = _get_auth()
        resp = requests.head(text, auth=(user, token), allow_redirects=True)
        resp.raise_for_status()
        final = resp.url
        m = re.search(r"/pages/(\d+)", final)
        if m:
            return m.group(1)
        m = re.search(r"pageId=(\d+)", final)
        if m:
            return m.group(1)
        raise ValueError(f"Could not extract page ID from redirected URL: {final}")

    raise ValueError(f"Could not determine page ID from input: {text}")


def read_confluence_page(page_id: str) -> tuple[str, str]:
    """Return (title, markdown_body) for a Confluence page."""
    data = _confluence_get(
        f"/wiki/api/v2/pages/{page_id}?body-format=atlas_doc_format"
    )
    title = data.get("title", "")
    adf_raw = (data.get("body") or {}).get("atlas_doc_format", {}).get("value", "{}")
    adf_doc = json.loads(adf_raw) if isinstance(adf_raw, str) else adf_raw
    markdown_body = adf_to_markdown(adf_doc)
    return title, markdown_body


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Read a Confluence page and convert to Markdown"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--url", help="URL of the Confluence page (or tiny link)")
    group.add_argument("-p", "--page-id", help="Numeric Confluence page ID")
    args = parser.parse_args()

    page_id = args.page_id if args.page_id else _resolve_page_id(args.url)
    print(f"Page ID: {page_id}")

    title, markdown_body = read_confluence_page(page_id)
    print(f"Title: {title}")
    print("Content (markdown):")
    print(markdown_body.rstrip())

    cache_dir = os.path.join(os.getcwd(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    output_path = os.path.join(cache_dir, f"confluence-{page_id}.md")
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {title}\n\n")
        f.write(f"Page ID: {page_id}\n\n")
        f.write(markdown_body)

    print(f"Wrote markdown to: {output_path}")


if __name__ == "__main__":
    main()
