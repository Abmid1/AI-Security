# Verification Engine Architecture

**Status:** Draft v0.1 — design only.
**Companion to:** [`verification-engine-spec.md`](./verification-engine-spec.md).

This document defines the engine's components, their responsibilities, interfaces, input/output schemas, failure behavior, and how they integrate with the wider platform.

**Design stance:** small, deterministic core; everything risky (AI, external tools, target interaction) pushed to the edges behind narrow interfaces, running in isolated workers. The trust-critical code (policy evaluator, scope enforcement) is tiny, pure, and heavily tested.

---

## 1. Component map

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                     Orchestrator                         │
                 │  (drives the state machine; calls components; no verdicts)│
                 └──────────────────────────────────────────────────────────┘
          ┌───────────┬───────────┬───────────┬───────────┬───────────┬──────────┐
          ▼           ▼           ▼           ▼           ▼           ▼          ▼
   ┌────────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
   │ Scope &    ││ Target   ││ Test     ││ Hypothesis││ Test     ││ Evidence ││ Policy   │
   │ Authz      ││ Discovery││ Registry ││ Generator ││ Executor ││ Store    ││ Evaluator│
   │ Enforcer   ││ &        ││(versioned││ (AI,      ││(isolated ││(redacted,││(DETER-   │
   │ (code)     ││ Coverage ││ defs)    ││ sandboxed)││ workers) ││ TTL)     ││ MINISTIC)│
   └────────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘
          │           │           │           │           │           │          │
          └───────────┴───────────┴───────────┴───────────┴───────────┴──────────┘
                                          │
                 ┌────────────────────────┼──────────────────────────────┐
                 ▼                        ▼                              ▼
          ┌────────────┐          ┌──────────────┐               ┌──────────────┐
          │ Dedup &    │          │ Remediation &│               │ Audit Log &  │
          │ Severity   │          │ Regression   │               │ Report Gen   │
          │ (code)     │          │ Validator    │               │ (code)       │
          └────────────┘          └──────────────┘               └──────────────┘

   Scanner Adapters (pluggable):  [ SCA ] [ Secrets ] [ DAST ] [ SAST ] [ TLS/Headers ] ...
   LLM Provider (pluggable):      [ one interface; concrete impl behind it ]
```

**Trust boundary:** the **Policy Evaluator**, **Scope & Authz Enforcer**, and **Dedup/Severity** are the deterministic trust core. Adapters, Hypothesis Generator (AI), and Test Executor are *untrusted/at-the-edge*: their output is data to be validated, never commands to obey.

---

## 2. Components in detail

For each: responsibilities, interface, I/O schema (shown as representative JSON), and failure behavior.

### 2.1 Orchestrator
- **Responsibilities:** owns the state machine; sequences component calls; enforces budgets/timeouts; records every transition to the audit log. Makes **no** security verdicts itself.
- **Interface:** `run_verification(finding_id) -> VerificationRun`, `run_remediation(finding_id, patch_ref) -> FixRun`.
- **Failure behavior:** on any component exception, moves the finding to `VERIFICATION_FAILED`/`FIX_FAILED` with the cause; never swallows errors into a success.

### 2.2 Scope & Authorization Enforcer (trust core)
- **Responsibilities:** the *code-enforced* gate. Before any target interaction: verify the target is within an active, unexpired authorization record and scope; verify the requested test's safety tier is authorized; block internal/metadata addresses unless explicitly whitelisted (SSRF self-protection).
- **Interface:** `check(target, test_safety_tier, auth_context) -> Allow | Deny(reason)`.
- **I/O:**
```json
// input
{ "target": {"base_url": "...", "host": "...", "resolved_ips": ["..."]},
  "test": {"id": "...", "safety_tier": "passive|active-safe|active-intrusive|state-changing"},
  "authorization_id": "..." }
// output
{ "decision": "deny", "reason": "safety_tier 'state-changing' not authorized for this assessment" }
```
- **Failure behavior:** fails **closed** — any error, missing record, or ambiguity ⇒ `Deny`. This is deliberate: when unsure, do not touch the target.
- **Key rule:** this check is called by the executor itself (defense in depth), not only by the orchestrator, so a bug upstream cannot cause an unauthorized request.

### 2.3 Target Discovery & Coverage Tracker
- **Responsibilities:** enumerate authorized endpoints/parameters/surfaces; maintain the **coverage ledger** (what is applicable, tested, untested, failed — see state-machine §5).
- **Interface:** `discover(target, scope) -> SurfaceMap`, `record(coverage_event)`.
- **Failure behavior:** discovery errors reduce coverage and are reported; never assume undiscovered = absent.

### 2.4 Test Registry (versioned test definitions)
- **Responsibilities:** the catalog of registered tests. Each test is a **declarative definition**: id, version, vulnerability class, WSTG/ASVS mapping, safety tier, required preconditions, required environment (e.g. collaborator), the adapter/method that runs it, the **oracle** (how to read the result), and the confirmation/disproof standard it contributes to.
- **Interface:** `get(test_id, version)`, `select_for(class, surface, authorized_tiers) -> [TestDef]`.
- **Schema (TestDef):**
```json
{ "id": "xss.reflected.browser-exec",
  "version": "1.3.0",
  "class": "xss",
  "wstg": "WSTG-CLNT-01", "asvs": ["5.3.x"],
  "safety_tier": "active-safe",
  "preconditions": ["reflection_point_found"],
  "requires_env": ["headless_browser"],
  "runner": {"adapter": "dast.browser", "method": "marker_execution"},
  "oracle": {"type": "browser_callback", "basis": "DYNAMIC_REPRODUCED"},
  "contributes_to": {"confirm": "marker_executed", "disprove": "no_execution_with_encoding_or_csp"} }
```
- **Why versioned:** evidence records the exact test version used, so results are reproducible and regressions in the tests themselves are traceable. Changing a test is a deliberate, reviewed version bump.
- **Failure behavior:** unknown/invalid test id ⇒ hard error (never "best-effort guess").

### 2.5 Hypothesis Generator (AI, sandboxed)
- **Responsibilities:** given a surface + candidate, propose *which registered tests* to run and how to parameterize them (within declared bounds). Triage/explain results.
- **Hard constraint (enforced in code):** it may only **select from and parameterize registered tests**. It cannot emit free-form shell/HTTP that executes. Its output is validated against a strict schema; anything else is discarded. This neutralizes prompt-injection-from-target attempts to coax a harmful action.
- **Interface:** `propose(surface, candidate, allowed_tests) -> [TestPlanItem]` where each item references a registered `test_id` + bounded params.
- **Input handling:** all target-derived content (responses, repo files, tool output) is passed as clearly-delimited **untrusted data** with an explicit instruction that it is data, not commands.
- **Failure behavior:** invalid/unschema'd proposal ⇒ dropped + logged; empty proposal ⇒ finding may become `UNTESTED(no_hypothesis)`; LLM error/timeout ⇒ retry then `VERIFICATION_FAILED` or fall back to any deterministic test that applies.

### 2.6 Test Executor (isolated workers)
- **Responsibilities:** actually run the selected tests against the authorized target (or isolated env), collecting raw evidence. Re-checks authorization/scope per request (defense in depth). Enforces per-test timeout, rate limits, side-effect tier, and cleanup.
- **Interface:** `execute(TestPlanItem, auth_context) -> RawEvidence`.
- **Isolation:** runs in a locked-down worker (no secrets beyond what the test needs via vault handle; egress limited to the authorized target + engine collaborator; CPU/mem/time caps).
- **Failure behavior:** crash/timeout ⇒ `RawEvidence{errored:true,...}` (→ `VERIFICATION_FAILED`); never fabricate a result; flaky tests run K trials and report consistency.

### 2.7 Scanner Adapters (pluggable, at the edge)
- **Responsibilities:** wrap established, maintained tools (SCA, secret scanner, DAST, SAST, TLS/header analyzer) behind a common interface. Each normalizes its native output into the engine's `RawEvidence` shape and declares which evidence basis it yields.
- **Interface:**
```python
class ScannerAdapter(Protocol):
    name: str; version: str
    def capabilities(self) -> list[VulnClass]: ...
    def run(self, task: AdapterTask, limits: Limits) -> RawEvidence: ...
```
- **Tool→category fit (candidates to evaluate, not final choices):**
  - **SCA / dependencies:** a maintained dependency/advisory scanner (basis `DEPENDENCY_MATCH`). *Why:* presence detection is a solved, deterministic problem; don't reinvent.
  - **Secrets:** a maintained entropy+pattern secret scanner (basis `SECRET_MATCH`). *Why:* mature rule sets reduce FP.
  - **DAST (web):** a maintained template-based web scanner + a headless-browser harness for XSS execution oracles. *Why:* broad, community-maintained check sets; the browser gives a real execution oracle.
  - **Injection depth:** an established injection tool in non-destructive mode for differential oracles. *Why:* mature oracle logic.
  - **SAST:** a maintained static-analysis engine with security rules (basis `STATIC_CONFIRMED`). *Why:* good at locating sinks/sources at code level.
  - **TLS/headers/config:** a maintained TLS/header analyzer (basis `CONFIG_OBSERVED`).
  - *(Final selections are deferred to the evaluation programme — see open risk #2 in the spec.)*
- **Failure behavior:** adapter exceptions are contained to that task; a crashing adapter never takes down the engine; its failure is recorded and reduces coverage.

### 2.8 Evidence Store
- **Responsibilities:** persist evidence bundles with redaction (secrets/PII scrubbed, bodies truncated), versioned, with a retention TTL and per-assessment deletion. Immutable append (new runs don't overwrite old evidence).
- **Interface:** `put(evidence_bundle) -> evidence_id`, `get(evidence_id)`.
- **Schema (EvidenceBundle):** the fields enumerated in spec §5 (`target`, `test_id`+`version`, `timestamp`, `environment`, `preconditions`, `auth_context`, `execution_evidence` (redacted), `expected_vs_observed`, `reproduction`, `impact`, `verdict_support`, `limitations`).
- **Failure behavior:** storage failure ⇒ the verification cannot be trusted ⇒ `VERIFICATION_FAILED` (we never claim a verdict we can't evidence).

### 2.9 Verification Policy Evaluator (trust core, deterministic)
- **Responsibilities:** the single authority that maps `(class, evidence_bundle)` → verdict, per the matrix and the §4 state-machine rule. **No LLM call.** Pure function → easy to test.
- **Interface:** `evaluate(finding, evidence, class_policy) -> Verdict`.
- **Failure behavior:** if inputs are malformed ⇒ raises; orchestrator maps to `VERIFICATION_FAILED`. Never defaults to a positive verdict.

### 2.10 Dedup & Severity (code)
- **Responsibilities:** canonicalize findings (same root cause/location/parameter ⇒ one finding with multiple observations); assign severity from recorded factors (CVSS-style inputs) presented as a coarse band + confidence.
- **Interface:** `canonical_key(finding) -> key`, `merge(findings) -> Finding`, `severity(finding, evidence) -> (band, confidence)`.
- **Failure behavior:** when unsure whether two findings are the same, keep them **separate** (prefer slight duplication over hiding a distinct issue) and flag for review.

### 2.11 Remediation & Regression Validator
- **Responsibilities:** implement the fix lifecycle (state-machine §6): create isolated worktree/clone, inspect patch for scope-clean diff, run pre-patch reproduction, apply patch, run post-patch test, run regressions + targeted re-scan, compute `FIX_VERIFIED`/`FIX_FAILED` deterministically. Never commits/pushes/deploys.
- **Interface:** `validate_fix(finding, patch_ref, workspace) -> FixResult`.
- **Failure behavior:** any missing step/evidence ⇒ `FIX_FAILED` with reason; a green build/unit run alone is insufficient (enforced).

### 2.12 Audit Log & Report Generator
- **Responsibilities:** append-only audit of authorizations, test executions, verdicts, transitions, approvals; generate reports that **label verdict + evidence basis + coverage gaps honestly** (AI-reviewed vs. reproduced, untested/failed areas listed).
- **Failure behavior:** if audit write fails, the triggering action is aborted (no silent unlogged action for consequential steps).

### 2.13 LLM Provider (pluggable)
- **Interface:** `class LLMProvider(Protocol): def complete(self, request: LLMRequest) -> LLMResponse`. The rest of the engine never references a specific model. Prompt-injection defenses (data-fencing, output-schema validation) live in the callers (2.5), not the provider.

---

## 3. Data flow (one verification run)

1. Orchestrator pulls a `CANDIDATE`, asks **Scope/Authz** to check it → Deny ⇒ `UNTESTED`.
2. **Target Discovery** supplies the relevant surface; **Test Registry** lists applicable tests for the class + authorized tiers.
3. **Hypothesis Generator** (AI) proposes a plan referencing registered tests only; output schema-validated.
4. **Test Executor** runs each plan item in an isolated worker (re-checking authz per request), producing `RawEvidence`.
5. **Evidence Store** persists redacted bundles.
6. **Policy Evaluator** computes the verdict deterministically; **Dedup/Severity** finalizes.
7. **Audit Log** records everything; **Report Gen** renders with honest labels and coverage.
8. (Optional, human-triggered) **Remediation Validator** runs the fix lifecycle; nothing is applied without human approval.

---

## 4. Integration points with the wider platform

| Platform piece | Engine relationship |
|---|---|
| Authorization service (upstream) | Creates the authorization record; the engine's Scope/Authz Enforcer *reads and enforces* it, failing closed. |
| Specialist agents (upstream) | Produce `CANDIDATE` findings; the engine treats their output as untrusted, schema-validated data. |
| Worker/queue infra | The engine's executor and adapters run as isolated workers with resource/egress limits. |
| PostgreSQL | Stores findings, verdicts, evidence metadata, coverage ledger, audit log, state transitions. |
| Fix agent (upstream) | Produces the patch in a worktree; the engine's Remediation Validator judges it. |
| Frontend | Reads reports; triggers human actions (Repair, Approve) that the engine gates on explicit authorization records. |

---

## 5. Cross-cutting failure principles (recap)
- **Fail closed** on authorization/scope.
- **Fail loud** on tool/LLM/storage errors (→ `VERIFICATION_FAILED`, counted against coverage).
- **Never upgrade absence of evidence into a positive verdict.**
- **AI output is data, validated against schema; never executed as instructions.**
- **Deterministic core is small, pure, and the only thing that issues verdicts.**
