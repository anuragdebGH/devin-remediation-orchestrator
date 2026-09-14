from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    github_webhook_secret: str
    github_token: str
    github_repository: str
    trigger_label: str
    devin_api_key: str
    devin_org_id: str
    devin_api_base_url: str = "https://api.devin.ai"
    devin_mode: str = "normal"
    devin_max_acu_limit: int = 10
    database_path: str = "/data/orchestrator.db"
    poll_interval_seconds: float = 15.0
    max_concurrent_sessions: int = 3
    trusted_author_associations: tuple[str, ...] = ("OWNER", "MEMBER", "COLLABORATOR")
    log_level: str = "INFO"
    devin_client_mode: str = "live"
    github_client_mode: str = "live"
    enable_demo_endpoint: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        associations = tuple(
            item.strip().upper()
            for item in os.getenv(
                "TRUSTED_AUTHOR_ASSOCIATIONS", "OWNER,MEMBER,COLLABORATOR"
            ).split(",")
            if item.strip()
        )
        return cls(
            github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_repository=os.getenv("GITHUB_REPOSITORY", "anuragdebGH/superset"),
            trigger_label=os.getenv("TRIGGER_LABEL", "devin-remediate"),
            devin_api_key=os.getenv("DEVIN_API_KEY", ""),
            devin_org_id=os.getenv("DEVIN_ORG_ID", ""),
            devin_api_base_url=os.getenv("DEVIN_API_BASE_URL", "https://api.devin.ai"),
            devin_mode=os.getenv("DEVIN_MODE", "normal"),
            devin_max_acu_limit=int(os.getenv("DEVIN_MAX_ACU_LIMIT", "10")),
            database_path=os.getenv("DATABASE_PATH", "/data/orchestrator.db"),
            poll_interval_seconds=float(os.getenv("POLL_INTERVAL_SECONDS", "15")),
            max_concurrent_sessions=int(os.getenv("MAX_CONCURRENT_SESSIONS", "3")),
            trusted_author_associations=associations,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            devin_client_mode=os.getenv("DEVIN_CLIENT_MODE", "live").lower(),
            github_client_mode=os.getenv("GITHUB_CLIENT_MODE", "live").lower(),
            enable_demo_endpoint=_as_bool(os.getenv("ENABLE_DEMO_ENDPOINT", "false")),
        )

    def validate(self) -> None:
        errors: list[str] = []
        if not self.github_webhook_secret:
            errors.append("GITHUB_WEBHOOK_SECRET is required")
        if "/" not in self.github_repository:
            errors.append("GITHUB_REPOSITORY must be owner/repository")
        if self.devin_client_mode not in {"live", "mock"}:
            errors.append("DEVIN_CLIENT_MODE must be live or mock")
        if self.github_client_mode not in {"live", "mock"}:
            errors.append("GITHUB_CLIENT_MODE must be live or mock")
        if self.devin_client_mode == "live" and not (
            self.devin_api_key and self.devin_org_id
        ):
            errors.append("DEVIN_API_KEY and DEVIN_ORG_ID are required in live mode")
        if self.github_client_mode == "live" and not self.github_token:
            errors.append("GITHUB_TOKEN is required in live mode")
        if self.max_concurrent_sessions < 1:
            errors.append("MAX_CONCURRENT_SESSIONS must be at least 1")
        if errors:
            raise ValueError("; ".join(errors))
