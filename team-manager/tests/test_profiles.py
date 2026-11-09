from team_manager.profiles import load_profiles, parse_frontmatter
from tests.conftest import write_profiles


def test_only_team_members_are_loaded(tmp_path):
    write_profiles(tmp_path)
    profiles = {p.name: p for p in load_profiles(tmp_path)}
    assert set(profiles) == {"karla", "yasmin", "lotta"}
    assert profiles["karla"].competencies == ["analyse"]
    assert profiles["karla"].display_name == "Karla"


def test_missing_directory_yields_no_agents(tmp_path):
    assert load_profiles(tmp_path / "gibt-es-nicht") == []


def test_broken_frontmatter_is_ignored(tmp_path):
    (tmp_path / "kaputt.md").write_text("---\nname: [unclosed\n---\n", encoding="utf-8")
    (tmp_path / "ohne.md").write_text("kein frontmatter", encoding="utf-8")
    assert load_profiles(tmp_path) == []


def test_bom_and_string_competency(tmp_path):
    (tmp_path / "a.md").write_text(
        "﻿---\nname: Anna\nteam_member: true\ncompetencies: schreiben\n---\n", encoding="utf-8"
    )
    [profile] = load_profiles(tmp_path)
    assert profile.name == "anna" and profile.competencies == ["schreiben"]


def test_parse_frontmatter_requires_closing_marker():
    assert parse_frontmatter("---\nname: x\n") == {}
