from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import update_daily_journal as journal


class TopScoredTasksSectionTests(unittest.TestCase):
    def test_formats_three_ranked_tasks_as_compact_list_items(self) -> None:
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
        self.assertIn("- PROPS-1 - Wichtigste Aufgabe (Wert für das Epic)", section)
        self.assertIn("- PROPS-3 - Dritte Aufgabe", section)
        self.assertNotIn("PROPS-4", section)
        self.assertNotIn("[PROPS-1]", section)
        self.assertNotIn("Punkte", section)

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
                patch.object(journal, "_collect_long_running_tickets", return_value=[]),
            ):
                path = journal.update_daily_journal(date(2026, 7, 31), temporary_directory)

            content = Path(path).read_text(encoding="utf-8")

        self.assertLess(content.index("## Termine"), content.index("## Top 3 scored Jira Tasks"))
        self.assertLess(
            content.index("## Top 3 scored Jira Tasks"),
            content.index("## Reflektion: Mein Tag heute"),
        )
        self.assertIn("- PROPS-1 - Wichtigste Aufgabe", content)

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
        self.assertIn("- PROPS-1 - Wichtigste Aufgabe", content)
        self.assertLess(content.index("## Termine"), content.index("## Top 3 scored Jira Tasks"))
        self.assertLess(
            content.index("## Top 3 scored Jira Tasks"),
            content.index("## Reflektion: Mein Tag heute"),
        )


class WeekdayManualGoalHeaderTests(unittest.TestCase):
    def test_monday_returns_wochenziele_header(self) -> None:
        self.assertEqual(
            journal._weekday_manual_goal_header(date(2026, 8, 3)),
            "## Wochenziele",
        )

    def test_friday_returns_erreichung_wochenziele_header(self) -> None:
        self.assertEqual(
            journal._weekday_manual_goal_header(date(2026, 8, 7)),
            "## Erreichung Wochenziele",
        )

    def test_other_weekday_returns_none(self) -> None:
        self.assertIsNone(journal._weekday_manual_goal_header(date(2026, 8, 5)))


class LongRunningTicketsSectionTests(unittest.TestCase):
    def test_formats_empty_list(self) -> None:
        section = journal._format_long_running_tickets_section([])

        self.assertEqual(
            "## Langlaufende Tasks\n\n- Keine Langläufer.\n",
            section,
        )

    def test_formats_tickets_with_entries(self) -> None:
        section = journal._format_long_running_tickets_section(
            [
                journal.InProgressTicket(key="KH-1", summary="Langläufer eins"),
                journal.InProgressTicket(key="KH-2", summary="Langläufer zwei"),
            ]
        )

        self.assertIn("## Langlaufende Tasks\n\n", section)
        self.assertIn(f"- [KH-1]({journal.JIRA_BASE_URL}/browse/KH-1) - Langläufer eins", section)
        self.assertIn(f"- [KH-2]({journal.JIRA_BASE_URL}/browse/KH-2) - Langläufer zwei", section)


class SectionOrderAndReflectionTests(unittest.TestCase):
    def test_section_order_includes_long_running_and_reflection(self) -> None:
        ranked_tasks = [
            {
                "key": "PROPS-1",
                "summary": "Wichtigste Aufgabe",
                "status": "In Progress",
                "score": 150,
                "reasons": [],
            }
        ]
        long_running = [journal.InProgressTicket(key="KH-1", summary="Langläufer")]
        with TemporaryDirectory() as temporary_directory:
            with (
                patch.object(journal, "_collect_appointments", return_value=([], True)),
                patch.object(journal, "get_ranked_issues", return_value=ranked_tasks),
                patch.object(journal, "_collect_long_running_tickets", return_value=long_running),
            ):
                # 2026-08-05 is a Wednesday: no weekly-goal section expected.
                path = journal.update_daily_journal(date(2026, 8, 5), temporary_directory)

            content = Path(path).read_text(encoding="utf-8")

        self.assertNotIn("## Wochenziele", content)
        self.assertNotIn("## Erreichung Wochenziele", content)
        self.assertLess(
            content.index("## Top 3 scored Jira Tasks"),
            content.index("## Langlaufende Tasks"),
        )
        self.assertLess(
            content.index("## Langlaufende Tasks"),
            content.index("## Reflektion: Mein Tag heute"),
        )
        self.assertNotIn("## Generierter Inhalt (Jira)", content)
        self.assertIn(f"- [KH-1]({journal.JIRA_BASE_URL}/browse/KH-1) - Langläufer", content)
        self.assertIn("Was ich heute gemacht habe", content)

    def test_rerun_preserves_existing_weekly_goal_content(self) -> None:
        def _run(day: date, temporary_directory: str) -> str:
            with (
                patch.object(journal, "_collect_appointments", return_value=([], True)),
                patch.object(journal, "get_ranked_issues", return_value=[]),
                patch.object(journal, "_collect_long_running_tickets", return_value=[]),
            ):
                return journal.update_daily_journal(day, temporary_directory)

        # 2026-08-03 is a Monday: expect "## Wochenziele".
        monday = date(2026, 8, 3)
        with TemporaryDirectory() as temporary_directory:
            path = _run(monday, temporary_directory)

            existing_text = Path(path).read_text(encoding="utf-8")
            filled_text = existing_text.replace(
                "## Wochenziele\n\n<!-- Optional durch Nutzer gepflegt -->",
                "## Wochenziele\n\n- Ziel A erreichen",
            )
            Path(path).write_text(filled_text, encoding="utf-8", newline="\n")

            _run(monday, temporary_directory)

            content = Path(path).read_text(encoding="utf-8")

        self.assertIn("- Ziel A erreichen", content)


if __name__ == "__main__":
    unittest.main()
