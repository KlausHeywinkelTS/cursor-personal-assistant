from __future__ import annotations

import json
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import prioritize_my_jira_issues as ranking


def issue(
    key: str,
    *,
    summary: str = "Test issue",
    status: str = "Backlog",
    status_category: str = "",
    priority: str = "",
    issue_type: str = "Task",
    parent_key: str = "",
    epic_link: str = "",
    remind_date: str = "",
    updated: str = "",
) -> dict:
    status_field: dict = {"name": status}
    if status_category:
        status_field["statusCategory"] = {"key": status_category}
    fields: dict = {
        "summary": summary,
        "status": status_field,
        "priority": {"name": priority},
        "issuetype": {"name": issue_type},
        "updated": updated,
        "customfield_10246": remind_date,
        "customfield_10014": epic_link,
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}
    return {"key": key, "fields": fields}


class ScoreIssueTests(unittest.TestCase):
    TODAY = date(2026, 7, 31)

    def test_combines_epic_priority_and_in_progress(self) -> None:
        raw = issue(
            "PROPS-1",
            status="In Progress",
            priority="High",
            parent_key="PROPS-EPIC",
        )

        result = ranking.score_issue(
            raw,
            {"PROPS-EPIC"},
            {"PROPS-EPIC": {"PROPS-1"}},
            self.TODAY,
        )

        self.assertEqual(150, result.score)
        self.assertEqual(
            (
                "+50 letzter offener direkter Task im Epic PROPS-EPIC",
                "+50 Priorität High",
                "+50 Status In Progress",
            ),
            result.reasons,
        )

    def test_appends_parent_epic_summary_to_task_summary(self) -> None:
        result = ranking.score_issue(
            issue(
                "PROPS-1",
                summary="Task summary",
                parent_key="PROPS-EPIC",
            ),
            {"PROPS-EPIC"},
            {},
            self.TODAY,
            {"PROPS-EPIC": "Epic summary"},
        )

        self.assertEqual("Task summary (Epic summary)", result.summary)

    def test_priority_points(self) -> None:
        for priority, expected_score in {
            "Showstopper": 100,
            "High": 50,
            "Medium": 20,
            "Low": 5,
            "Unprioritized": 0,
        }.items():
            with self.subTest(priority=priority):
                result = ranking.score_issue(
                    issue("PROPS-1", priority=priority),
                    set(),
                    {},
                    self.TODAY,
                )
                self.assertEqual(expected_score, result.score)

    def test_to_be_refined_is_deducted(self) -> None:
        result = ranking.score_issue(
            issue("PROPS-1", status="To be refined"),
            set(),
            {},
            self.TODAY,
        )

        self.assertEqual(-50, result.score)
        self.assertEqual(("-50 Status To be refined",), result.reasons)

    def test_blocked_and_waiting_remind_date_thresholds(self) -> None:
        cases = [
            ("Blocked", self.TODAY - timedelta(days=1), 20),
            ("Waiting", self.TODAY, 20),
            ("Blocked", self.TODAY + timedelta(days=1), -100),
        ]
        for status, remind_day, expected_score in cases:
            with self.subTest(status=status, remind_day=remind_day):
                result = ranking.score_issue(
                    issue(
                        "PROPS-1",
                        status=status,
                        remind_date=remind_day.isoformat(),
                    ),
                    set(),
                    {},
                    self.TODAY,
                )
                self.assertEqual(expected_score, result.score)

    def test_todo_inactivity_starts_at_four_full_weeks(self) -> None:
        cases = [
            (27, 20),
            (28, 40),
            (35, 60),
        ]
        for inactive_days, expected_score in cases:
            with self.subTest(inactive_days=inactive_days):
                result = ranking.score_issue(
                    issue(
                        "PROPS-1",
                        status="ToDo",
                        updated=(self.TODAY - timedelta(days=inactive_days)).isoformat(),
                    ),
                    set(),
                    {},
                    self.TODAY,
                )
                self.assertEqual(expected_score, result.score)


class RankingTests(unittest.TestCase):
    TODAY = date(2026, 7, 31)

    def test_excludes_done_rejected_and_epics_then_sorts_by_score_and_key(self) -> None:
        raw_issues = [
            issue("PROPS-2", priority="Medium"),
            issue("PROPS-1", priority="Medium"),
            issue("PROPS-3", status="Done", priority="Showstopper"),
            issue("PROPS-4", status="Rejected", priority="Showstopper"),
            issue("PROPS-5", issue_type="Epic", priority="Showstopper"),
            issue(
                "PROPS-6",
                status="Closed",
                status_category="done",
                priority="Showstopper",
            ),
        ]

        ranked = ranking.rank_issues(raw_issues, set(), {}, self.TODAY)

        self.assertEqual(["PROPS-1", "PROPS-2"], [item.key for item in ranked])
        self.assertEqual([20, 20], [item.score for item in ranked])

    def test_parent_and_classic_epic_link_children_are_combined(self) -> None:
        parent_child = issue("PROPS-1", parent_key="PROPS-EPIC")
        classic_child = issue("PROPS-2", epic_link="PROPS-EPIC")
        done_child = issue(
            "PROPS-3",
            status="Done",
            parent_key="PROPS-EPIC",
        )
        subtask = issue(
            "PROPS-4",
            issue_type="Sub-task",
            parent_key="PROPS-EPIC",
        )

        with patch.object(
            ranking,
            "_jira_search",
            side_effect=[
                [parent_child, done_child, subtask],
                [classic_child],
            ],
        ) as search:
            children = ranking.fetch_open_direct_epic_children({"PROPS-EPIC"}, 100)

        self.assertEqual({"PROPS-EPIC": {"PROPS-1", "PROPS-2"}}, dict(children))
        self.assertIn("parent IN", search.call_args_list[0].kwargs["jql"])
        self.assertIn("cf[10014] IN", search.call_args_list[1].kwargs["jql"])

    def test_format_ranking_includes_score_explanations(self) -> None:
        output = ranking.format_ranking(
            [
                ranking.RankedIssue(
                    key="PROPS-1",
                    summary="Priorisierte Aufgabe",
                    status="In Progress",
                    score=50,
                    reasons=("+50 Status In Progress",),
                )
            ]
        )

        self.assertIn("PROPS-1 | Priorisierte Aufgabe | In Progress | 50 Punkte", output)
        self.assertIn("  - +50 Status In Progress", output)

    def test_get_ranked_issues_returns_a_json_compatible_array(self) -> None:
        ranked_issue = ranking.RankedIssue(
            key="PROPS-1",
            summary="Priorisierte Aufgabe",
            status="In Progress",
            score=50,
            reasons=("+50 Status In Progress",),
        )

        with patch.object(ranking, "fetch_ranked_issues", return_value=[ranked_issue]):
            result = ranking.get_ranked_issues()
            serialized_result = ranking.get_ranked_issues_json()

        self.assertEqual(
            [
                {
                    "key": "PROPS-1",
                    "summary": "Priorisierte Aufgabe",
                    "status": "In Progress",
                    "score": 50,
                    "reasons": ["+50 Status In Progress"],
                }
            ],
            result,
        )
        self.assertEqual(result, json.loads(serialized_result))


if __name__ == "__main__":
    unittest.main()
