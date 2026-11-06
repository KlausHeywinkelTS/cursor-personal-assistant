from __future__ import annotations

import unittest

import find_invalid_jql_automations as scan


class NeutralizeSmartValuesTest(unittest.TestCase):
    def test_unquoted_smart_value_gets_quoted_placeholder(self) -> None:
        query, found = scan.neutralize_smart_values("parent = {{issue.key}}")
        self.assertTrue(found)
        self.assertEqual(query, f'parent = "{scan.PLACEHOLDER}"')

    def test_quoted_smart_value_keeps_surrounding_quotes(self) -> None:
        query, found = scan.neutralize_smart_values('labels = "jsm-{{issue.key}}*"')
        self.assertTrue(found)
        self.assertEqual(query, f'labels = "jsm-{scan.PLACEHOLDER}*"')

    def test_smart_value_inside_function_call(self) -> None:
        query, _ = scan.neutralize_smart_values(
            'issue in linkedIssues({{issue.key}}, "clones")'
        )
        self.assertEqual(
            query, f'issue in linkedIssues("{scan.PLACEHOLDER}", "clones")'
        )

    def test_smart_value_with_inner_quotes_does_not_break_quote_state(self) -> None:
        query, _ = scan.neutralize_smart_values(
            'a = {{x.join(",")}} AND b = "y"'
        )
        self.assertEqual(query, f'a = "{scan.PLACEHOLDER}" AND b = "y"')

    def test_plain_jql_is_unchanged(self) -> None:
        jql = 'project = PROPS AND status in ("Done", Rejected)'
        self.assertEqual(scan.neutralize_smart_values(jql), (jql, False))


class ExtractJqlTest(unittest.TestCase):
    def test_finds_all_known_locations(self) -> None:
        rule = {
            "trigger": {
                "type": "jira.jql.scheduled",
                "value": {"jql": "project = A", "executionMode": "jql"},
            },
            "components": [
                {"type": "jira.jql.condition", "value": "issuetype = Bug"},
                {
                    "type": "jira.issues.related.condition",
                    "value": {"compareJql": "status = Done", "relatedJql": ""},
                },
                {
                    "type": "jira.issue.related",
                    "value": {"relatedType": "jql", "jql": "parent = {{issue.key}}"},
                },
                {
                    "value": {
                        "name": {"type": "FREE", "value": "lookupIssues"},
                        "type": "JQL",
                        "query": {"type": "SMART", "value": "key = X-1"},
                    }
                },
            ],
        }
        found = {reference.jql for reference in scan.extract_jql(rule)}
        self.assertEqual(
            found,
            {
                "project = A",
                "issuetype = Bug",
                "status = Done",
                "parent = {{issue.key}}",
                "key = X-1",
            },
        )

    def test_ignores_empty_jql_and_unrelated_text(self) -> None:
        rule = {"components": [{"type": "x", "value": {"jql": "  "}}, {"value": "a = b"}]}
        self.assertEqual(scan.extract_jql(rule), [])


class ErrorClassificationTest(unittest.TestCase):
    def test_structural_errors_from_the_announcement(self) -> None:
        for error in (
            "A value provided by the function 'openSprints' is invalid for the field 'status'.",
            "History searches do not support the  'sprint' field.",
            "Operator 'is' does not support searching for non-empty values for field 'project'.",
            "Error in JQL Query: Expecting either a value, list or function before the end of the query.",
        ):
            finding = scan.JqlFinding(
                scan.JqlReference("$", "t", "q"), (error,), False
            )
            self.assertTrue(finding.structural_errors, error)

    def test_unknown_field_is_a_review_case_because_it_may_be_hidden(self) -> None:
        finding = scan.JqlFinding(
            scan.JqlReference("$", "t", "q"),
            ("Field 'foo' does not exist or you do not have permission to view it.",),
            False,
        )
        self.assertTrue(finding.value_errors)
        self.assertFalse(finding.structural_errors)

    def test_value_errors_are_separated(self) -> None:
        finding = scan.JqlFinding(
            scan.JqlReference("$", "t", "q"),
            (
                "The value 'X' does not exist for the field 'project'.",
                "Operator 'is' does not support searching for non-empty values for field 'project'.",
            ),
            False,
        )
        self.assertEqual(len(finding.value_errors), 1)
        self.assertEqual(len(finding.structural_errors), 1)


if __name__ == "__main__":
    unittest.main()
