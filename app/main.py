from __future__ import annotations

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from html import escape
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from app.clients import DevinClient, GitHubClient, MockDevinClient, MockGitHubClient
from app.config import Settings
from app.db import TaskStore
from app.orchestrator import Orchestrator
from app.webhook import IgnoredWebhook, parse_issue_event, verify_signature


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    resolved.validate()
    configure_logging(resolved.log_level)

    store = TaskStore(resolved.database_path)
    store.initialize()
    devin = MockDevinClient() if resolved.devin_client_mode == "mock" else DevinClient(resolved)
    github = (
        MockGitHubClient() if resolved.github_client_mode == "mock" else GitHubClient(resolved)
    )
    orchestrator = Orchestrator(resolved, store, devin, github)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        orchestrator.start()
        try:
            yield
        finally:
            await orchestrator.stop()
            await devin.close()
            await github.close()

    api = FastAPI(
        title="Devin Remediation Orchestrator",
        version="1.0.0",
        lifespan=lifespan,
    )
    api.state.settings = resolved
    api.state.store = store
    api.state.orchestrator = orchestrator
    api.state.github = github

    @api.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/webhooks/github", status_code=202)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str = Header(default=""),
        x_github_delivery: str = Header(default=""),
    ) -> dict[str, Any]:
        body = await request.body()
        if not verify_signature(body, x_hub_signature_256, resolved.github_webhook_secret):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
        if not x_github_delivery:
            raise HTTPException(status_code=400, detail="missing X-GitHub-Delivery")
        try:
            payload = json.loads(body)
            event = parse_issue_event(payload, x_github_delivery, x_github_event, resolved)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="invalid JSON") from error
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, IgnoredWebhook):
                return {"accepted": False, "reason": str(error)}
            raise HTTPException(status_code=422, detail="malformed issue payload") from error
        task, created = store.enqueue(event)
        return {"accepted": created, "duplicate": not created, "task": task.to_dict()}

    @api.post("/api/tasks/{task_id}/retry")
    async def retry_task(task_id: int) -> dict[str, Any]:
        if not store.retry(task_id):
            raise HTTPException(status_code=409, detail="only failed tasks can be retried")
        task = store.get(task_id)
        return {"retried": True, "task": task.to_dict() if task else None}

    @api.get("/api/tasks")
    async def list_tasks(limit: int = 100) -> dict[str, Any]:
        safe_limit = min(max(limit, 1), 500)
        return {"tasks": [task.to_dict() for task in store.list(safe_limit)]}

    @api.get("/api/summary")
    async def summary() -> dict[str, object]:
        return store.summary()

    @api.get("/metrics")
    async def metrics() -> Response:
        data = store.summary()
        counts = data["by_status"]
        lines = [
            "# HELP remediation_tasks Number of remediation tasks by state.",
            "# TYPE remediation_tasks gauge",
        ]
        for status in sorted(counts):
            lines.append(f'remediation_tasks{{status="{status}"}} {counts[status]}')
        lines.extend(
            [
                "# HELP remediation_pr_creation_success_rate Completed tasks divided by "
                "terminal tasks.",
                "# TYPE remediation_pr_creation_success_rate gauge",
                f"remediation_pr_creation_success_rate {data['pr_creation_success_rate'] or 0}",
                "# HELP remediation_average_time_to_pr_seconds Mean start-to-PR duration.",
                "# TYPE remediation_average_time_to_pr_seconds gauge",
                f"remediation_average_time_to_pr_seconds "
                f"{data['average_time_to_pr_seconds'] or 0}",
            ]
        )
        return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @api.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> str:
        return dashboard_html(store.summary(), [task.to_dict() for task in store.list(50)])

    @api.post("/demo/trigger", status_code=202)
    async def demo_trigger(request: Request) -> dict[str, Any]:
        if not resolved.enable_demo_endpoint:
            raise HTTPException(status_code=404, detail="not found")
        payload = await request.json()
        body = json.dumps(payload, separators=(",", ":")).encode()
        delivery = "demo-" + hashlib.sha256(body).hexdigest()[:16]
        signature = "sha256=" + hmac.new(
            resolved.github_webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not verify_signature(body, signature, resolved.github_webhook_secret):
            raise HTTPException(status_code=500, detail="demo signature failure")
        try:
            event = parse_issue_event(payload, delivery, "issues", resolved)
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        task, created = store.enqueue(event)
        return {"accepted": created, "duplicate": not created, "task": task.to_dict()}

    return api


def dashboard_html(summary: dict[str, object], tasks: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{task['id']}</td><td>{escape(task['repository'])}#{task['issue_number']}</td>"
        f"<td><span class='state {escape(task['status'])}'>{escape(task['status'])}</span></td>"
        f"<td>{escape(task['issue_title'])}</td>"
        f"<td>{link(task['devin_url'], 'session')}</td>"
        f"<td>{link(task['pr_url'], 'pull request')}</td>"
        f"<td>{escape(task['error'] or '')}</td></tr>"
        for task in tasks
    )
    rate = summary["pr_creation_success_rate"]
    rate_text = "n/a" if rate is None else f"{float(rate) * 100:.0f}%"
    average = summary["average_time_to_pr_seconds"]
    average_text = "n/a" if average is None else f"{float(average):.1f}s"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Devin Remediation Control Plane</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#0b1020;color:#e8edf7;margin:0;padding:32px}}
h1{{margin:0 0 8px}} .sub{{color:#9ba8bf;margin-bottom:28px}}
.cards{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:14px;margin-bottom:28px}}
.card{{background:#151d31;border:1px solid #26324d;border-radius:12px;padding:18px}}
.value{{font-size:30px;font-weight:700;margin-top:8px}}
table{{width:100%;border-collapse:collapse;background:#151d31}}
th,td{{padding:12px;border-bottom:1px solid #26324d;text-align:left;vertical-align:top}}
th{{color:#9ba8bf}}
a{{color:#72a7ff}} .state{{padding:4px 8px;border-radius:999px;background:#26324d}}
.completed{{background:#174c36}} .failed{{background:#642c34}}
.running,.starting{{background:#234a71}}
@media(max-width:800px){{
  .cards{{grid-template-columns:1fr 1fr}}
  body{{padding:16px}}
  table{{font-size:12px}}
}}
</style></head><body>
<h1>Devin Remediation Control Plane</h1>
<div class="sub">
GitHub issue → governed Devin session → reviewable pull request · refreshes every 5s
</div>
<div class="cards">
<div class="card">Total tasks<div class="value">{summary['total']}</div></div>
<div class="card">Active<div class="value">{summary['active']}</div></div>
<div class="card">PR creation success<div class="value">{rate_text}</div></div>
<div class="card">Average time to PR<div class="value">{average_text}</div></div>
</div>
<table><thead><tr><th>ID</th><th>Issue</th><th>Status</th><th>Title</th><th>Devin</th><th>Output</th><th>Error</th></tr></thead>
<tbody>{rows or '<tr><td colspan="7">No remediation events yet.</td></tr>'}</tbody></table>
</body></html>"""


def link(url: str | None, label: str) -> str:
    if not url or urlparse(url).scheme not in {"http", "https"}:
        return "—"
    return f'<a href="{escape(url)}">{label}</a>'


app = create_app()
