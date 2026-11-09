"""Test 2/3: Die Datenbank verhindert gleichzeitige Doppelreservierungen."""

import threading
from collections import Counter

from team_manager.errors import AgentBusy


def _race(callables):
    barrier = threading.Barrier(len(callables))
    outcomes: list = [None] * len(callables)

    def runner(i, fn):
        barrier.wait()
        try:
            outcomes[i] = ("ok", fn())
        except AgentBusy as exc:
            outcomes[i] = ("busy", exc)

    threads = [threading.Thread(target=runner, args=(i, fn)) for i, fn in enumerate(callables)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return outcomes


def test_20_parallel_start_task_calls_yield_exactly_one_winner(svc):
    outcomes = _race([lambda i=i: svc.start_task("karla", f"Auftrag {i}") for i in range(20)])
    assert Counter(kind for kind, _ in outcomes) == {"ok": 1, "busy": 19}
    assert len(svc.list_tasks("active")) == 1


def test_20_parallel_delegations_from_different_sessions_yield_exactly_one_winner(svc):
    outcomes = _race(
        [
            lambda i=i: svc.reserve_for_delegation("karla", f"Auftrag {i}", "", "C:/p", f"s{i}", f"toolu_{i}")
            for i in range(20)
        ]
    )
    assert Counter(kind for kind, _ in outcomes) == {"ok": 1, "busy": 19}
    winner = next(v for kind, v in outcomes if kind == "ok")
    losers = [v for kind, v in outcomes if kind == "busy"]
    assert all(e.details["task_id"] == winner["id"] for e in losers)


def test_parallel_different_agents_all_succeed(svc):
    outcomes = _race([lambda n=n: svc.start_task(n, "Parallel") for n in ("karla", "yasmin", "lotta")])
    assert Counter(kind for kind, _ in outcomes) == {"ok": 3}
