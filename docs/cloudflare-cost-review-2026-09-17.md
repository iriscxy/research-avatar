# Cloudflare cost investigation — 2026-09-17

## Confirmed cause

The Containers usage API reports approximately $219.58 of gross CPU, memory and disk
usage from 2026-08-17 to 2026-09-17 08:27 UTC, before included allowances and taxes:
$203.05 memory, $11.44 disk and $5.09 CPU. This is an estimate using current published
rates, not a reconciled invoice. The exact billing period and card transaction remain
unverified because Wrangler cannot read billing history and the dashboard needs login.
Durable Objects also accumulated approximately 2.49 million GB-seconds; its included
allowance and billable-unit rounding must be applied to the actual invoice period.

There were 59 container applications left by historical releases. On August 25,
18 versions each accumulated roughly one day of 4-GiB allocation; most reported zero
transmitted bytes. Only the current V61 instance was running at inspection on September
17; the other 58 applications had no running instances. The CLI's application-level
`instances: 6` is not proof of six billable, running containers.

A local reproduction using the exact deployed image confirmed that its Python PID 1
ignored SIGTERM. Cloudflare Containers SDK 0.0.29 implements idle stop by sending
SIGTERM, with no automatic SIGKILL escalation. The gateway registered no SIGTERM
handler. Separately, creating a new Durable Object class/name for releases allowed
obsolete versions to keep running independently. The previous release verification
missed shutdown behavior and historical resource cleanup.

## Correction

- Handle SIGTERM explicitly, exit through the gateway cleanup, and terminate child
  studio workers. Preserve the existing two-hour inactivity window.
- Use `basic` (1 GiB, 0.25 vCPU, 4 GB disk), at most one container and two private
  studio sessions. The recent current-version measured memory peak was ~139 MiB.
- Pin `ONLINE_STUDIO_INSTANCE_NAME` to the existing production instance name, so
  Worker-only releases do not create another container. Keep the V61 class; update
  the image through the same container application's rollout.
- Remove stopped historical container applications only after rechecking that each
  has no instances. Preserve registry images, current V61 and D1 account/auth/usage
  data. Retire old V30–V60 Durable Object classes in migration v63; older classes
  were already retired by v31.

At published rates, one continuously running container's memory costs $25.92 per
30 days at 4 GiB and $6.48 at 1 GiB, before allowances. Actual sleep reduces this.
The $5 Workers plan, CPU, disk, Durable Objects, tax and any other services are
separate. Application model-spend quotas do not cap Cloudflare infrastructure bills.

## Evidence and validation

Evidence is retained under `outputs/cloudflare-billing-review-20260917/`:
container usage and daily analysis, workload memory peaks, pre-cleanup instance
inventory, exact cleanup targets/results, SIGTERM reproduction and reduced-resource
runtime verification. No real model calls are required for these checks.

Sources:
- https://developers.cloudflare.com/containers/platform/pricing/
- https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-container-metrics/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
