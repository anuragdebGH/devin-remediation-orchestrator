from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.models import IssueEvent, Task


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TaskStore:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_id TEXT NOT NULL UNIQUE,
                    repository TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    issue_url TEXT NOT NULL,
                    issue_title TEXT NOT NULL,
                    issue_body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    devin_session_id TEXT,
                    devin_url TEXT,
                    pr_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    last_polled_at TEXT,
                    UNIQUE(repository, issue_number)
                )
                """
            )

    def enqueue(self, event: IssueEvent) -> tuple[Task, bool]:
        timestamp = now_iso()
        created = True
        with self._connection() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO remediation_tasks (
                        delivery_id, repository, issue_number, issue_url,
                        issue_title, issue_body, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                    """,
                    (
                        event.delivery_id,
                        event.repository,
                        event.issue_number,
                        event.issue_url,
                        event.title,
                        event.body,
                        timestamp,
                        timestamp,
                    ),
                )
                task_id = int(cursor.lastrowid)
            except sqlite3.IntegrityError:
                created = False
                row = connection.execute(
                    """
                    SELECT id FROM remediation_tasks
                    WHERE delivery_id = ? OR (repository = ? AND issue_number = ?)
                    ORDER BY id LIMIT 1
                    """,
                    (event.delivery_id, event.repository, event.issue_number),
                ).fetchone()
                if row is None:
                    raise
                task_id = int(row["id"])
        task = self.get(task_id)
        assert task is not None
        return task, created

    def get(self, task_id: int) -> Task | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM remediation_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._to_task(row) if row else None

    def list(self, limit: int = 100) -> list[Task]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM remediation_tasks ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._to_task(row) for row in rows]

    def queued(self, limit: int) -> list[Task]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remediation_tasks
                WHERE status = 'queued' ORDER BY id LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_task(row) for row in rows]

    def active(self) -> list[Task]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remediation_tasks
                WHERE status IN ('starting', 'running', 'action_required')
                ORDER BY id
                """
            ).fetchall()
        return [self._to_task(row) for row in rows]

    def interrupted_starts(self) -> list[Task]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remediation_tasks
                WHERE status = 'starting' AND devin_session_id IS NULL
                ORDER BY id
                """
            ).fetchall()
        return [self._to_task(row) for row in rows]

    def failed_without_pr(self, limit: int = 100) -> list[Task]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remediation_tasks
                WHERE status = 'failed' AND pr_url IS NULL
                ORDER BY id LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_task(row) for row in rows]

    def mark_starting(self, task_id: int) -> bool:
        timestamp = now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE remediation_tasks
                SET status = 'starting', started_at = COALESCE(started_at, ?),
                    updated_at = ?, error = NULL
                WHERE id = ? AND status = 'queued'
                """,
                (timestamp, timestamp, task_id),
            )
        return cursor.rowcount == 1

    def mark_running(self, task_id: int, session_id: str, session_url: str) -> None:
        timestamp = now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE remediation_tasks
                SET status = 'running', devin_session_id = ?, devin_url = ?, updated_at = ?
                WHERE id = ?
                """,
                (session_id, session_url, timestamp, task_id),
            )

    def mark_polled(self, task_id: int, status: str) -> None:
        timestamp = now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE remediation_tasks
                SET status = ?, updated_at = ?, last_polled_at = ? WHERE id = ?
                """,
                (status, timestamp, timestamp, task_id),
            )

    def mark_completed(self, task_id: int, pr_url: str, created_at: str | None = None) -> None:
        timestamp = now_iso()
        completed_timestamp = created_at or timestamp
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE remediation_tasks
                SET status = 'completed', pr_url = ?, completed_at = ?, updated_at = ?,
                    last_polled_at = ?, error = NULL WHERE id = ?
                """,
                (pr_url, completed_timestamp, timestamp, timestamp, task_id),
            )

    def mark_failed(self, task_id: int, error: str) -> None:
        timestamp = now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE remediation_tasks
                SET status = 'failed', error = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (error[:2000], timestamp, timestamp, task_id),
            )

    def retry(self, task_id: int) -> bool:
        timestamp = now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE remediation_tasks
                SET status = 'queued', devin_session_id = NULL, devin_url = NULL,
                    pr_url = NULL, error = NULL, started_at = NULL, completed_at = NULL,
                    last_polled_at = NULL, updated_at = ?
                WHERE id = ? AND status = 'failed'
                """,
                (timestamp, task_id),
            )
        return cursor.rowcount == 1

    def summary(self) -> dict[str, object]:
        with self._connection() as connection:
            status_rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM remediation_tasks GROUP BY status"
            ).fetchall()
            duration_row = connection.execute(
                """
                SELECT AVG((julianday(completed_at) - julianday(started_at)) * 86400.0)
                    AS average_seconds
                FROM remediation_tasks
                WHERE status = 'completed' AND started_at IS NOT NULL
                """
            ).fetchone()
        counts = {str(row["status"]): int(row["count"]) for row in status_rows}
        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0)
        terminal = completed + failed
        pr_creation_success_rate = (completed / terminal) if terminal else None
        return {
            "total": sum(counts.values()),
            "by_status": counts,
            "active": sum(counts.get(s, 0) for s in ("starting", "running", "action_required")),
            "throughput_completed": completed,
            "pr_creation_success_rate": pr_creation_success_rate,
            "success_rate": pr_creation_success_rate,
            "average_time_to_pr_seconds": duration_row["average_seconds"] if duration_row else None,
        }

    @staticmethod
    def _to_task(row: sqlite3.Row) -> Task:
        return Task(**dict(row))
