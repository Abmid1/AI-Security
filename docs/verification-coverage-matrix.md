# Verification Coverage Matrix

**Status:** Draft v0.1 — design only.
**Companion to:** [`verification-engine-spec.md`](./verification-engine-spec.md).

This document defines, per vulnerability class, how the engine detects, verifies, and judges findings. It is deliberately honest about what **cannot** be auto-verified.

### How to read each entry

Each class lists the ten required facets from the task:
1. **Meaning** — what the vulnerability is.
2. **Discover first** — what the engine must learn before it can test.
3. **Deterministic detection** — tools/custom checks (the non-AI signal).
4. **AI role** — where AI helps on cases tools miss (hypothesis/triage only).
5. **Confirmation evidence** — the class-specific standard for `Confirmed`.
6. **Disproof** — what makes it `Disproven`.
7. **Inconclusive / Untested** — when we refuse to claim either.
8. **Limitations / FP risk** — honest caveats.
9. **Safe reproduction** — how to reproduce without harm.
10. **Fix test** — how we check a patch actually fixed it.

**Safety note that applies to all classes:** "detection tools" and "safe probes" below refer to using established, maintained scanners and the engine's registered, safety-tiered tests. This document specifies *what evidence counts*, not attack payloads. All active testing requires authorization and respects the safety tiers in the architecture doc. Out-of-band and state-changing tests are gated to Phase 2 + explicit authorization.

### Evidence-basis legend
`DYN` = dynamic reproduced · `STAT` = static confirmed · `DEP` = dependency match · `CFG` = config observed · `SEC` = secret match · `AI` = AI-reviewed only (never sufficient for Confirmed).

### Verifiability tiers (summary)
- **Tier A — strongly auto-verifiable:** dynamic reproduction gives an unambiguous oracle. (Most injection, reflected XSS, path traversal, SSTI, open redirect.)
- **Tier B — auto-detectable, impact needs judgement:** presence is deterministic, exploitability/impact often isn't. (Dependencies, secrets, config/headers, CSRF presence, missing crypto.)
- **Tier C — assisted only, usually manual-confirm:** no reliable automatic oracle. (Business logic, much access-control/IDOR, race conditions, some deserialization.)

---

## SQL / NoSQL Injection — Tier A

1. **Meaning:** untrusted input alters a database query's structure, letting an attacker read/alter data or bypass logic.
2. **Discover first:** endpoints, parameters (query/body/header/cookie), which reach a data store, auth context, DB family if inferable.
3. **Deterministic detection:** established injection scanners (e.g. an sqlmap-style adapter) run in their safe, non-destructive modes against authorized targets; SAST for query construction from tainted input.
4. **AI role:** spot non-obvious injectable parameters, suggest which registered probe class fits the observed stack, explain odd responses. It selects from registered tests only.
5. **Confirmation evidence (`DYN`):** a **differential/boolean or error-based oracle** — a safe, registered probe produces a database-attributable behavioral difference that a benign control input does not (e.g. a structured DB error, or a reliable true/false response divergence), captured as sanitized request/response pairs and repeated to rule out flakiness. For blind cases, a *time-based* differential with repeated trials and controls. (`STAT` alone ⇒ at most Inconclusive unless reachability is also shown.)
6. **Disproof:** inputs are parameterized/escaped at the sink (static) **and** probes show no differential across the oracle set.
7. **Inconclusive/Untested:** only a static signal with no runtime confirmation; WAF interferes and can't be distinguished; no DB reachable.
8. **Limitations/FP risk:** WAFs and generic error pages cause both false pos/neg; time-based oracles are flaky — require repeats + controls.
9. **Safe reproduction:** read-only, idempotent probes only; never destructive statements; rate-limited; recorded as a replayable registered test.
10. **Fix test:** re-run the exact oracle against the patched version → must flip to no-differential; plus a regression test that the endpoint still returns correct data for benign input.
**WSTG:** Input Validation / Injection. **ASVS:** V5 (Validation, Sanitization & Encoding).

---

## Cross-Site Scripting (XSS) — Tier A (reflected/DOM), Tier B→A (stored)

1. **Meaning:** attacker-controlled content executes as script in a victim's browser.
2. **Discover first:** reflection points, output contexts (HTML/attr/JS/URL), sinks in client JS, CSP presence.
3. **Deterministic detection:** DAST reflection checks with a headless browser oracle; SAST for dangerous DOM sinks from tainted sources.
4. **AI role:** identify context-specific encoding gaps, propose which registered marker/context test applies.
5. **Confirmation evidence (`DYN`):** a benign, uniquely-tagged marker injected via the registered test **actually executes in a real browser context** (observed via instrumented headless browser — e.g. a callback from a harmless marker), with the request/response and execution trace recorded. Reflection *without* execution ⇒ Inconclusive, not Confirmed.
6. **Disproof:** output is correctly encoded for its context and/or a strict CSP blocks execution, and the browser oracle shows no execution.
7. **Inconclusive/Untested:** reflected but not shown executing; stored XSS where persistence couldn't be safely tested.
8. **Limitations/FP risk:** reflection ≠ execution; CSP can neutralize; framework auto-escaping often prevents real exploitation.
9. **Safe reproduction:** harmless non-destructive markers only (no real payloads that exfiltrate); isolated browser context.
10. **Fix test:** re-run browser oracle → no execution; confirm encoding/CSP present; regression that legitimate content still renders.
**WSTG:** Client-side / XSS. **ASVS:** V5.

---

## Server-Side Request Forgery (SSRF) — Tier A if in-band, else Tier C

1. **Meaning:** server is coerced into making requests to attacker-chosen destinations (internal services, cloud metadata).
2. **Discover first:** features that fetch URLs/host input; allow-list behavior; cloud environment.
3. **Deterministic detection:** DAST SSRF checks; the engine's **controlled callback server** (out-of-band, Phase 2) to detect blind SSRF.
4. **AI role:** find indirect URL inputs (webhooks, importers, PDF/image fetchers), suggest the safe destination to test (the engine's own collaborator only).
5. **Confirmation evidence:** in-band: response reveals content of an internal resource the client could not reach directly; out-of-band (`DYN`): the controlled collaborator receives a request provably originating from the target with a unique token. **Testing cloud-metadata endpoints is a gated, explicitly-authorized action.**
6. **Disproof:** URL input is strictly allow-listed / resolves only to permitted hosts; no callback received across the test set.
7. **Inconclusive/Untested:** no collaborator available (pre-Phase 2) and no in-band signal ⇒ Inconclusive; metadata test not authorized ⇒ Untested(reason).
8. **Limitations/FP risk:** egress firewalls may block the collaborator (false negative); DNS rebinding nuances.
9. **Safe reproduction:** target only the engine's own collaborator or an authorized benign host; never pivot into real internal services beyond proof-of-reach.
10. **Fix test:** re-run → no callback / allow-list enforced; regression that legitimate URL fetching still works.
**WSTG:** SSRF testing. **ASVS:** V12/V5 (depending on edition mapping).

---

## OS Command Injection — Tier A

1. **Meaning:** input reaches a shell/command execution, allowing arbitrary commands.
2. **Discover first:** features invoking system commands; parameters reaching them.
3. **Deterministic detection:** DAST command-injection checks; SAST for shell execution from tainted input.
4. **AI role:** spot indirect command sinks (filename, archive, conversion features).
5. **Confirmation evidence (`DYN`):** a **harmless, non-destructive** differential proof — e.g. a benign timing or an out-of-band callback from a safe command — repeated with controls; full I/O recorded. **No destructive commands, ever.**
6. **Disproof:** no shell invocation / fully parameterized exec; no differential across probes.
7. **Inconclusive/Untested:** only blind with no collaborator (pre-Phase 2); ambiguous timing.
8. **Limitations/FP risk:** timing oracles flaky; environment command availability varies.
9. **Safe reproduction:** benign commands only (e.g. controlled sleep/echo-to-collaborator); strict rate limits; cleanup verified.
10. **Fix test:** re-run differential → negative; regression on legitimate feature behavior.
**WSTG:** Command Injection. **ASVS:** V5.

---

## Path Traversal / Unauthorized File Access — Tier A

1. **Meaning:** input manipulates file paths to read/write outside the intended directory.
2. **Discover first:** file-serving/upload/download params; base directories.
3. **Deterministic detection:** DAST traversal checks; SAST for path construction from tainted input.
4. **AI role:** find non-obvious file params (templates, locale files, report exports).
5. **Confirmation evidence (`DYN`):** retrieval of a **known-benign out-of-scope file** whose signature is recognizable and that the endpoint should not serve, recorded as request/response. Prefer platform-neutral, non-sensitive marker files over system files.
6. **Disproof:** path canonicalization + allow-listing enforced; traversal attempts resolve inside the jail.
7. **Inconclusive/Untested:** ambiguous responses; write-traversal not safely testable.
8. **Limitations/FP risk:** error pages mimic success; encoding variants.
9. **Safe reproduction:** read-only; target benign marker files; never exfiltrate real sensitive files.
10. **Fix test:** re-run → access denied/jailed; regression on legitimate file access.
**WSTG:** Path Traversal / LFI. **ASVS:** V5/V12.

---

## Broken Access Control / IDOR — Tier C (assisted; comparative when possible)

1. **Meaning:** users can act on resources/functions beyond their authorization (horizontal/vertical).
2. **Discover first:** object identifiers in requests, role model, **≥2 authorized test identities** with known-distinct data.
3. **Deterministic detection:** comparative testing — the engine replays an action authorized for role/user A using role/user B's session and checks whether B improperly obtains A's resource. Requires a reliable **oracle** (known ownership).
4. **AI role:** map which endpoints take object refs; propose which identity pairs to compare; explain whether a difference is a real authz break vs. shared/public data.
5. **Confirmation evidence (`DYN`, comparative):** identity B receives identity A's protected resource (or performs A's privileged action) where the model says it must not, proven by a recorded A/B response differential with known ground-truth ownership supplied as a precondition.
6. **Disproof:** B is denied (403/empty) across the matrix; resource is legitimately shared/public.
7. **Inconclusive/Untested:** no second identity / ownership ground truth provided ⇒ Untested; ambiguous ownership ⇒ Inconclusive. **Default to `AI_REVIEWED` + manual-confirm when a trustworthy oracle is absent.**
8. **Limitations/FP risk:** highest false-positive class for naive automation — "different data" often means "legitimately different," not "broken." Requires ground-truth ownership to avoid crying wolf.
9. **Safe reproduction:** read-only comparisons with provided test accounts; never alter/delete another user's real data.
10. **Fix test:** re-run comparison matrix → B consistently denied; regression that A still accesses A's own resources.
**WSTG:** Authorization testing. **ASVS:** V4 (Access Control).

---

## Authentication & Session Management — Tier B/C

1. **Meaning:** weaknesses in login, credential handling, session lifecycle (fixation, weak tokens, missing lockout, insecure cookies).
2. **Discover first:** auth endpoints, token/cookie mechanics, flags, lifetimes.
3. **Deterministic detection:** check cookie flags (`HttpOnly`/`Secure`/`SameSite`), session-fixation behavior (does the ID rotate on login?), token entropy sampling, transport.
4. **AI role:** reason about flow weaknesses (e.g. password-reset token predictability) and propose registered checks.
5. **Confirmation evidence:** concrete observed facts (`CFG`/`DYN`): e.g. session ID unchanged after privilege change (fixation), cookie lacking security flags as returned, credentials transmitted over cleartext. Each is a specific recorded observation, not a vibe.
6. **Disproof:** the specific weakness check passes (ID rotates, flags present, TLS enforced).
7. **Inconclusive/Untested:** brute-force/lockout testing that could lock real accounts ⇒ Untested unless explicitly authorized on test accounts.
8. **Limitations/FP risk:** many sub-checks; don't conflate "missing SameSite" severity with "no auth at all."
9. **Safe reproduction:** use provided test accounts only; no credential-stuffing against real users; respect lockout.
10. **Fix test:** re-run the specific sub-check → passes; regression on login/logout flows.
**WSTG:** Authentication / Session Management. **ASVS:** V2 (Auth), V3 (Session).

---

## Security Misconfiguration & Insecure HTTP Headers — Tier B

1. **Meaning:** missing hardening — absent/weak security headers, debug endpoints, directory listing, verbose errors, default creds.
2. **Discover first:** responses across representative endpoints, server banners.
3. **Deterministic detection:** header analysis (CSP, HSTS, X-Content-Type-Options, frame controls, etc.), probing for known exposed admin/debug paths via a maintained template scanner.
4. **AI role:** judge *impact* in context (a missing header matters more on an auth'd app).
5. **Confirmation evidence (`CFG`):** the exact header absence/weak value as returned, or the exposed endpoint's response, recorded verbatim (sanitized).
6. **Disproof:** header present with adequate value; endpoint not exposed / returns proper denial.
7. **Inconclusive/Untested:** header present but policy adequacy debatable ⇒ record value, mark impact Inconclusive.
8. **Limitations/FP risk:** low technical FP for *presence*; high risk of *over-rating severity*. Keep most of these Low/Info unless they enable a concrete attack.
9. **Safe reproduction:** passive observation; benign requests only.
10. **Fix test:** re-request → header present/value correct, endpoint locked; no regression to legitimate responses.
**WSTG:** Configuration & Deployment Mgmt. **ASVS:** V14 (Config), V13.

---

## Sensitive-Data Exposure & Cryptographic Weakness — Tier B

1. **Meaning:** sensitive data transmitted/stored without adequate protection, or weak/broken crypto.
2. **Discover first:** TLS config, endpoints returning sensitive fields, storage descriptions (from code), algorithms in use.
3. **Deterministic detection:** TLS/cipher scanner; SAST for weak algorithms (e.g. MD5/SHA1 for passwords, ECB mode, hardcoded IVs); detection of sensitive data in cleartext responses.
4. **AI role:** classify whether returned fields are actually sensitive; reason about key-management smells.
5. **Confirmation evidence:** `CFG`/`STAT` — e.g. TLS negotiates a known-weak protocol/cipher (recorded handshake), or code uses a broken algorithm for a security purpose (exact code location), or a response returns sensitive data over non-TLS.
6. **Disproof:** strong TLS enforced; approved algorithms; no cleartext sensitive data.
7. **Inconclusive/Untested:** at-rest encryption claims not verifiable from outside ⇒ Untested unless code/infra available.
8. **Limitations/FP risk:** "sensitive" is context-dependent; algorithm use may be non-security (e.g. MD5 for a cache key is not a vuln).
9. **Safe reproduction:** passive/offline analysis; don't harvest real sensitive data — record presence, redact content.
10. **Fix test:** re-scan TLS/algorithms → compliant; regression that functionality still works.
**WSTG:** Cryptography / Data Protection. **ASVS:** V6 (Crypto), V8 (Data Protection), V9 (Comms).

---

## Vulnerable Dependencies / Known CVEs — Tier B

1. **Meaning:** the app uses components with publicly known vulnerabilities.
2. **Discover first:** dependency manifests/lockfiles, versions, (ideally) call-graph reachability.
3. **Deterministic detection:** SCA against maintained advisory databases (version-range match); optional reachability analysis.
4. **AI role:** assess whether the vulnerable code path is actually used; summarize advisory relevance.
5. **Confirmation evidence (`DEP`):** a dependency+version falling in a published-vulnerable range per a maintained advisory, with the advisory ID recorded. **This confirms *presence of a known-vulnerable component*, not exploitability in this app** — the verdict and wording must say so.
6. **Disproof:** version outside vulnerable range, or a documented backported fix.
7. **Inconclusive/Untested:** reachability unknown (common) ⇒ Confirmed-presence but exploitability Inconclusive.
8. **Limitations/FP risk:** advisories have false ranges; transitive deps noisy; presence ≠ exploitable.
9. **Safe reproduction:** read manifests only; no active exploit of the CVE by default.
10. **Fix test:** re-run SCA after upgrade → no matching advisory; regression/build + tests still pass.
**WSTG:** Known-vulnerable components. **ASVS:** V14 (Config/Dependencies).

---

## Exposed Secrets — Tier B (→A when a safe validity check exists)

1. **Meaning:** credentials/keys/tokens committed to code or exposed in responses.
2. **Discover first:** repo history, config files, client bundles, responses.
3. **Deterministic detection:** secret scanners (entropy + known-pattern rules) across code/history and fetched content.
4. **AI role:** reduce false positives by judging whether a match is a real secret vs. example/placeholder.
5. **Confirmation evidence (`SEC`):** a high-confidence pattern match (recorded redacted, e.g. prefix + length + location). Where a **safe, read-only validity check** exists for that secret type and is authorized, a liveness result elevates confidence; otherwise it's "potential secret, unverified validity."
6. **Disproof:** match is a documented placeholder/example, or revoked/invalid per a safe check.
7. **Inconclusive/Untested:** real-looking but no safe way to verify validity ⇒ report as potential, validity Untested.
8. **Limitations/FP risk:** example keys, test fixtures, and rotated secrets cause false positives; validity checks can have side effects — only use read-only, authorized ones.
9. **Safe reproduction:** store only redacted evidence; never log the full secret; never use a found secret beyond an authorized liveness check.
10. **Fix test:** re-scan after rotation/removal → no match; confirm secret revoked; regression that app still has working credentials via proper secret management.
**WSTG:** Secret management / data exposure. **ASVS:** V6/V14.

---

## API Security Weaknesses — Tier mixed (A/B/C by sub-type)

1. **Meaning:** API-specific issues — broken object/function-level authorization, mass assignment, excessive data exposure, missing rate limits (aligns with OWASP API Top 10).
2. **Discover first:** API schema (OpenAPI if available), endpoints, object refs, roles.
3. **Deterministic detection:** schema-driven fuzzing/tests; reuse the IDOR comparative method for object/function authorization; detect excessive fields in responses.
4. **AI role:** infer intended vs. actual object ownership and which fields shouldn't be returned/accepted.
5. **Confirmation evidence:** sub-type specific — e.g. object-authz uses the IDOR comparative oracle (`DYN`); excessive-exposure uses a recorded response containing fields the role shouldn't see (needs a ground-truth expectation).
6. **Disproof:** proper authz denial; responses limited to permitted fields.
7. **Inconclusive/Untested:** no schema/ground truth ⇒ Inconclusive/`AI_REVIEWED`.
8. **Limitations/FP risk:** inherits IDOR's FP risk; "excessive" needs a spec of what's expected.
9. **Safe reproduction:** read-only comparative tests with provided identities.
10. **Fix test:** re-run the relevant comparative/field check; regression on legitimate API use.
**WSTG:** API testing. **ASVS:** V4/V1/V13.

---

## Missing Rate Limiting / Resource Controls — Tier B

1. **Meaning:** endpoints accept unlimited requests, enabling brute force, credential stuffing, scraping, or cost/DoS abuse (OWASP API4: unrestricted resource consumption).
2. **Discover first:** sensitive/expensive endpoints (login, password reset, token issue, search, export, anything triggering heavy work), and the observed response to repeated benign requests.
3. **Deterministic detection:** send a **bounded, benign** burst of in-scope requests and observe whether limiting kicks in (`429`/`Retry-After`/backoff) before the configured threshold. Strictly rate-limited and authorized — this is an active-safe tier test, never a flood/DoS.
4. **AI role:** identify which endpoints are sensitive/expensive and therefore *should* be limited.
5. **Confirmation evidence (`DYN`/`CFG`):** a recorded sequence of authorized benign requests to a sensitive endpoint that are all accepted with no limiting, up to a conservative cap — plus the expectation that this endpoint class should be limited. Evidence is the request count + responses, not a stress test.
6. **Disproof:** limiting observed (429/backoff) within an acceptable threshold.
7. **Inconclusive/Untested:** limiting may exist only at an edge not reachable from the test vantage point ⇒ note vantage limitation; cannot safely probe ⇒ Untested.
8. **Limitations/FP risk:** limits may be IP/edge-based and invisible from our vantage (false positive); must never cross into a real DoS to "prove" absence — cap the burst well below harm.
9. **Safe reproduction:** small, capped, authorized bursts only; abort immediately on first sign of limiting or target distress; never sustained load.
10. **Fix test:** re-run the capped burst → limiting now observed within threshold; regression that legitimate normal-rate traffic is unaffected.
**WSTG:** Business Logic / DoS-adjacent testing. **ASVS:** V11/V13. **See also:** our own platform's rate limiting in [`platform-hardening-spec.md`](./platform-hardening-spec.md) §1.

---

## Server-Side Template Injection (SSTI) — Tier A

1. **Meaning:** input is evaluated by a server-side template engine, enabling code/expression execution.
2. **Discover first:** inputs rendered through templates (emails, reports, dynamic pages); engine family.
3. **Deterministic detection:** DAST SSTI checks using benign expression-evaluation markers.
4. **AI role:** identify template-rendered inputs; infer engine from behavior.
5. **Confirmation evidence (`DYN`):** a benign arithmetic/expression marker is **evaluated by the engine** (e.g. a unique math expression returns its computed result), recorded request/response, repeated. Do **not** escalate to code execution for proof.
6. **Disproof:** input rendered literally / auto-escaped; marker not evaluated.
7. **Inconclusive/Untested:** ambiguous reflection without evaluation.
8. **Limitations/FP risk:** some reflections coincidentally resemble evaluation; use unique, control-compared markers.
9. **Safe reproduction:** evaluation-proof markers only; never proceed to RCE payloads.
10. **Fix test:** re-run → marker rendered literally; regression on legitimate templating.
**WSTG:** Injection / SSTI. **ASVS:** V5.

---

## XML External Entity (XXE) — Tier A if in-band / Tier C if blind — "where applicable"

1. **Meaning:** an XML parser processes external entities, enabling file read/SSRF/DoS.
2. **Discover first:** endpoints accepting XML (or formats backed by XML); parser config.
3. **Deterministic detection:** DAST XXE checks; SAST for insecure parser configuration.
4. **AI role:** find XML-backed inputs (SOAP, SVG, docx, config uploads).
5. **Confirmation evidence:** in-band: a benign external entity resolves to recognizable benign content in the response; out-of-band (`DYN`, Phase 2): controlled collaborator receives the parser's request with a unique token. Avoid entity-expansion/DoS tests except in an isolated environment with explicit authorization.
6. **Disproof:** external entity processing disabled; no resolution/callback.
7. **Inconclusive/Untested:** XML not accepted ⇒ Not applicable/Untested; blind with no collaborator ⇒ Inconclusive.
8. **Limitations/FP risk:** modern parsers often disable entities by default (false-positive hypotheses from AI).
9. **Safe reproduction:** benign entities targeting benign files/collaborator only; never DoS a shared environment.
10. **Fix test:** re-run → entity not processed; regression that legitimate XML still parses.
**WSTG:** XXE testing. **ASVS:** V5.

---

## Cross-Site Request Forgery (CSRF) — Tier B (presence), Tier C (true exploitability)

1. **Meaning:** a victim's authenticated browser is tricked into performing a state-changing action.
2. **Discover first:** state-changing endpoints, token mechanism, SameSite cookie posture.
3. **Deterministic detection:** check for anti-CSRF tokens on state-changing requests and whether requests succeed without them / cross-origin; inspect SameSite.
4. **AI role:** identify which actions are state-changing and sensitive.
5. **Confirmation evidence (`DYN`/`CFG`):** a state-changing request is accepted **without** a valid anti-CSRF token and **without** SameSite protection (recorded), on a sensitive action. Presence of protection recorded as the control.
6. **Disproof:** valid token required and verified, or SameSite=Lax/Strict effectively blocks cross-site use.
7. **Inconclusive/Untested:** performing the real state change would alter data ⇒ test on a safe/idempotent action or mark Untested; genuine end-to-end exploit (victim browser) usually not auto-run.
8. **Limitations/FP risk:** SameSite defaults in modern browsers mitigate many cases — don't over-report; distinguish "no token" from "actually exploitable."
9. **Safe reproduction:** prefer read-only/idempotent endpoints or provided test accounts; avoid destructive state changes.
10. **Fix test:** re-run → request rejected without token / SameSite enforced; regression that legitimate requests still work.
**WSTG:** CSRF testing. **ASVS:** V4/V3.

---

## Business-Logic & Workflow Vulnerabilities — Tier C (AI-reviewed + manual-confirm)

1. **Meaning:** abuse of legitimate functionality in unintended ways (e.g. negative quantities, skipping steps, price manipulation).
2. **Discover first:** the intended workflow, invariants, and value constraints — which the engine usually does **not** know without a spec.
3. **Deterministic detection:** limited — can test specific, declared invariants if a human provides them as oracles.
4. **AI role:** primary here — hypothesize invariant violations and propose declared-invariant tests. But its output is `AI_REVIEWED` until a declared oracle reproduces it.
5. **Confirmation evidence:** only when a **human-declared invariant/oracle** exists and a test violates it deterministically. Absent that, no `Confirmed`.
6. **Disproof:** the declared invariant holds under test.
7. **Inconclusive/Untested:** no declared invariants ⇒ `AI_REVIEWED` hypotheses only; explicitly not Confirmed.
8. **Limitations/FP risk:** highest ambiguity; AI readily hallucinates "logic flaws." This class is honest about needing humans.
9. **Safe reproduction:** only against declared, safe-to-exercise workflows with test accounts.
10. **Fix test:** re-run the declared-invariant test; regression on the workflow.
**WSTG:** Business Logic testing. **ASVS:** V11 (Business Logic).

---

## Insecure Deserialization — Tier C (mostly static + manual)

1. **Meaning:** untrusted serialized data is deserialized unsafely, potentially enabling RCE/object injection.
2. **Discover first:** endpoints accepting serialized formats; libraries used.
3. **Deterministic detection:** SAST for dangerous deserialization APIs on tainted input; detection of serialized formats in requests.
4. **AI role:** identify serialized inputs and dangerous sinks.
5. **Confirmation evidence:** generally **not** safely auto-exploitable. `STAT` (dangerous API on tainted input, exact location) supports **Inconclusive/AI-reviewed** with high-priority manual review. A safe, non-destructive differential (if one genuinely exists for the stack) could raise it, but RCE proof is **not** attempted automatically.
6. **Disproof:** safe deserialization (allow-listed types, safe formats) at the sink.
7. **Inconclusive/Untested:** the normal outcome — flag for manual expert review.
8. **Limitations/FP risk:** exploitability is gadget-chain dependent; static presence ≠ exploitable.
9. **Safe reproduction:** no destructive gadget execution; static evidence + manual review.
10. **Fix test:** static re-check that unsafe deserialization is removed/constrained; regression tests.
**WSTG:** Deserialization testing. **ASVS:** V5.

---

## Race Conditions — Tier C (feasibility-gated)

1. **Meaning:** concurrent requests violate an invariant (e.g. double-spend, limit bypass).
2. **Discover first:** operations with shared-state invariants (balances, coupons, stock) and a declared invariant/oracle.
3. **Deterministic detection:** a controlled concurrency test (parallel requests) against a declared invariant, in an isolated environment.
4. **AI role:** hypothesize which operations are race-prone.
5. **Confirmation evidence (`DYN`, feasibility-gated):** a declared invariant is violated under controlled concurrency, reproduced across repeated trials, in an isolated/test environment with explicit authorization.
6. **Disproof:** invariant holds under repeated concurrency tests.
7. **Inconclusive/Untested:** no declared invariant, no isolated environment, or non-reproducible ⇒ Inconclusive/Untested. Flakiness must not be read as Confirmed.
8. **Limitations/FP risk:** timing-dependent, environment-sensitive, easy to misattribute; requires isolation to avoid harming real data.
9. **Safe reproduction:** isolated test environment + test accounts only; never race real financial/production operations.
10. **Fix test:** re-run concurrency test → invariant holds; regression on normal sequential behavior.
**WSTG:** Business Logic / concurrency. **ASVS:** V11.

---

## Summary: what is and isn't auto-verifiable (honesty table)

| Class | Can be auto-Confirmed with evidence? | Default when evidence is thin |
|---|---|---|
| SQLi/NoSQLi, Cmd injection, SSTI, Path traversal, Reflected XSS | Yes (dynamic oracle) | Inconclusive |
| SSRF, XXE | Yes **if** in-band or (Phase 2) collaborator | Inconclusive/Untested |
| Dependencies/CVEs | Presence yes; exploitability usually no | Confirmed-presence + Inconclusive-exploitability |
| Secrets | Presence yes; validity sometimes | Potential (validity Untested) |
| Config/Headers, Auth/Session, Crypto/Data exposure, CSRF presence, Rate limiting | Facts yes; impact judged | Record fact, judge severity |
| IDOR/Access-control, API object-authz | Only with a ground-truth oracle | AI-reviewed + manual-confirm |
| Business logic, Race conditions, Deserialization RCE | Rarely/No automatically | AI-reviewed + manual-confirm |

This table is the engine's promise: it will not pretend Tier C is Tier A.
