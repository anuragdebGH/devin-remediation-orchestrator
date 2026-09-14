from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IssueEvent:
    delivery_id: str
    repository: str
    issue_number: int
    issue_url: str
    title: str
    body: str
    author_association: str


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    url: str
    status: str
    status_detail: str | None
    pull_requests: tuple[str, ...]
    structured_output: dict[str, Any] | None = None


@dataclass(frozen=True)
class Task:
    id: int
    delivery_id: str
    repository: str
    issue_number: int
    issue_url: str
    issue_title: str
    issue_body: str
    status: str
    devin_session_id: str | None
    devin_url: str | None
    pr_url: str | None
    error: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    updated_at: str
    last_polled_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
