# Five-minute Loom script

## 0:00–0:45 — What

“Engineering teams do not lack dependency alerts or backlog tickets; they lack execution capacity.
Superset is a useful example: its requirements file explicitly caps `apispec` below 6.7 because an
upgrade broke a test, while its Cypress test package remains on 11.2 with a version-specific Chrome
workaround. Both are known work, but each requires investigation, code changes, tests, and a clean
PR—not another alert.

I built a governed remediation control plane. When a trusted maintainer adds the
`devin-remediate` label, the system turns that approved issue into one bounded Devin session and
tracks it through a pull request.”

## 0:45–2:15 — Demo

1. Show the two issues in `anuragdebGH/superset`; open the `apispec` issue.
2. Show the dashboard with no active task.
3. Add `devin-remediate` to the issue, or run `python scripts/simulate_webhook.py` for the local demo.
4. Refresh the issue: point out the Devin session comment and link.
5. Open the Devin session briefly: show repository investigation, test reproduction, and the branch.
6. Return to the dashboard: show `running`, then `completed`, success rate, time-to-PR, and PR URL.
7. Open the PR: show the focused diff, regression test, exact test commands, and `Closes #1`.

Say explicitly when using simulation: “The lifecycle you see is deterministic mock data; it proves
the control plane without consuming Devin or GitHub credentials. The real evidence is the linked
Devin session and PR shown next.” Do not present `/pull/999` as a real PR.

## 2:15–3:35 — How

“GitHub signs the webhook. The receiver verifies HMAC, accepts only `issues.labeled`, checks the
repository allowlist, exact trigger label, and trusted author association, then durably inserts a
task. Delivery and repository/issue uniqueness make redelivery safe.

A bounded worker creates a Devin v3 organization session with the repository, issue-specific
prompt, tags, ACU ceiling, and required JSON output schema. The issue body is untrusted input, not
agent policy. The prompt requires reproduction, minimal change, regression coverage, repository
test conventions, a rollback note, and a PR; it explicitly forbids merging or touching secrets and
permissions.

The worker reconciles Devin status after restarts. It maps waiting states to human action, marks
hard session failures, and only calls the task successful when the API exposes a PR. Every state is
in SQLite, GitHub receives progress comments, `/api/summary` powers the dashboard, and `/metrics`
is Prometheus-compatible.”

## 3:35–4:25 — Why Devin

“A deterministic bot can bump a version string. It cannot reliably discover why a large codebase
pinned that version, reproduce a cross-library failure, locate the correct test, adapt code, select
the relevant checks, interpret failures, and author a coherent PR across Python and TypeScript.
That is the critical distinction: this system automates an engineering outcome, not a command.

Devin is the core execution primitive. The surrounding service supplies governance, durability,
budgeting, and measurement; Devin supplies the adaptive multi-step work that makes heterogeneous
backlog remediation practical.”

## 4:25–5:00 — When / next steps

“For a customer deployment I would first replay historical issues to establish acceptance rate,
time-to-PR, engineer review time, and cost per accepted PR. Then I would introduce risk tiers:
automatic session start for low-risk dependency and test work, explicit approval for sensitive
areas, and no autonomous merge initially.

At scale I would move the ledger to Postgres, queue events, ingest CI results, add OpenTelemetry,
and use repository-specific Devin playbooks. The VP-level measure is not sessions created; it is
accepted PR throughput, lead-time reduction, and engineering hours returned, bounded by review
quality and spend.”
