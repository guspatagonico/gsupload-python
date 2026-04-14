# Plan: Auth and Billing Rollout (Hosted Service)

## Scope and Goals
- Define an authentication layer for a hosted `gsupload` service.
- Add usage-based billing with transparent metering and invoicing.
- Preserve the existing CLI behavior for self-hosted FTP/SFTP usage.

## Non-goals
- Rewriting the CLI into a web UI.
- Replacing existing local config-based workflows.
- Supporting on-prem billing providers in the first release.

## Current-state Assumptions
- The repository is a Python CLI package with no server runtime yet.
- Existing configuration files contain host credentials and should remain local.
- No billing system or auth provider is currently integrated.

## Risks and Dependencies
- Selecting a billing provider with stable Python SDK support.
- Secure storage of credentials and secrets for hosted usage.
- Legal/compliance requirements for payment data handling.
- Backward compatibility for existing CLI users.

## Phases with Checklists
### Design and Contracts
- [ ] Write an ADR in `docs/` documenting the chosen auth mechanism and token policy.
- [ ] Write an ADR in `docs/` documenting the billing provider and tier limits.
- [ ] Add a usage metric schema doc under `docs/` (bytes/files/sessions).
- [ ] Draft API contracts in `docs/` and link them from `docs/ARCHITECTURE.md`.
- [ ] Exit criteria: ADRs merged and linked from `docs/ARCHITECTURE.md`.

### Hosted Service MVP
- [ ] Create a new `src/gsupload/hosted/` package for hosted service clients.
- [ ] Implement client calls for health, token issuance, usage ingest, entitlement checks.
- [ ] Add idempotency key handling and audit logging for usage events.
- [ ] Document data retention policy in `docs/`.
- [ ] Exit criteria: integration tests hit mock endpoints with 200 OK responses.

### CLI Integration and Docs
- [ ] Add hosted config fields in `src/gsupload/config.py` with validation.
- [ ] Add CLI auth flow in `src/gsupload/cli.py` (token acquire/refresh).
- [ ] Add usage reporting hooks in `src/gsupload/utils.py` or `src/gsupload/hosted/`.
- [ ] Update `gsupload.json.example` with hosted-mode fields (no secrets).
- [ ] Update `docs/USER_MANUAL.md` with hosted-mode configuration.
- [ ] Add tests in `tests/test_config.py` and `tests/test_cli.py` for hosted settings.
- [ ] Exit criteria: hosted-mode CLI passes `pytest` and docs are updated.

### Billing Launch
- [ ] Implement webhook handlers for billing events (invoice paid/failed).
- [ ] Reconcile usage → invoice for sample accounts and document results.
- [ ] Add admin reporting and fraud thresholds.
- [ ] Run limited beta and capture support outcomes.
- [ ] Exit criteria: invoices reconcile with usage for the beta cohort.

## Verification Commands and Acceptance Criteria
- `pytest` remains green for the CLI.
- Auth endpoints return valid tokens and reject invalid credentials.
- Usage ingestion is idempotent and produces stable monthly totals.
- A full usage cycle results in a correct invoice without manual edits.

## Rollback Notes
- If billing reconciliation fails, disable usage reporting and revert to free-tier only.
- If auth instability causes outages, fall back to CLI-only local usage.

## Delivery Evidence
- Architecture docs updated for hosted service components.
- CLI docs include hosted mode configuration.
- Billing reconciliation report for the beta cohort.
