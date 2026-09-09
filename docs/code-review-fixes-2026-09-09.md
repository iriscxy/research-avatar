# Code review fixes — 2026-09-09

All five reproduced review findings have been addressed.

- Online table saves and previews reject file-access and executable TeX commands.
  Preview and manuscript compilation share a restricted, credential-free environment.
  The API rejects edits to hosted placeholder tables even when called directly.
- Section titles use `textContent`; the status indicator is a separate DOM node.
  Uploaded/generated titles cannot inject HTML through the section list.
- Account usage is stored outside temporary projects. The hosted service mirrors
  monotonic per-project totals to Cloudflare D1 using a server-authenticated endpoint.
  Retries do not double count; a new container consults D1 before accepting work.
  Existing readable project ledgers are imported, and cleanup records usage before
  removing files. Deleted historical ledgers cannot be reconstructed.
- Title generation rebases its update under the batch-job lock and rejects a stale
  result when batch drafting has started in another request.
- Session initialization reserves capacity before model analysis and process startup.
  Failed initialization releases its reservation. Recovery and process restarts use
  the same capacity check; restarts for a session are serialized.

Model-call boundaries check hosted account usage, including background writing.
PDF transcription is included in the scoped onboarding ledger. Cancellation remains
available after the account reaches its limit. Estimates depend on reported provider
usage and configured model prices; this does not reserve the exact eventual token
cost of concurrent in-flight calls.

## Validation

- Full suite: 690 tests, 13 skipped, no failures.
- New regressions cover unsafe tables, placeholder API access, restricted TeX
  environments, stale title responses, quota reset, immediate charge persistence,
  fresh-container D1 totals, retry outboxes, and concurrent session reservations.
- Node tests execute the actual Worker code with a D1 test double and verify
  authentication, bounded bodies, account isolation and idempotent high-water marks.
- Browser verification of the actual section-rendering function confirms hostile
  markup remains visible text and no longer executes an event handler.
- An isolated release-runtime container compiled a safe table successfully. Both
  the command check and, independently, the TeX environment rejected an attempt to
  read a purpose-created marker file outside the simulated project.

## Deployment

Apply `deploy/cloudflare/migrations/0003_account_usage.sql` to AUTH_DB before
publishing the Worker. Set `ONLINE_STUDIO_USAGE_URL` to the Worker's HTTPS
`/internal/account-usage` endpoint. The existing encrypted `DEEPSEEK_API_KEY`
authenticates the container callback; never put it in Wrangler's public `vars`.
The container receives the URL and secret through its environment; browser requests
cannot update account totals.

`usage.sqlite3` is an independent local ledger/outbox under ONLINE_STUDIO_DATA_ROOT.
Keep it when deleting temporary projects. Hosted D1 is authoritative across container
replacements. A billing outage retains pending records and blocks new chargeable
work until synchronization succeeds.
