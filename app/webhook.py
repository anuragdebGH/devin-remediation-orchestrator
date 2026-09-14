from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.config import Settings
from app.models import IssueEvent


class IgnoredWebhook(ValueError):
    pass


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_issue_event(
    payload: dict[str, Any], delivery_id: str, event_name: str, settings: Settings
) -> IssueEvent:
    if event_name != "issues":
        raise IgnoredWebhook("only GitHub issues events are supported")
    if payload.get("action") != "labeled":
        raise IgnoredWebhook("only the labeled action triggers remediation")
    label = payload.get("label", {}).get("name")
    if label != settings.trigger_label:
        raise IgnoredWebhook(f"label {label!r} is not the trigger label")

    repository = payload.get("repository", {}).get("full_name")
    if repository != settings.github_repository:
        raise IgnoredWebhook("repository is not allowlisted")

    issue = payload.get("issue") or {}
    if "pull_request" in issue:
        raise IgnoredWebhook("pull request issue events are ignored")
    association = str(issue.get("author_association") or "NONE").upper()
    if association not in settings.trusted_author_associations:
        raise IgnoredWebhook("issue author is not a trusted repository contributor")

    return IssueEvent(
        delivery_id=delivery_id,
        repository=repository,
        issue_number=int(issue["number"]),
        issue_url=str(issue["html_url"]),
        title=str(issue.get("title") or "Untitled issue"),
        body=str(issue.get("body") or ""),
        author_association=association,
    )
