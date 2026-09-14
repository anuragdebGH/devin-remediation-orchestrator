from __future__ import annotations

from app.db import TaskStore
from app.models import IssueEvent


def event(delivery_id: str = "delivery-1") -> IssueEvent:
    return IssueEvent(
        delivery_id=delivery_id,
        repository="anuragdebGH/superset",
        issue_number=1,
        issue_url="https://github.com/anuragdebGH/superset/issues/1",
        title="Upgrade apispec",
        body="Do the work",
        author_association="OWNER",
    )


def test_enqueue_is_idempotent(tmp_path) -> None:
    store = TaskStore(str(tmp_path / "tasks.db"))
    store.initialize()
    first, created_first = store.enqueue(event())
    second, created_second = store.enqueue(event("delivery-2"))
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert store.summary()["total"] == 1


def test_state_and_summary(tmp_path) -> None:
    store = TaskStore(str(tmp_path / "tasks.db"))
    store.initialize()
    task, _ = store.enqueue(event())
    assert store.mark_starting(task.id)
    store.mark_running(task.id, "devin-1", "https://app.devin.ai/sessions/devin-1")
    store.mark_completed(task.id, "https://github.com/anuragdebGH/superset/pull/2")
    summary = store.summary()
    assert summary["throughput_completed"] == 1
    assert summary["success_rate"] == 1.0


def test_interrupted_start_is_visible(tmp_path) -> None:
    store = TaskStore(str(tmp_path / "tasks.db"))
    store.initialize()
    task, _ = store.enqueue(event())
    assert store.mark_starting(task.id)
    assert [item.id for item in store.interrupted_starts()] == [task.id]
