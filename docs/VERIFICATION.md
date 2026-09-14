# Verification record

Date: 2026-09-14

## Verified in this build environment

- `ruff check .`: passed.
- `pytest -q`: 10 tests passed.
- HTTP service startup in mock mode: passed.
- HMAC-signed `issues.labeled` fixture: accepted.
- Durable lifecycle: `queued → starting → running → completed`.
- Observable mock output: synthetic `https://github.com/anuragdebGH/superset/pull/999`.
- `/api/summary`: one completed task, 100% terminal success, measured time-to-PR.
- `/metrics`: valid Prometheus-style task, success-rate, and duration series.
- `/dashboard`: rendered completed state plus Devin/PR links.

## Independently grounded against the public Superset fork

- The fork exists at `https://github.com/anuragdebGH/superset`.
- Its `master` branch still contains `apispec>=6.0.0,<6.7.0` and the documented broken-test note.
- Its Cypress package still declares `cypress: ^11.2.0`.
- Its Cypress configuration still contains the Chrome 117 workaround and removal TODO.
- The public orchestrator repository exists at
  `https://github.com/anuragdebGH/devin-remediation-orchestrator`.
- Superset issue #1 exists at `https://github.com/anuragdebGH/superset/issues/1`.
- Superset issue #3 exists at `https://github.com/anuragdebGH/superset/issues/3`.
- Issue #2 was closed as an accidental duplicate and is excluded from the workflow.

## Not yet verified

- Docker image build: Docker was not installed in the build environment.
- Live GitHub writes: no GitHub credential/connection was available.
- Live Devin session: no Devin API key or organization ID was available.
- Real Superset remediation PR and CI result: blocked on the two items above.

## Evidence to capture before submission

| Evidence | Value |
| --- | --- |
| Public orchestrator repository | https://github.com/anuragdebGH/devin-remediation-orchestrator |
| Superset issue 1 | https://github.com/anuragdebGH/superset/issues/1 |
| Superset issue 3 | https://github.com/anuragdebGH/superset/issues/3 |
| GitHub webhook delivery ID/status | _pending_ |
| Live Devin session URL | _pending_ |
| Real remediation PR URL | _pending_ |
| Superset checks run and result | _pending_ |
| Start-to-PR duration | _pending_ |
| ACUs consumed | _pending_ |
| Loom URL (under five minutes) | _pending_ |

Do not submit with the mock PR as evidence. Replace every pending value with a link or measured
result from the live run.
