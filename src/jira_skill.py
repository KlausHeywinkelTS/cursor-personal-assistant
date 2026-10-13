"""Shared access to the user-level Jira skill's public Python API.

The Jira skill (``~/.claude/skills/jira/src``) exposes ``jira_client`` as its
public API. Scripts in this repo import from here instead of loading CLI
modules or underscore-prefixed helpers from the skill.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

_API_MODULE = "jira_client"


def _candidate_jira_helper_dirs() -> list[Path]:
    """Return likely locations for the Jira skill's src directory."""
    candidates: list[Path] = [Path(__file__).resolve().parent]

    for env_name in ("CURSOR_JIRA_SKILL_SRC", "JIRA_SKILL_SRC"):
        configured = os.getenv(env_name)
        if configured:
            candidates.append(Path(configured).expanduser())

    home = Path.home()
    candidates.extend(
        [
            home / ".claude" / "skills" / "jira" / "src",
            home / ".cursor" / "skills" / "jira" / "src",
            home / "Dev" / "props-cursor-plugins" / "skills" / "jira" / "src",
        ]
    )

    plugin_cache = home / ".cursor" / "plugins" / "cache"
    if plugin_cache.exists():
        candidates.extend(plugin_cache.glob("**/skills/jira/src"))

    return candidates


def _find_jira_skill_dir() -> Path:
    candidates = _candidate_jira_helper_dirs()
    for candidate in candidates:
        if (candidate / f"{_API_MODULE}.py").is_file():
            return candidate

    searched = "\n".join(f"- {path}" for path in candidates)
    raise ModuleNotFoundError(
        f"Could not find {_API_MODULE}.py. Install the Jira user skill or set "
        f"CURSOR_JIRA_SKILL_SRC to its src directory.\nSearched:\n{searched}"
    )


def _load_jira_client() -> Any:
    skill_dir = str(_find_jira_skill_dir())
    # Appended, so modules in this repo's src/ keep precedence. jira_client
    # imports its siblings (atlassian_core, adf) by plain name.
    if skill_dir not in sys.path:
        sys.path.append(skill_dir)
    return importlib.import_module(_API_MODULE)


_client = _load_jira_client()

JIRA_BASE_URL: str = _client.JIRA_BASE_URL
search = _client.search


def jira_get_metadata(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET a Jira REST path that carries no personal data (e.g. ``/rest/api/3/field``).

    The skill's client only supports endpoints with a pseudonymization rule, so
    this goes around it. Use it for schema and configuration endpoints only,
    never for issues, comments or user data.
    """
    import requests

    atlassian_core = importlib.import_module("atlassian_core")
    user, token = atlassian_core.get_auth()
    response = requests.get(
        f"{JIRA_BASE_URL}{path}",
        headers={"Accept": "application/json"},
        auth=(user, token),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
