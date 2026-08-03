from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import Mock, patch

import search_archived_confluence_pages as search


class QueryNormalizationTests(unittest.TestCase):
    def test_decodes_slug_and_drops_stop_words(self) -> None:
        normalized = search.normalize_query(
            "SW+Capitalization+Technical+Solutions+for+Expense+Tracking"
        )

        self.assertEqual(
            normalized,
            "SW Capitalization Technical Solutions for Expense Tracking",
        )
        self.assertEqual(
            search.query_terms(normalized),
            ["sw", "capitalization", "technical", "solutions", "expense", "tracking"],
        )


class PageMatchingTests(unittest.TestCase):
    def test_ranks_exact_title_above_partial_title_matches(self) -> None:
        pages = [
            {
                "id": "3",
                "title": "Expense Tracking: Technical Solutions",
                "status": "trashed",
                "spaceId": "42",
            },
            {
                "id": "2",
                "title": "SW Capitalization Technical Solutions for Expense Tracking",
                "status": "archived",
                "spaceId": "42",
            },
            {
                "id": "1",
                "title": "Unrelated Page",
                "status": "deleted",
            },
            {
                "id": "4",
                "title": "Technical Solutions",
                "status": "archived",
            },
        ]

        normalized, matches = search.find_matching_pages(
            pages,
            "SW+Capitalization+Technical+Solutions+for+Expense+Tracking",
        )

        self.assertEqual(
            normalized,
            "SW Capitalization Technical Solutions for Expense Tracking",
        )
        self.assertEqual([match["id"] for match in matches], ["2", "3"])
        self.assertEqual(matches[0]["score"], 1_000)
        self.assertEqual(matches[1]["matching_terms"], 4)


class CreationDateFilterTests(unittest.TestCase):
    def test_keeps_only_pages_created_strictly_after_cutoff(self) -> None:
        pages = [
            {"id": "1", "createdAt": "2026-07-01T10:00:00Z"},
            {"id": "2", "createdAt": "2026-07-02T10:00:00Z"},
            {"id": "3", "createdAt": "not-a-date"},
            {"id": "4"},
        ]

        filtered_pages = search.filter_pages_created_after(
            pages,
            date(2026, 7, 1),
        )

        self.assertEqual([page["id"] for page in filtered_pages], ["2"])


class PageListingTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {"ATLASSIAN_USER": "user@example.test", "ATLASSIAN_TOKEN": "token"},
        clear=True,
    )
    @patch.object(search.requests, "get")
    def test_reads_all_cursor_pages_and_removes_duplicates(self, get: Mock) -> None:
        first_response = Mock()
        first_response.json.return_value = {
            "results": [{"id": "1", "title": "First"}],
            "_links": {"next": "/wiki/api/v2/pages?cursor=next-page"},
        }
        first_response.links = {}

        second_response = Mock()
        second_response.json.return_value = {
            "results": [
                {"id": "1", "title": "First"},
                {"id": "2", "title": "Second"},
            ]
        }
        second_response.links = {}
        get.side_effect = [first_response, second_response]

        pages = search.list_pages_with_statuses(("archived", "trashed"), page_size=50)

        self.assertEqual([page["id"] for page in pages], ["1", "2"])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(
            get.call_args_list[0].kwargs["params"],
            [("limit", 50), ("status", "archived"), ("status", "trashed")],
        )
        self.assertIsNone(get.call_args_list[1].kwargs["params"])


if __name__ == "__main__":
    unittest.main()
