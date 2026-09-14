# Remove the `apispec <6.7.0` dependency ceiling

## Problem

`requirements/base.in` currently contains `apispec>=6.0.0,<6.7.0` with a comment that 6.7.0
breaks a unit test. This leaves Superset on 6.6.1 while compatible fixes and releases continue
upstream. The exact incompatibility is not documented by a regression test or linked failure.

## Requested remediation

Reproduce the failure using the newest `apispec` version supported by Superset's Python matrix.
Fix the underlying OpenAPI/schema incompatibility rather than weakening assertions, then update
the input and generated requirements consistently.

## Acceptance criteria

- The 6.7.0 ceiling is removed or advanced, with the remaining constraint justified in code.
- The broken behavior is covered by a focused regression test.
- Relevant OpenAPI/API tests and dependency consistency checks pass.
- The PR changes no unrelated dependencies.
- The PR documents the reproduced root cause, commands run, risk, and rollback.
