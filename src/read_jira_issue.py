# Reads a jira issue and prints summary and description on the console.
# Uses environment variables for the jira credentials: ATLASSIAN_USER and ATLASSIAN_TOKEN
# Uses the Atlassian REST API to read the issue.
# Uses the requests library to make the API calls.
# Parameter to the script: 
# -i, --issue-key: The key of the issue to read.
# Always writes output to cache/<issue-key>.md

import os
import requests
import argparse
import sys
from typing import Any, Optional


def _adf_apply_marks(text: str, marks: Optional[list[dict[str, Any]]]) -> str:
    if not marks:
        return text

    # Apply marks by wrapping; order matters for link-vs-formatting, so handle link last.
    link_href: Optional[str] = None
    for mark in marks:
        mtype = (mark or {}).get("type")
        if mtype == "strong":
            text = f"**{text}**"
        elif mtype == "em":
            text = f"*{text}*"
        elif mtype == "code":
            text = f"`{text}`"
        elif mtype == "strike":
            text = f"~~{text}~~"
        elif mtype == "link":
            link_href = ((mark or {}).get("attrs") or {}).get("href")

    if link_href:
        # If text is empty, fall back to the URL.
        label = text if text else link_href
        text = f"[{label}]({link_href})"

    return text


def _adf_render_inlines(nodes: Optional[list[dict[str, Any]]]) -> str:
    if not nodes:
        return ""

    parts: list[str] = []
    for node in nodes:
        ntype = (node or {}).get("type")
        if ntype == "text":
            raw = node.get("text", "")
            parts.append(_adf_apply_marks(raw, node.get("marks")))
        elif ntype == "hardBreak":
            parts.append("\n")
        elif ntype == "inlineCard":
            url = ((node or {}).get("attrs") or {}).get("url")
            parts.append(f"[{url}]({url})" if url else "")
        elif ntype == "emoji":
            # Best effort
            short = ((node or {}).get("attrs") or {}).get("shortName")
            parts.append(short or "")
        elif ntype == "mention":
            text = ((node or {}).get("attrs") or {}).get("text")
            parts.append(text or "")
        else:
            # Fallback: render nested inline content if present
            parts.append(_adf_render_inlines((node or {}).get("content")))

    return "".join(parts)


def _adf_blockquote(lines: list[str]) -> str:
    # Keep blank lines inside blockquotes compatible with Markdown renderers:
    # represent blank line as '>'.
    out: list[str] = []
    for line in lines:
        out.append("> " + line if line else ">")
    return "\n".join(out)


def _adf_render_blocks(nodes: Optional[list[dict[str, Any]]], indent: str = "") -> list[str]:
    if not nodes:
        return []

    blocks: list[str] = []
    for node in nodes:
        blocks.extend(_adf_render_block(node, indent=indent))
    return blocks


def _adf_render_table(table_node: dict[str, Any], indent: str = "") -> list[str]:
    # Very small best-effort table renderer. Assumes first row is header.
    rows = (table_node or {}).get("content") or []
    if not rows:
        return []

    rendered_rows: list[list[str]] = []
    for row in rows:
        cells = (row or {}).get("content") or []
        rendered_cells: list[str] = []
        for cell in cells:
            cell_blocks = _adf_render_blocks((cell or {}).get("content") or [], indent="")
            cell_text = " ".join([b.strip() for b in cell_blocks if b.strip()]) or ""
            # Escape pipes
            rendered_cells.append(cell_text.replace("|", r"\|"))
        rendered_rows.append(rendered_cells)

    # Normalize column count
    col_count = max((len(r) for r in rendered_rows), default=0)
    if col_count == 0:
        return []
    for r in rendered_rows:
        while len(r) < col_count:
            r.append("")

    header = rendered_rows[0]
    body = rendered_rows[1:] if len(rendered_rows) > 1 else []
    lines = []
    lines.append(indent + "| " + " | ".join(header) + " |")
    lines.append(indent + "| " + " | ".join(["---"] * col_count) + " |")
    for r in body:
        lines.append(indent + "| " + " | ".join(r) + " |")
    return lines


def _adf_render_block(node: Optional[dict[str, Any]], indent: str = "") -> list[str]:
    if not node:
        return []

    ntype = node.get("type")
    content = node.get("content") or []
    attrs = node.get("attrs") or {}

    if ntype == "doc":
        # Join blocks with blank lines (but avoid growing multiple blanks).
        rendered = _adf_render_blocks(content, indent=indent)
        out: list[str] = []
        for block in rendered:
            if not block.strip():
                # keep single blank line at most
                if out and out[-1] != "":
                    out.append("")
                continue
            if out and out[-1] != "":
                out.append("")
            out.append(block)
        return out

    if ntype == "paragraph":
        text = _adf_render_inlines(content).strip()
        return [indent + text] if text else []

    if ntype == "heading":
        level = int(attrs.get("level", 1) or 1)
        level = max(1, min(level, 6))
        text = _adf_render_inlines(content).strip()
        return [indent + ("#" * level) + " " + text] if text else []

    if ntype == "bulletList":
        items = content
        out: list[str] = []
        for item in items:
            out.extend(_adf_render_list_item(item, indent=indent, ordered=False))
        return out

    if ntype == "orderedList":
        start = int(attrs.get("order", 1) or 1)
        out: list[str] = []
        idx = start
        for item in content:
            out.extend(_adf_render_list_item(item, indent=indent, ordered=True, number=idx))
            idx += 1
        return out

    if ntype == "panel":
        panel_type = attrs.get("panelType")  # info|success|warning|error
        children_blocks = _adf_render_blocks(content, indent="")
        # Flatten block list into lines (keeping blank lines)
        lines: list[str] = []
        for b in children_blocks:
            lines.extend(b.splitlines() if b else [""])

        # GitHub Flavored Markdown "alerts":
        # > [!NOTE]
        # > ...
        admonition_map = {
            "info": "NOTE",
            "note": "NOTE",
            "success": "TIP",
            "warning": "WARNING",
            "error": "CAUTION",
        }
        label = admonition_map.get(panel_type)
        if label:
            lines = [f"[!{label}]"] + (lines if lines else [""])
        quoted = _adf_blockquote(lines)
        return [(indent + quoted.replace("\n", "\n" + indent)).rstrip()]

    if ntype == "blockquote":
        children_blocks = _adf_render_blocks(content, indent="")
        lines: list[str] = []
        for b in children_blocks:
            lines.extend(b.splitlines() if b else [""])
        quoted = _adf_blockquote(lines)
        return [(indent + quoted.replace("\n", "\n" + indent)).rstrip()]

    if ntype == "rule":
        return [indent + "---"]

    if ntype == "codeBlock":
        language = attrs.get("language") or ""
        code_text = _adf_render_inlines(content)
        # Some ADF codeBlocks nest text inside paragraphs; handle that too.
        if not code_text.strip():
            code_text = "\n".join(_adf_render_blocks(content, indent=""))
        fence = "```"
        return [indent + f"{fence}{language}\n{code_text}\n{fence}"]

    if ntype == "table":
        return _adf_render_table(node, indent=indent)

    if ntype in {"tableRow", "tableCell", "tableHeader"}:
        # Rendered by table parent.
        return []

    # Fallback: render children as blocks.
    return _adf_render_blocks(content, indent=indent)


def _adf_render_list_item(
    item: Optional[dict[str, Any]],
    *,
    indent: str,
    ordered: bool,
    number: Optional[int] = None,
) -> list[str]:
    if not item:
        return []

    # ADF listItem contains block nodes: usually paragraph, possibly nested lists.
    blocks = (item.get("content") or []) if item.get("type") == "listItem" else (item.get("content") or [])
    rendered_blocks = _adf_render_blocks(blocks, indent="")

    prefix = f"{number}. " if ordered else "- "
    first_line = ""
    rest: list[str] = []

    if rendered_blocks:
        first = rendered_blocks[0].strip()
        first_line = first
        rest = rendered_blocks[1:]

    lines: list[str] = []
    lines.append(indent + prefix + first_line)

    # Continuation lines: indent under the bullet/number.
    # For GitHub/CommonMark, nested blocks (esp. fenced code blocks) are more reliable
    # when indented at least 4 spaces under the list item.
    continuation_indent = indent + (" " * max(4, len(prefix)))
    for b in rest:
        if not b.strip():
            continue
        # Keep multi-line blocks aligned
        for line in b.splitlines():
            lines.append(continuation_indent + line)

    return lines


def adf_to_markdown(adf_doc: dict[str, Any]) -> str:
    """
    Convert Atlassian Document Format (ADF) to Markdown (best-effort).
    Jira Cloud `fields.description` is commonly returned as ADF JSON.
    """
    blocks = _adf_render_block(adf_doc, indent="")
    # _adf_render_block returns list of blocks; join with newlines preserving blank lines.
    text = "\n".join(blocks).strip() + "\n"
    return text

JIRA_BASE_URL = "https://trustedshops.atlassian.net"
ALLOWED_CHILD_ISSUE_TYPES = {"task", "story"}


def _get_jira_auth() -> tuple[str, str]:
    user = os.getenv("ATLASSIAN_USER")
    token = os.getenv("ATLASSIAN_TOKEN")
    if not user or not token:
        raise RuntimeError(
            "Missing credentials. Please set ATLASSIAN_USER and ATLASSIAN_TOKEN environment variables."
        )
    return user, token


def _jira_get(path: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, auth=(user, token), params=params)
    response.raise_for_status()
    return response.json()


def _jira_post(path: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    user, token = _get_jira_auth()
    url = f"{JIRA_BASE_URL}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, auth=(user, token), json=payload)
    response.raise_for_status()
    return response.json()


def read_jira_issue(issue_key: str) -> dict[str, Any]:
    return _jira_get(f"/rest/api/3/issue/{issue_key}")


def _jira_search(
    *,
    jql: str,
    fields: list[str],
    max_results: int = 500,
) -> list[dict[str, Any]]:
    """
    Jira Cloud search helper with pagination (JQL enhanced search endpoint).
    Returns the list of issues as returned by the API (each item contains at least 'key' and 'fields').
    """
    issues: list[dict[str, Any]] = []
    page_size = 100
    next_page_token: Optional[str] = None
    while True:
        remaining = max_results - len(issues)
        if remaining <= 0:
            break
        page_limit = min(page_size, remaining)
        payload: dict[str, Any] = {
            "jql": jql,
            "fields": fields,
            "maxResults": page_limit,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        data = _jira_post("/rest/api/3/search/jql", payload=payload)
        page = data.get("issues") or []
        issues.extend(page)
        if len(page) == 0:
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    return issues


def _render_adf_or_text(value: Any) -> str:
    if isinstance(value, dict) and value.get("type") == "doc":
        return adf_to_markdown(value).rstrip()
    if value is None:
        return ""
    return str(value).strip()


def _child_supplement_markdown_lines(children: list[dict[str, Any]]) -> list[str]:
    if not children:
        return []

    out: list[str] = [
        "## Supplemental information from direct child work-items (Task/Story)",
        "",
        (
            "Important: Epic information is the primary source of truth. "
            "Child work-items only provide additional details."
        ),
        "",
    ]
    for c in children:
        key = c.get("key") or ""
        summary = c.get("summary") or ""
        status = c.get("status") or ""
        issuetype = c.get("issuetype") or ""
        browse_url = c.get("url") or (f"{JIRA_BASE_URL}/browse/{key}" if key else "")
        description = (c.get("description_md") or "").strip()

        meta = ", ".join([p for p in [issuetype, status] if p]).strip()
        meta = f" ({meta})" if meta else ""

        if key and browse_url:
            out.append(f"- [{key}]({browse_url}) - {summary}{meta}")
        elif key:
            out.append(f"- {key} - {summary}{meta}")
        else:
            out.append(f"- {summary}{meta}")

        if description:
            for line in description.splitlines():
                out.append(f"  {line}" if line else "")
        out.append("")
    return out


def _extract_children(issue: dict[str, Any], *, include_description: bool) -> list[dict[str, Any]]:
    """
    Best-effort child extraction:
    - For any issue: include direct Sub-Tasks from fields.subtasks
    - For Epics: include direct epic children via Jira Search
    - Only include child issue types Task/Story
    - Optionally include child descriptions
    """
    issue_key = issue.get("key") or ""
    fields = (issue.get("fields") or {})
    issuetype_name = (((fields.get("issuetype") or {}).get("name")) or "").strip().lower()

    children_by_key: dict[str, dict[str, Any]] = {}

    if issuetype_name == "epic" and issue_key:
        wanted_fields = ["summary", "status", "issuetype"]
        if include_description:
            wanted_fields.append("description")
        # Try broad query first, then parent-only fallback.
        jql_candidates = [
           f'parent = "{issue_key}"',
        ]
        for jql in jql_candidates:
            try:
                found = _jira_search(jql=jql, fields=wanted_fields, max_results=2000)
                for it in found:
                    k = it.get("key") or ""
                    if not k or k == issue_key:
                        continue
                    it_fields = it.get("fields") or {}
                    child_issuetype = (((it_fields.get("issuetype") or {}).get("name")) or "").strip()
                    if child_issuetype.lower() not in ALLOWED_CHILD_ISSUE_TYPES:
                        continue
                    children_by_key[k] = {
                        "key": k,
                        "summary": it_fields.get("summary") or "",
                        "status": ((it_fields.get("status") or {}).get("name")) or "",
                        "issuetype": child_issuetype,
                        "url": f"{JIRA_BASE_URL}/browse/{k}",
                        "description_md": _render_adf_or_text(it_fields.get("description")) if include_description else "",
                    }
                break
            except requests.HTTPError as e:
                print(f"Error fetching children for epic {issue_key} with JQL '{jql}': {e}")
                continue

    # Final list, stable/sorted by key.
    children = [v for k, v in children_by_key.items() if k]
    children.sort(key=lambda x: (x.get("key") or ""))
    return children

def main():
    # Windows consoles often default to cp1252; Jira content can contain Unicode (e.g. U+2011).
    # Ensure printing does not crash on such characters.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description='Read a Jira issue and print summary and description')
    parser.add_argument('-i', '--issue-key', required=True, help='The key of the issue to read')
    parser.add_argument(
        '--include-children',
        action='store_true',
        help='Include direct child work-item descriptions (Task/Story) as supplemental information.',
    )
    args = parser.parse_args()
    issue = read_jira_issue(args.issue_key)
    fields = issue.get("fields", {})

    print(f"Issue key: {args.issue_key}")
    print(f"Issue summary: {fields['summary']}")

    parent_field = fields.get("parent") or {}
    parent_key = parent_field.get("key") or ""
    parent_summary = (parent_field.get("fields") or {}).get("summary") or ""
    if parent_key:
        print(f"Parent: {parent_key} — {parent_summary}")

    description = fields.get("description")
    description_md = _render_adf_or_text(description)

    print("Issue description (markdown):")
    print(description_md.rstrip())

    cache_dir = os.path.join(os.getcwd(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    output_path = os.path.join(cache_dir, f"{args.issue_key}.md")
    release_brief_url = fields.get("customfield_10131") or ""

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"Issue key: {args.issue_key}\n")
        if parent_key:
            f.write(f"Parent: {parent_key} — {parent_summary}\n")
        if release_brief_url:
            f.write(f"Release Brief: [{release_brief_url}]({release_brief_url})\n")
        f.write(f"Issue summary: {fields['summary']}\n")
        f.write("\n")
        f.write(description_md)
        if args.include_children:
            children = _extract_children(issue, include_description=True)
            children_section = _child_supplement_markdown_lines(children)
            if children_section:
                f.write("\n\n")
                f.write("\n".join(children_section))

    print(f"Wrote markdown to: {output_path}")
    return 0

if __name__ == "__main__":
    main()