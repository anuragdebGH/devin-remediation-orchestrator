#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import urllib.request
from pathlib import Path


def request(url: str, method: str = "GET", data: bytes | None = None, headers=None):
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a signed GitHub issue webhook")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--secret", default="demo-secret")
    parser.add_argument(
        "--fixture",
        default=str(Path(__file__).parents[1] / "fixtures/apispec-issue-labeled.json"),
    )
    args = parser.parse_args()

    body = Path(args.fixture).read_bytes()
    signature = "sha256=" + hmac.new(args.secret.encode(), body, hashlib.sha256).hexdigest()
    delivery = "local-demo-" + str(time.time_ns())
    result = request(
        f"{args.base_url}/webhooks/github",
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": delivery,
        },
    )
    print(json.dumps(result, indent=2))
    task_id = result["task"]["id"]
    for _ in range(20):
        tasks = request(f"{args.base_url}/api/tasks")["tasks"]
        task = next(item for item in tasks if item["id"] == task_id)
        print(f"task={task_id} status={task['status']} pr={task['pr_url'] or '-'}")
        if task["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)


if __name__ == "__main__":
    main()
