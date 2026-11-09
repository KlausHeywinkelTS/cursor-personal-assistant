"""Übergangsmatrix: jeder erlaubte und jeder verbotene Übergang wird geprüft."""

import itertools

import pytest

from team_manager.errors import ErrorCode, InvalidTransition
from team_manager.lifecycle import (
    ACTIVE_STATUSES,
    ALLOWED,
    ACTORS,
    STATUSES,
    TERMINAL_STATUSES,
    check_transition,
)


def test_status_sets_match_briefing():
    assert set(STATUSES) == {
        "REGISTERED", "IN_PROGRESS", "BLOCKED", "REVIEW_REQUIRED", "DONE", "FAILED", "CANCELLED",
    }
    assert set(ACTIVE_STATUSES) == {"REGISTERED", "IN_PROGRESS", "BLOCKED"}
    assert set(TERMINAL_STATUSES) == {"DONE", "FAILED", "CANCELLED"}


@pytest.mark.parametrize("src,dst,actor", sorted(ALLOWED))
def test_allowed_transitions_pass(src, dst, actor):
    check_transition(src, dst, actor)  # darf nicht werfen


_FORBIDDEN = [
    (s, d, a)
    for s, d, a in itertools.product(STATUSES, STATUSES, ACTORS)
    if (s, d, a) not in ALLOWED
]


@pytest.mark.parametrize("src,dst,actor", _FORBIDDEN)
def test_forbidden_transitions_raise(src, dst, actor):
    with pytest.raises(InvalidTransition) as exc:
        check_transition(src, dst, actor)
    assert exc.value.code == ErrorCode.INVALID_TRANSITION


@pytest.mark.parametrize("actor", [a for a in ACTORS if a != "user"])
def test_done_only_by_user(actor):
    with pytest.raises(InvalidTransition):
        check_transition("REVIEW_REQUIRED", "DONE", actor)


def test_user_can_mark_done():
    check_transition("REVIEW_REQUIRED", "DONE", "user")


@pytest.mark.parametrize("terminal", TERMINAL_STATUSES)
def test_terminal_states_have_no_exit(terminal):
    assert not [t for t in ALLOWED if t[0] == terminal]


def test_review_required_does_not_block_agent():
    assert "REVIEW_REQUIRED" not in ACTIVE_STATUSES


def test_unknown_status_rejected():
    with pytest.raises(InvalidTransition):
        check_transition("IN_PROGRESS", "NONSENSE", "agent")
