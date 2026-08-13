# Contract: Organizations API

See `_conventions.md`. Covers FR-012–FR-019 (MVP: read-only single-member org; Future rows
marked).

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /organizations/current` | Authenticated | — | `200 {id, name, slug, plan, created_at}` | — |
| `PATCH /organizations/current` | Authenticated (owner/admin) | `{name?}` | `200 {organization}` | `422` |
| `GET /organizations/current/members` | Authenticated | — | `200 {items: [{user_id, name, email, role}]}` (MVP: always exactly one row) | — |
| `POST /organizations/current/invitations` *(Future)* | Authenticated (owner/admin) | `{email, role}` | `202 {invitation}` | `403 insufficient_role`, `409 already_member` |
| `DELETE /organizations/current/members/{user_id}` *(Future)* | Authenticated (owner) | — | `204` | `403`, `404` |

**Authorization notes**: role checks (`owner`/`admin`/`member`) are enforced server-side on
every write; the frontend hiding a button is a UX convenience, never the actual gate (SEC-003).
At MVP, every Organization has exactly one `owner` membership and no other roles exist yet, so
role checks are exercised in tests via directly-seeded multi-membership fixtures even before the
invitation flow ships.
