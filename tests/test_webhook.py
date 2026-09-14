from __future__ import annotations

import hashlib
import hmac

from app.config import Settings
from app.webhook import IgnoredWebhook, parse_issue_event, verify_signature


def settings(tmp_path) -> Settings:
    return Settings(
        github_webhook_secret="secret",
        github_token="",
        github_repository="anuragdebGH/superset",
        trigger_label="devin-remediate",
        devin_api_key="",
        devin_org_id="",
        database_path=str(tmp_path / "test.db"),
        devin_client_mode="mock",
        github_client_mode="mock",
    )


def payload() -> dict:
    return {
        "action": "labeled",
        "label": {"name": "devin-remediate"},
        "repository": {"full_name": "anuragdebGH/superset"},
        "issue": {
            "number": 7,
            "html_url": "https://github.com/anuragdebGH/superset/issues/7",
            "title": "Upgrade dependency",
            "body": "Acceptance criteria",
            "author_association": "OWNER",
        },
    }


def test_signature_verification() -> None:
    body = b'{"event":"value"}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, "secret")
    assert not verify_signature(body + b"x", signature, "secret")
    assert not verify_signature(body, None, "secret")


def test_parse_trusted_labeled_issue(tmp_path) -> None:
    event = parse_issue_event(payload(), "delivery-1", "issues", settings(tmp_path))
    assert event.repository == "anuragdebGH/superset"
    assert event.issue_number == 7


def test_rejects_untrusted_author(tmp_path) -> None:
    event_payload = payload()
    event_payload["issue"]["author_association"] = "NONE"
    try:
        parse_issue_event(event_payload, "delivery-1", "issues", settings(tmp_path))
    except IgnoredWebhook as error:
        assert "trusted" in str(error)
    else:
        raise AssertionError("untrusted issue author should be ignored")


def test_rejects_wrong_repository(tmp_path) -> None:
    event_payload = payload()
    event_payload["repository"]["full_name"] = "attacker/repository"
    try:
        parse_issue_event(event_payload, "delivery-1", "issues", settings(tmp_path))
    except IgnoredWebhook as error:
        assert "allowlisted" in str(error)
    else:
        raise AssertionError("wrong repository should be ignored")
