# Contract: Auth API

See `_conventions.md` for shared rules. Covers spec User Story 1 (FR-001–FR-011).

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `POST /auth/signup` | Public | `{email, password, name}` | `201 {user, organization}` + sets refresh cookie, returns access token in body | `422` validation, `409 email_taken` |
| `POST /auth/login` | Public | `{email, password}` | `200 {user, access_token}` + sets refresh cookie | `401 invalid_credentials` (identical response whether email exists or not — FR-010 anti-enumeration) |
| `POST /auth/logout` | Authenticated | — | `204` — revokes the current refresh token | — |
| `POST /auth/logout-all` | Authenticated | — | `204` — revokes all of the user's refresh tokens | — |
| `POST /auth/refresh` | Public (cookie) | — (refresh cookie) | `200 {access_token}` | `401 invalid_or_expired_refresh_token` |
| `POST /auth/forgot-password` | Public | `{email}` | `202` always (never reveals whether the email exists — FR-010) | — |
| `POST /auth/reset-password` | Public | `{token, new_password}` | `200` | `400 invalid_or_expired_token` |
| `GET /auth/me` | Authenticated | — | `200 {user, organization, role}` | — |
| `PATCH /auth/me` | Authenticated | `{name?, email?}` | `200 {user}` | `422`, `409 email_taken` |
| `POST /auth/me/change-password` | Authenticated | `{current_password, new_password}` | `200` | `401 invalid_current_password` |
| `GET /auth/me/sessions` | Authenticated | — | `200 {items: [{id, created_at, last_used_at, is_current}]}` | — |
| `DELETE /auth/me/sessions/{session_id}` | Authenticated | — | `204` — revokes one specific refresh token | `404` |

**Rate limits** (SEC-009): `login`, `signup`, `forgot-password` are limited per-IP and
per-email (e.g. 5/min, 20/hour) — exceeding returns `429 rate_limited`.

**Security notes**: `login`/`forgot-password` return structurally identical responses/timings
regardless of whether the account exists (FR-010). Access tokens are never persisted client-side
beyond memory/short-lived storage the frontend controls; the refresh token is httpOnly and never
readable by JavaScript.
