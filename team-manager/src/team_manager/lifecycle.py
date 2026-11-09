"""Auftragslebenszyklus als reine Tabelle ohne I/O.

Ein Übergang ist nur erlaubt, wenn (von, nach, Akteur) in ALLOWED steht.
Akteure:
  agent    - der Agent selbst über MCP-Werkzeuge
  hook     - Claude-Code-Hooks (Start, Stop, Fehler)
  user     - Benutzeraktion im Cockpit
  watchdog - zeitgesteuerte Überwachung im Service
"""

from __future__ import annotations

from .errors import InvalidTransition

STATUSES = (
    "REGISTERED",
    "IN_PROGRESS",
    "BLOCKED",
    "REVIEW_REQUIRED",
    "DONE",
    "FAILED",
    "CANCELLED",
)
ACTIVE_STATUSES = ("REGISTERED", "IN_PROGRESS", "BLOCKED")
TERMINAL_STATUSES = ("DONE", "FAILED", "CANCELLED")
ACTORS = ("agent", "hook", "user", "watchdog")

_RULES: dict[tuple[str, str], tuple[str, ...]] = {
    ("REGISTERED", "IN_PROGRESS"): ("hook",),
    ("REGISTERED", "FAILED"): ("hook", "watchdog", "user"),
    ("REGISTERED", "CANCELLED"): ("user",),
    ("IN_PROGRESS", "BLOCKED"): ("agent",),
    ("IN_PROGRESS", "REVIEW_REQUIRED"): ("agent", "hook"),
    ("IN_PROGRESS", "FAILED"): ("hook", "watchdog", "user"),
    ("IN_PROGRESS", "CANCELLED"): ("user",),
    ("BLOCKED", "IN_PROGRESS"): ("agent", "user"),
    ("BLOCKED", "REVIEW_REQUIRED"): ("agent",),
    ("BLOCKED", "FAILED"): ("hook", "watchdog", "user"),
    ("BLOCKED", "CANCELLED"): ("user",),
    # Review: ausschließlich der Benutzer entscheidet.
    ("REVIEW_REQUIRED", "DONE"): ("user",),
    ("REVIEW_REQUIRED", "FAILED"): ("user",),
}

ALLOWED: frozenset[tuple[str, str, str]] = frozenset(
    (src, dst, actor) for (src, dst), actors in _RULES.items() for actor in actors
)


def check_transition(src: str, dst: str, actor: str) -> None:
    """Wirft InvalidTransition, wenn der Übergang für diesen Akteur nicht zulässig ist."""
    if src not in STATUSES or dst not in STATUSES:
        raise InvalidTransition(f"Unbekannter Status: {src!r} -> {dst!r}.")
    if (src, dst, actor) not in ALLOWED:
        raise InvalidTransition(
            f"Übergang {src} -> {dst} ist für '{actor}' nicht zulässig.",
            details={"from": src, "to": dst, "actor": actor},
        )
