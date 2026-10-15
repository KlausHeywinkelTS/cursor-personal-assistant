from __future__ import annotations

import unittest
from pathlib import Path

import import_si_epics_from_excel as imp

XLSX = Path(__file__).resolve().parent.parent / "tmp" / "REQ_DEL_RAID_JIRA.xlsx"


def _row(sheet: str = "REQ", **overrides) -> imp.EpicRow:
    values = dict(
        spec=imp.SHEETS[sheet], excel_row=2, item_id="X-R01", initiative="SI-1", summary="X-R01 Name",
        description="Beschreibung", notes="", name_value="Name", workstream="Rollout", priority="High",
        status="Open", assignee_raw="", related_ids=[],
    )
    values.update(overrides)
    return imp.EpicRow(**values)


class ParsingTests(unittest.TestCase):
    def test_split_ids_accepts_semicolon_and_comma(self) -> None:
        self.assertEqual(imp.split_ids("A-R01; A-R02,A-R03"), ["A-R01", "A-R02", "A-R03"])

    def test_first_person_takes_first_entry_only(self) -> None:
        self.assertEqual(imp.first_person("Christoph Terwey / BAU Owner TBC"), "Christoph Terwey")
        self.assertEqual(imp.first_person("Project 3 Lead"), "Project 3 Lead")

    def test_clean_treats_dash_placeholders_as_empty(self) -> None:
        self.assertEqual(imp.clean("—"), "")
        self.assertEqual(imp.clean(None), "")
        self.assertEqual(imp.clean("  x "), "x")


class PayloadTests(unittest.TestCase):
    def test_req_description_has_notes_second_then_requirement_and_workstream(self) -> None:
        doc = imp.build_description(_row(notes="Wichtig"))
        labels = [p["content"][0]["text"] for p in doc["content"]]
        self.assertEqual(labels, ["Beschreibung", "Notes: ", "Requirement: ", "Workstream: "])

    def test_del_description_uses_deliverable_label(self) -> None:
        doc = imp.build_description(_row("DEL"))
        self.assertEqual(doc["content"][1]["content"][0]["text"], "Deliverable: ")

    def test_fields_contain_fixed_values_and_parent(self) -> None:
        fields = imp.build_fields(_row("DEL"), reporter_id="rep", assignee_id=None)
        self.assertEqual(fields["components"], [{"name": "Project Deliverable"}])
        self.assertEqual(fields["labels"], ["Internal_AI_Environment"])
        self.assertEqual(fields["reporter"], {"accountId": "rep"})
        self.assertEqual(fields["parent"], {"key": "SI-1"})
        self.assertNotIn("assignee", fields)

    def test_status_and_priority_mapping(self) -> None:
        self.assertEqual(imp.target_status(_row(status="Open")), "ToDo")
        self.assertEqual(imp.target_status(_row(status="In Progress")), "In Progress")
        self.assertEqual(imp.jira_priority(_row(priority="Medium")), "Medium")
        with self.assertRaises(ValueError):
            imp.target_status(_row(status="Weird"))

    def test_link_payload_uses_relates_type(self) -> None:
        payload = imp.build_link_payload("SI-2", "SI-1")
        self.assertEqual(payload["type"], {"name": "Relates"})
        self.assertEqual(payload["outwardIssue"], {"key": "SI-2"})


@unittest.skipUnless(XLSX.is_file(), "Excel-Datei nicht vorhanden")
class ExcelTests(unittest.TestCase):
    def test_reads_all_rows_and_resolves_all_related_requirements(self) -> None:
        req = imp.read_rows(XLSX, imp.SHEETS["REQ"])
        dele = imp.read_rows(XLSX, imp.SHEETS["DEL"])
        self.assertEqual((len(req), len(dele)), (68, 54))
        self.assertEqual(req[0].summary, "ROL-R01 Rollout Strategy & Wave Plan")
        req_ids = {r.item_id for r in req}
        for row in dele:
            self.assertTrue(row.related_ids, row.item_id)
            self.assertLessEqual(set(row.related_ids), req_ids, row.item_id)


if __name__ == "__main__":
    unittest.main()
