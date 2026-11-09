"""Agentenprofile (Claude-Code-Subagenten) als einzige Quelle für Namen, Beschreibung und Kompetenzen.

Ein Profil gehört zum Team, wenn sein Frontmatter `team_member: true` enthält.
Claude Code ignoriert unbekannte Frontmatter-Felder, die Dateien bleiben also kompatibel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger("team_manager.profiles")


@dataclass(frozen=True)
class AgentProfile:
    name: str
    display_name: str
    description: str
    competencies: list[str] = field(default_factory=list)
    path: str = ""


def parse_frontmatter(text: str) -> dict:
    text = text.removeprefix(chr(0xFEFF))  # UTF-8-BOM
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def load_profiles(agents_dir: Path) -> list[AgentProfile]:
    profiles: list[AgentProfile] = []
    if not agents_dir.is_dir():
        log.warning("agents_dir_missing", extra={"path": str(agents_dir)})
        return profiles
    for file in sorted(agents_dir.glob("*.md")):
        meta = parse_frontmatter(file.read_text(encoding="utf-8", errors="replace"))
        if meta.get("team_member") is not True:
            continue
        name = str(meta.get("name", "")).strip().lower()
        if not name:
            log.warning("profile_without_name", extra={"path": str(file)})
            continue
        competencies = meta.get("competencies") or []
        if isinstance(competencies, str):
            competencies = [competencies]
        profiles.append(
            AgentProfile(
                name=name,
                display_name=str(meta.get("display_name") or name.capitalize()),
                description=str(meta.get("description", "")).strip(),
                competencies=[str(c) for c in competencies],
                path=str(file),
            )
        )
    return profiles
