from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import update_daily_journal as journal


class TopScoredTasksSectionTests(unittest.TestCase):
    def test_formats_three_ranked_tasks_with_readable_details(self) -> None:
        section = journal._format_top_scored_jira_tasks_section(
            [
                {
                    "key": "PROPS-1",
                    "summary": "Wichtigste Aufgabe (Wert für das Epic)",
                    "status": "In Progress",
                    "score": 150,
                    "reasons": ["+100 Priorität Showstopper", "+50 Status In Progress"],
                },
                {
                    "key": "PROPS-2",
                    "summary": "Zweite Aufgabe",
                    "status": "Backlog",
                    "score": 50,
                    "reasons": ["+50 letzter offener direkter Task im Epic PROPS-10"],
                },
                {
                    "key": "PROPS-3",
                    "summary": "Dritte Aufgabe",
                    "status": "Waiting",
                    "score": 20,
                    "reasons": ["+20 Waiting mit fälligem Remind-Date (2026-07-31)"],
                },
                {
                    "key": "PROPS-4",
                    "summary": "Nicht in der Top 3",
                    "status": "Backlog",
                    "score": 0,
                    "reasons": [],
                },
            ]
        )

        self.assertIn("## Top 3 scored Jira Tasks\n\n", section)
        self.assertIn("### 1. [PROPS-1]", section)
        self.assertIn("### 3. [PROPS-3]", section)
        self.assertNotIn("PROPS-4", section)
        self.assertIn("**Status:** `In Progress`", section)
        self.assertIn("- +100 Priorität Showstopper", section)

    def test_formats_empty_ranking(self) -> None:
        section = journal._format_top_scored_jira_tasks_section([])

        self.assertEqual(
            "## Top 3 scored Jira Tasks\n\n"
            "- Keine offenen Jira-Tasks im Ranking gefunden.\n",
            section,
        )

    def test_places_top_scored_tasks_between_appointments_and_manual_content(self) -> None:
        ranked_tasks = [
            {
                "key": "PROPS-1",
                "summary": "Wichtigste Aufgabe",
                "status": "In Progress",
                "score": 150,
                "reasons": ["+50 Status In Progress"],
            }
        ]
        with TemporaryDirectory() as temporary_directory:
            with (
                patch.object(journal, "_collect_appointments", return_value=([], True)),
                patch.object(journal, "get_ranked_issues", return_value=ranked_tasks),
                patch.object(journal, "_collect_candidate_issues", return_value={}),
                patch.object(journal, "_collect_in_progress_tickets", return_value=[]),
                patch.object(journal, "_collect_new_tickets", return_value=[]),
                patch.object(journal, "_collect_issue_events", return_value=([], [], [])),
            ):
                path = journal.update_daily_journal(date(2026, 7, 31), temporary_directory)

            content = Path(path).read_text(encoding="utf-8")

        self.assertLess(content.index("## Termine"), content.index("## Top 3 scored Jira Tasks"))
        self.assertLess(
            content.index("## Top 3 scored Jira Tasks"),
            content.index("## Manueller Inhalt"),
        )
        self.assertIn("### 1. [PROPS-1]", content)

    def test_writes_top_scored_tasks_when_creating_ranked_stub(self) -> None:
        ranked_tasks = [
            {
                "key": "PROPS-1",
                "summary": "Wichtigste Aufgabe",
                "status": "In Progress",
                "score": 150,
                "reasons": ["+50 Status In Progress"],
            }
        ]
        with TemporaryDirectory() as temporary_directory:
            with (
                patch.object(journal, "_collect_appointments", return_value=([], True)),
                patch.object(journal, "get_ranked_issues", return_value=ranked_tasks),
            ):
                path = journal.write_journal_stub_with_ranking_if_missing(
                    date(2026, 8, 3),
                    temporary_directory,
                )

            content = Path(path).read_text(encoding="utf-8")

        self.assertIn("## Top 3 scored Jira Tasks", content)
        self.assertIn("### 1. [PROPS-1]", content)
        self.assertLess(content.index("## Termine"), content.index("## Top 3 scored Jira Tasks"))
        self.assertLess(
            content.index("## Top 3 scored Jira Tasks"),
            content.index("## Manueller Inhalt"),
        )


if __name__ == "__main__":
    unittest.main()
