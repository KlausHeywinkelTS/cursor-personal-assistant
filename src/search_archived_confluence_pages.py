"""Search archived and deleted Confluence pages by title or former URL slug.

The Confluence v2 pages endpoint only supports exact title filtering. This
script therefore retrieves archived, trashed, and deleted pages, then filters
them by creation date and ranks relevant title matches locally.

Usage:
    py src/search_archived_confluence_pages.py --query "SW+Capitalization+Technical+Solutions+for+Expense+Tracking"
    py src/search_archived_confluence_pages.py --query "Expense Tracking" --limit 50
    py src/search_archived_confluence_pages.py --query "Expense Tracking" -o cache/archived_pages.json

Pages permanently purged from the Confluence trash cannot be recovered or
searched through the API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus, urljoin

import requests


CONFLUENCE_BASE_URL = "https://trustedshops.atlassian.net"
PAGES_URL = f"{CONFLUENCE_BASE_URL}/wiki/api/v2/pages"
DEFAULT_STATUSES = ("archived", "trashed", "deleted")
DEFAULT_CREATED_AFTER = date(2026, 7, 1)
STOP_WORDS = frozenset({"and", "der", "die", "das", "for", "in", "of", "the", "to", "und"})


def get_auth() -> tuple[str, str]:
    """Return Confluence credentials from the established environment variables."""
    user = os.getenv("ATLASSIAN_USER")
    token = os.getenv("ATLASSIAN_TOKEN")
    if not user or not token:
        raise RuntimeError(
            "Missing credentials. Please set ATLASSIAN_USER and ATLASSIAN_TOKEN "
            "environment variables."
        )
    return user, token


def normalize_query(slug_or_title: str) -> str:
    """Decode a URL slug and normalize its whitespace."""
    return " ".join(unquote_plus(slug_or_title).split())


def query_terms(query: str) -> list[str]:
    """Return meaningful, unique title terms in their original order."""
    terms: list[str] = []
    for term in re.findall(r"\w+", query.casefold(), flags=re.UNICODE):
        if len(term) < 2 or term in STOP_WORDS or term in terms:
            continue
        terms.append(term)
    return terms


def parse_date(value: str) -> date:
    """Parse a CLI date in ISO format."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD."
        ) from exc


def _absolute_url(url: str) -> str:
    return urljoin(CONFLUENCE_BASE_URL, url)


def _next_page_url(response: requests.Response, payload: dict[str, Any]) -> str | None:
    """Extract the v2 cursor URL from either body links or HTTP Link headers."""
    body_next = ((payload.get("_links") or {}).get("next")) or ""
    if body_next:
        return _absolute_url(str(body_next))

    header_next = (response.links.get("next") or {}).get("url")
    return _absolute_url(header_next) if header_next else None


def list_pages_with_statuses(
    statuses: Iterable[str] = DEFAULT_STATUSES,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Return all pages in the selected non-current statuses."""
    user, token = get_auth()
    params: list[tuple[str, str | int]] = [("limit", page_size)]
    params.extend(("status", status) for status in statuses)

    pages: list[dict[str, Any]] = []
    seen_page_ids: set[str] = set()
    seen_urls: set[str] = set()
    url = PAGES_URL

    while url and url not in seen_urls:
        seen_urls.add(url)
        response = requests.get(
            url,
            headers={"Accept": "application/json"},
            auth=(user, token),
            params=params if url == PAGES_URL else None,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        for page in payload.get("results") or []:
            page_id = str(page.get("id") or "")
            if page_id and page_id not in seen_page_ids:
                seen_page_ids.add(page_id)
                pages.append(page)

        url = _next_page_url(response, payload)

    return pages


def _title_score(title: str, normalized_query: str, terms: list[str]) -> tuple[int, int]:
    normalized_title = " ".join(title.casefold().split())
    title_terms = set(re.findall(r"\w+", normalized_title, flags=re.UNICODE))
    matching_terms = sum(term in title_terms for term in terms)

    if normalized_title == normalized_query.casefold():
        return 1_000, matching_terms
    if normalized_query.casefold() in normalized_title:
        return 900, matching_terms
    if terms and matching_terms == len(terms):
        return 800, matching_terms
    return matching_terms * 100, matching_terms


def filter_pages_created_after(
    pages: Iterable[dict[str, Any]],
    created_after: date,
) -> list[dict[str, Any]]:
    """Keep only pages whose API creation date is strictly after the given day."""
    matching_pages: list[dict[str, Any]] = []
    for page in pages:
        created_at = str(page.get("createdAt") or "")
        try:
            created_on = date.fromisoformat(created_at[:10])
        except ValueError:
            continue
        if created_on > created_after:
            matching_pages.append(page)
    return matching_pages


def find_matching_pages(
    pages: Iterable[dict[str, Any]],
    slug_or_title: str,
    minimum_matching_terms: int = 3,
) -> tuple[str, list[dict[str, Any]]]:
    """Rank pages with sufficiently many meaningful matching title terms."""
    normalized_query = normalize_query(slug_or_title)
    terms = query_terms(normalized_query)
    if not terms:
        raise ValueError("The search query must contain at least one meaningful term.")
    if minimum_matching_terms < 1:
        raise ValueError("minimum_matching_terms must be at least 1.")
    required_matches = min(minimum_matching_terms, len(terms))

    matches: list[dict[str, Any]] = []
    for page in pages:
        title = str(page.get("title") or "")
        score, matching_terms = _title_score(title, normalized_query, terms)
        if matching_terms < required_matches:
            continue

        links = page.get("_links") or {}
        webui = str(links.get("webui") or "")
        matches.append(
            {
                "id": str(page.get("id") or ""),
                "title": title,
                "status": str(page.get("status") or ""),
                "space_id": str(page.get("spaceId") or ""),
                "parent_id": str(page.get("parentId") or ""),
                "created_at": str(page.get("createdAt") or ""),
                "modified_at": str((page.get("version") or {}).get("createdAt") or ""),
                "url": _absolute_url(webui) if webui else "",
                "matching_terms": matching_terms,
                "score": score,
            }
        )

    matches.sort(
        key=lambda page: (
            -int(page["score"]),
            -int(page["matching_terms"]),
            page["title"].casefold(),
        )
    )
    return normalized_query, matches


def print_results(
    normalized_query: str,
    matches: list[dict[str, Any]],
    scanned_count: int,
    created_after: date,
) -> None:
    print(
        f"\nSuche nach '{normalized_query}' in archivierten und geloeschten "
        f"Seiten, erstellt nach {created_after.isoformat()} "
        f"({scanned_count} Seiten durchsucht):\n"
    )
    if not matches:
        print("Keine passenden Seiten gefunden.")
        print("Hinweis: Endgueltig aus dem Papierkorb entfernte Seiten sind nicht durchsuchbar.")
        return

    for page in matches:
        print(
            f"[{page['id']}] {page['title']} "
            f"(Status: {page['status']}, Treffer: {page['matching_terms']})"
        )
        if page["space_id"]:
            print(f"  Space-ID: {page['space_id']}")
        if page["created_at"]:
            print(f"  Erstellt: {page['created_at']}")
        if page["modified_at"]:
            print(f"  Letzte Version: {page['modified_at']}")
        if page["url"]:
            print(f"  URL: {page['url']}")
        print()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Search archived, trashed, and deleted Confluence pages by title."
    )
    parser.add_argument(
        "--query",
        "--slug",
        dest="query",
        required=True,
        help="Former Confluence URL slug, full page title, or title fragment.",
    )
    parser.add_argument(
        "--status",
        action="append",
        choices=DEFAULT_STATUSES,
        help="Status to search; can be passed more than once. Defaults to all.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of matching pages to print and save (default: 25).",
    )
    parser.add_argument(
        "--created-after",
        type=parse_date,
        default=DEFAULT_CREATED_AFTER,
        help=(
            "Only include pages created strictly after this date (YYYY-MM-DD; "
            "default: 2026-07-01)."
        ),
    )
    parser.add_argument(
        "--minimum-matching-terms",
        type=int,
        default=3,
        help="Required matching title terms (default: 3).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        choices=range(1, 251),
        metavar="{1..250}",
        help="Confluence pages fetched per API call (default: 100).",
    )
    parser.add_argument("-o", "--output", help="Save results as JSON to this file.")
    args = parser.parse_args()

    statuses = tuple(args.status or DEFAULT_STATUSES)
    pages = list_pages_with_statuses(statuses, args.page_size)
    dated_pages = filter_pages_created_after(pages, args.created_after)
    normalized_query, matches = find_matching_pages(
        dated_pages,
        args.query,
        args.minimum_matching_terms,
    )
    limited_matches = matches[: args.limit]
    print_results(normalized_query, limited_matches, len(dated_pages), args.created_after)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "query": args.query,
                    "normalized_query": normalized_query,
                    "statuses": statuses,
                    "created_after": args.created_after.isoformat(),
                    "retrieved_count": len(pages),
                    "scanned_count": len(dated_pages),
                    "minimum_matching_terms": args.minimum_matching_terms,
                    "count": len(limited_matches),
                    "results": limited_matches,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Gespeichert: {len(limited_matches)} Ergebnisse -> {output_path}")


if __name__ == "__main__":
    main()
