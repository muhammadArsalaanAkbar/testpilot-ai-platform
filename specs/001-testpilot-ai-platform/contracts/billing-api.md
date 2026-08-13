# Contract: Billing / Subscription API

See `_conventions.md`. Covers FR-119–FR-129.

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /organizations/current/billing` | Authenticated | — | `200 {plan: {tier, limits: {...}}, usage: {projects, test_executions, ai_operations, members}, period: {start, end}}` | — |
| `GET /billing/plans` | Public | — | `200 {items: [{tier, limits, price_cents}]}` (for the marketing `/pricing` page and in-app upgrade prompts) | — |
| `POST /organizations/current/billing/change-plan` *(Future)* | Authenticated (owner) | `{tier}` | `200 {organization}` | `402 payment_required`, `403` |

**Usage enforcement**: not a separate endpoint — every write endpoint that consumes a limited
resource (project creation, test-run creation, generation/analysis enqueue) independently
returns `402 {"error": {"code": "plan_limit_exceeded", "details": {"limit": "test_executions",
"used": N, "max": M}}}` when blocked, per plan.md's `billing.check_and_reserve_usage()`. This
contract's `GET /billing` endpoint is for display (Settings → Billing page), not enforcement.
