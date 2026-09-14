# Upgrade Cypress and remove the legacy Chrome headless workaround

## Problem

`superset-frontend/cypress-base/package.json` still declares Cypress `^11.2.0`.
`cypress.config.ts` carries a Chrome/Chromium 117 workaround specifically documented for Cypress
versions below 12.15.0. The stale test runtime and workaround increase security and maintenance
exposure in a critical end-to-end test path.

## Requested remediation

Upgrade Cypress to the newest major compatible with Superset's supported Node version and plugins.
Remove the obsolete Chrome headless argument rewrite, migrate configuration or tests required by
the chosen Cypress version, and keep the resulting change focused on the Cypress test package.

## Acceptance criteria

- Cypress is upgraded to a currently supported version compatible with Superset's Node matrix.
- The `<12.15.0` Chrome headless workaround and its TODO are removed.
- The Cypress configuration loads and representative headless smoke tests pass.
- Lockfiles are regenerated with the repository-standard package manager.
- Breaking changes, residual risks, test evidence, and rollback are documented in the PR.
