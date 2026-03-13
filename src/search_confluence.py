"""Search Confluence pages via CQL.

Usage:
    py src/search_confluence.py --query "process documentation"
    py src/search_confluence.py --query "onboarding" --limit 5
    py src/search_confluence.py --query "release brief" -o cache/confluence_results.json
"""

import argparse
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from read_confluence_page import _get_auth, CONFLUENCE_BASE_URL


def search_confluence(query: str, limit: int = 5) -> list[dict]:
    user, token = _get_auth()
    cql = f'type = "page" AND text ~ "{query}" ORDER BY lastModified DESC'
    url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/search"
    params = {"cql": cql, "limit": limit, "expand": "space,excerpt"}
    headers = {"Accept": "application/json"}
    resp = requests.get(url, headers=headers, auth=(user, token), params=params)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict] = []
    for item in data.get("results") or []:
        page_id = item.get("id") or ""
        title = item.get("title") or ""
        space_name = ((item.get("space") or {}).get("name")) or ""
        excerpt = (item.get("excerpt") or "").replace("\n", " ")
        webui = (item.get("_links") or {}).get("webui") or ""
        page_url = f"{CONFLUENCE_BASE_URL}/wiki{webui}" if webui else ""
        results.append({
            "id": page_id,
            "title": title,
            "space": space_name,
            "url": page_url,
            "excerpt": excerpt,
        })
    return results


def print_results(results: list[dict], query: str) -> None:
    if not results:
        print(f"Keine Confluence-Seiten gefunden fuer: '{query}'")
        return
    print(f"\nConfluence-Ergebnisse fuer '{query}' ({len(results)} Seiten):\n")
    for r in results:
        print(f"[{r['id']}] {r['title']} ({r['space']})")
        print(f"  URL: {r['url']}")
        if r["excerpt"]:
            print(f"  Excerpt: {r['excerpt'][:200]}")
        print()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Search Confluence pages via CQL")
    parser.add_argument("--query", required=True, help="Search query / keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")
    parser.add_argument("-o", "--output", help="Save results as JSON to this file")
    args = parser.parse_args()

    results = search_confluence(args.query, args.limit)
    print_results(results, args.query)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"query": args.query, "count": len(results), "results": results}, fh, ensure_ascii=False, indent=2)
        print(f"Gespeichert: {len(results)} Ergebnisse -> {args.output}")


if __name__ == "__main__":
    main()
