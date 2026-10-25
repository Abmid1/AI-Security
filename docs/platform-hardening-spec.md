# Platform Hardening Specification (the scanner secures itself)

**Status:** Draft v0.1 — design only, not yet implemented.
**Companion to:** [`verification-engine-spec.md`](./verification-engine-spec.md).

**Why this document exists.** This platform stores unusually sensitive data: vulnerability findings, proof-of-exploit evidence, repository contents, and the credentials used to test customer systems. If *our* app is breached, we hand an attacker a map of everyone's weaknesses. So the platform must meet the same security bar it demands of its targets. This document specifies four non-negotiable controls:

1. Rate limiting
2. Production-grade authentication
3. Database lock-down (row-level isolation + least privilege)
4. Secret management (nothing sensitive in the client, the repo, the DB, or logs)

Each is written twice: **(A) how we build it into our platform**, and **(B) how the engine detects its absence in scanned targets** (cross-referenced to the coverage matrix).

**Plain-language framing:** these four are the "lock the doors of your own house before inspecting someone else's" rules.

---

## 1. Rate limiting

### (A) In our platform
- **Layered limits.** Apply limits at two places: the **edge** (reverse proxy / API gateway) for coarse per-IP protection, and the **application** (FastAPI middleware) for per-account and per-endpoint limits. Edge limits stop floods before they reach app code; app limits understand *who* is calling.
- **Stricter on sensitive/expensive endpoints.** Authentication endpoints (login, password reset, token issue) get tight limits to blunt credential-stuffing and brute force. **Scan-triggering endpoints** get their own budget because a scan is expensive — without this, one account could launch thousands of scans and blow up cost and outbound load. This ties into the engine's existing scan budgets/timeouts.
- **Keying.** Limit by account first, falling back to IP for unauthenticated routes. Use a shared store (e.g. Redis) so limits hold across multiple app instances, not per-process.
- **Honest responses.** Over-limit returns HTTP `429` with a `Retry-After`; never silently drop. Limit hits are logged (for abuse detection) but the logs carry no secrets.
- **Outbound limiting too.** The engine already rate-limits its *outbound* test traffic toward authorized targets (architecture §2.6). This section covers *inbound* traffic to our own API.

**Assumption H1:** a shared rate-limit store (Redis or equivalent) is available in all environments. *Validation:* health check fails closed if the store is unreachable on sensitive routes (we'd rather reject than run unprotected).

### (B) As a detection class
The engine already flags missing rate limiting in targets — see the new **Missing Rate Limiting / Resource Controls** entry in the coverage matrix.

---

## 2. Production-grade authentication

### (A) In our platform
- **Don't roll our own.** Use a vetted authentication system — a maintained identity provider / OIDC flow, or a well-maintained auth framework — rather than hand-written login/session code. Custom auth is a classic source of critical bugs.
- **Password storage (if we store passwords at all):** a modern memory-hard hash (Argon2id preferred, bcrypt acceptable) with per-user salts. Never plain, never fast hashes (MD5/SHA-family) for passwords.
- **Multi-factor authentication (MFA)** available, and **required** for roles that can authorize scans or approve patches — those are the consequential actions.
- **Sessions/tokens done right:** short-lived access tokens with refresh + rotation; session IDs regenerated on privilege change (prevents fixation); cookies marked `HttpOnly`, `Secure`, `SameSite=Lax`/`Strict`; server-side revocation on logout and on suspicious activity.
- **Brute-force defences:** account lockout/backoff + the auth-endpoint rate limits from §1; generic error messages that don't reveal whether an account exists.
- **Separation of duties:** who can *authorize a target* and who can *approve a patch* are distinct, auditable permissions (ties to the human-controlled-consequential-actions principle).
- **Transport:** TLS everywhere; HSTS; no auth material over plain HTTP, ever.

**Assumption H2:** we can adopt an external IdP / maintained auth library rather than building bespoke auth. *Validation:* confirmed during MVP; if a bespoke component is unavoidable it gets a dedicated security review before shipping.

### (B) As a detection class
Covered by the matrix's **Authentication & Session Management** entry; our own auth is also subject to the platform's security review and the evaluation programme's authenticated scenarios.

---

## 3. Database lock-down (row-level isolation + least privilege)

### (A) In our platform
- **Row-Level Security (RLS) in PostgreSQL.** Enable RLS on every table holding tenant/user data (findings, evidence, scans, targets, authorizations). Policies restrict every row to its owning tenant/user, enforced by the **database itself** — so even a bug in application code cannot leak another tenant's findings. The app sets the current tenant/user per request (e.g. via a session variable the policies read), and the policy does the rest.
  - *Why RLS and not just app-side `WHERE` clauses:* app-side filtering is one forgotten `WHERE` away from a cross-tenant leak (classic IDOR). RLS is defence-in-depth at the layer closest to the data.
- **Least-privilege DB roles.** The application connects as a role that can only `SELECT/INSERT/UPDATE/DELETE` the tables it needs — **not** a superuser, and **not** the role that owns the schema. Separate roles for: app runtime, migrations, and read-only reporting. Migrations run as a distinct role in a distinct step, never by the live app.
- **Scoped connections.** No `SET ROLE` escalation from the app role; no ability to disable RLS from the app role (RLS bypass is reserved to the owner role, which the app never uses).
- **Tenant isolation for sensitive artefacts.** Evidence bundles and repo snapshots are additionally namespaced per tenant in storage, with access checks mirroring the DB policies.
- **Encryption & retention.** Encryption at rest for the DB and evidence store; TTL + hard delete per assessment (evidence of someone's vulnerabilities shouldn't linger).

**Assumption H3:** PostgreSQL RLS meets our multi-tenant isolation needs. *Validation:* explicit cross-tenant isolation tests in the test suite — attempt to read another tenant's rows as the app role and assert it returns nothing (a binary gate, like the evaluation plan's invariant gates).

### (B) As a detection class
This *is* the access-control / IDOR detection problem viewed from the defender's side — see the matrix's **Broken Access Control / IDOR** and **API Security** entries. Our own RLS is verified by the cross-tenant isolation tests above.

---

## 4. Secret management (never expose private tokens, API keys, DB keys)

### (A) In our platform
- **Server-side only.** All secrets — DB credentials, LLM provider keys, signing keys, target-test credentials — live in **server-side configuration**: environment variables loaded from a non-committed file in development, and a managed **secrets manager / vault** in production. Never in the frontend bundle, never in client-reachable config, never returned by an API.
- **Never in git.** `.env` and any real secret file are git-ignored from commit #1; the repo ships only `.env.example` with **placeholder** values and documentation. A pre-commit secret scan (the same class of tool the engine uses) blocks accidental commits.
- **Never in the database.** Application secrets are not stored as data. Secrets that *must* be persisted for operation (e.g. a target's test credentials) are stored in the secrets manager and referenced by **handle**, not value — the DB and evidence store hold handles, never the secret itself.
- **Never in logs or evidence.** Logging and the evidence store run output through secret redaction before write (architecture §2.8). Credentials used in authenticated tests are passed to workers by vault handle and scrubbed from any captured request/response.
- **Rotation & least privilege.** Each secret is scoped to exactly what needs it; rotation is supported without redeploying code; LLM/provider keys are per-environment so a leak is contained.
- **Frontend gets nothing secret.** The Next.js app only ever receives short-lived, user-scoped session tokens — no API keys, no DB access, no provider keys. Anything the browser can read is assumed public.

**Assumption H4:** a managed secrets manager is available in production. *Validation:* if only env vars are available at first, they are injected at runtime by the platform (not baked into images), and migrating to a managed vault is a tracked hardening task.

### (B) As a detection class
Covered by the matrix's **Exposed Secrets** entry (secrets in code/history/responses) — and the engine's own repo is subject to that same scan in CI.

---

## 5. How these fold into the existing plan

- **Threat model:** these four controls are now first-class entries in the platform threat model (they were implied under "least privilege" and "secrets in env vars"; this document makes them concrete and testable).
- **Milestones:** they attach to the early milestones —
  - M1 (Authorization & scope) now also covers **production auth (§2)** and **DB RLS/roles (§3)**.
  - M0/M1 cover **secret management (§4)** from the first commit (`.env.example` + git-ignore + pre-commit secret scan).
  - **Rate limiting (§1)** lands with the first real API surface and tightens around the scan-trigger endpoint in M2.
- **Binary gates (mirroring the evaluation plan):**
  1. Cross-tenant read as the app role returns nothing (RLS works).
  2. No secret-pattern match anywhere in the repo or in logs/evidence samples.
  3. Auth and scan-trigger endpoints return `429` under the configured limit in a load test.
  4. The frontend bundle contains no provider/DB keys (scanned build artifact).

These gates are cheap, deterministic, and run in CI — the same honesty standard the engine holds targets to.
