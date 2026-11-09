from datetime import UTC, datetime, timedelta

import pytest

from team_manager.config import Settings
from team_manager.db import Database
from team_manager.events_bus import EventBus
from team_manager.notify import RecordingNotifier
from team_manager.profiles import AgentProfile
from team_manager.service import TaskService


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


# Testdaten, keine Produktivkonfiguration: die echten Profile liegen in agents/*.md
TEST_PROFILES = [
    AgentProfile("karla", "Karla", "Testagentin Karla", ["analyse"]),
    AgentProfile("yasmin", "Yasmin", "Testagentin Yasmin", ["recherche"]),
    AgentProfile("lotta", "Lotta", "Testagentin Lotta", ["dokumentation"]),
]


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "team.db")
    database.migrate()
    return database


@pytest.fixture
def settings(tmp_path):
    return Settings(
        home=tmp_path / "home",
        agents_dir=tmp_path / "agents",
        token="test-token",
        registered_timeout_s=120,
        orphan_timeout_s=900,
        session_end_grace_s=120,
    )


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def svc(db, settings, clock, notifier):
    service = TaskService(db, settings, notifier=notifier, bus=EventBus(), clock=clock)
    service.sync_agents(TEST_PROFILES)
    return service


PROFILE_TEMPLATE = """---
name: {name}
description: {desc}
tools: Read, Glob, Grep
disallowedTools: Agent
team_member: true
display_name: {display}
competencies: [{comp}]
---

Du bist {display}.
"""


def write_profiles(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for p in TEST_PROFILES:
        (directory / f"{p.name}.md").write_text(
            PROFILE_TEMPLATE.format(name=p.name, desc=p.description, display=p.display_name, comp=", ".join(p.competencies)),
            encoding="utf-8",
        )
    # Kein Teammitglied: darf nicht auftauchen
    (directory / "explore.md").write_text("---\nname: explore\ndescription: kein Team\n---\n", encoding="utf-8")


@pytest.fixture
def app_settings(tmp_path):
    agents = tmp_path / "agents"
    write_profiles(agents)
    return Settings(
        home=tmp_path / "home", agents_dir=agents, port=8765, token="test-token", notifications=False,
        bridge_wait_s=0.3, watchdog_interval_s=3600,
    )
