from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.models import SessionSnapshot, Task

logger = logging.getLogger(__name__)


class DevinGateway(Protocol):
    async def create_session(self, task: Task, prompt: str) -> SessionSnapshot: ...

    async def get_session(self, session_id: str) -> SessionSnapshot: ...


class GitHubGateway(Protocol):
    async def comment(self, repository: str, issue_number: int, body: str) -> None: ...


class DevinClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.devin_api_base_url,
            headers={
                "Authorization": f"Bearer {settings.devin_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    async def create_session(self, task: Task, prompt: str) -> SessionSnapshot:
        response = await self.client.post(
            f"/v3/organizations/{self.settings.devin_org_id}/sessions",
            json={
                "prompt": prompt,
                "title": f"Remediate {task.repository}#{task.issue_number}",
                "repos": [task.repository],
                "tags": ["event-driven-remediation", f"issue-{task.issue_number}"],
                "devin_mode": self.settings.devin_mode,
                "max_acu_limit": self.settings.devin_max_acu_limit,
                "resumable": True,
                "structured_output_required": True,
                "structured_output_schema": structured_output_schema(),
            },
        )
        response.raise_for_status()
        return _snapshot(response.json())

    async def get_session(self, session_id: str) -> SessionSnapshot:
        response = await self.client.get(
            f"/v3/organizations/{self.settings.devin_org_id}/sessions/{session_id}"
        )
        response.raise_for_status()
        return _snapshot(response.json())

    async def close(self) -> None:
        await self.client.aclose()


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "devin-remediation-orchestrator/1.0",
            },
            timeout=httpx.Timeout(20.0),
        )

    async def comment(self, repository: str, issue_number: int, body: str) -> None:
        response = await self.client.post(
            f"/repos/{repository}/issues/{issue_number}/comments", json={"body": body}
        )
        response.raise_for_status()

    async def close(self) -> None:
        await self.client.aclose()


class MockDevinClient:
    """Deterministic lifecycle for local demos; it never calls Devin or GitHub."""

    def __init__(self) -> None:
        self.polls: dict[str, int] = {}
        self.repositories: dict[str, str] = {}

    async def create_session(self, task: Task, prompt: str) -> SessionSnapshot:
        del prompt
        session_id = f"devin-demo-{task.id}"
        self.polls[session_id] = 0
        self.repositories[session_id] = task.repository
        return SessionSnapshot(
            session_id=session_id,
            url=f"https://app.devin.ai/sessions/{session_id}",
            status="new",
            status_detail=None,
            pull_requests=(),
        )

    async def get_session(self, session_id: str) -> SessionSnapshot:
        await asyncio.sleep(0)
        count = self.polls.get(session_id, 0) + 1
        self.polls[session_id] = count
        repository = self.repositories.get(session_id, "example/repository")
        if count < 2:
            return SessionSnapshot(
                session_id=session_id,
                url=f"https://app.devin.ai/sessions/{session_id}",
                status="running",
                status_detail="working",
                pull_requests=(),
            )
        pr_url = f"https://github.com/{repository}/pull/999"
        return SessionSnapshot(
            session_id=session_id,
            url=f"https://app.devin.ai/sessions/{session_id}",
            status="running",
            status_detail="finished",
            pull_requests=(pr_url,),
            structured_output={
                "outcome": "pull_request_opened",
                "summary": "Updated the dependency and added regression coverage.",
                "tests": ["targeted unit tests passed"],
                "pull_request_url": pr_url,
            },
        )

    async def close(self) -> None:
        return None


class MockGitHubClient:
    def __init__(self) -> None:
        self.comments: list[dict[str, Any]] = []

    async def comment(self, repository: str, issue_number: int, body: str) -> None:
        self.comments.append(
            {"repository": repository, "issue_number": issue_number, "body": body}
        )
        logger.info(
            "mock_github_comment repository=%s issue=%s body=%s",
            repository,
            issue_number,
            re.sub(r"\s+", " ", body)[:240],
        )

    async def close(self) -> None:
        return None


def structured_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["outcome", "summary", "tests", "pull_request_url"],
        "properties": {
            "outcome": {
                "type": "string",
                "enum": ["pull_request_opened", "blocked", "no_change_required"],
            },
            "summary": {"type": "string"},
            "tests": {"type": "array", "items": {"type": "string"}},
            "pull_request_url": {"type": ["string", "null"]},
        },
    }


def _snapshot(payload: dict[str, Any]) -> SessionSnapshot:
    pull_requests = tuple(
        item["pr_url"]
        for item in payload.get("pull_requests", [])
        if isinstance(item, dict) and item.get("pr_url")
    )
    return SessionSnapshot(
        session_id=payload["session_id"],
        url=payload["url"],
        status=payload["status"],
        status_detail=payload.get("status_detail"),
        pull_requests=pull_requests,
        structured_output=payload.get("structured_output"),
    )
