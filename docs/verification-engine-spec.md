# Verification Engine Specification

**Status:** Draft v0.1 — design only, not yet implemented.
**Audience:** engineers building the platform (written to be read by a beginner too — plain-language notes are included).
**Scope of this document:** the *Verification Engine* — the part of the platform that takes raw candidate findings and decides, using repeatable technical tests and recorded evidence, whether each one is **confirmed**, **disproven**, or **inconclusive**, and that validates proposed fixes.

Companion documents:
- [`verification-coverage-matrix.md`](./verification-coverage-matrix.md) — per vulnerability-class detection, evidence, and verdict rules.
- [`verification-state-machine.md`](./verification-state-machine.md) — states, transitions, failure handling.
- [`verification-architecture.md`](./verification-architecture.md) — components, interfaces, data flow.
- [`verification-evaluation-plan.md`](./verification-evaluation-plan.md) — benchmarks, ground truth, metrics.

---

## 0. Guiding principle

> **AI investigates. Deterministic code enforces the rules. Technical tests establish evidence. The human controls consequential actions.**

Every design choice below traces back to this sentence. In particular:

- A verdict of **Confirmed** is never produced by an AI model agreeing with itself. It is produced by **deterministic policy code** reading **recorded technical evidence**.
- AI is used to *generate hypotheses* ("this parameter looks injectable; here is a safe probe to try") and to *triage/explain*. It is never the authority on the final verdict.
- Anything consequential — running a potentially intrusive test, applying a patch to the real repo — requires an explicit human authorization record.

**Plain-language version:** the AI is a detective who suggests leads. The lab (tests) produces the evidence. A rulebook (code) decides whether the evidence is enough to convict. A judge (you) signs off on anything that has real-world consequences.

---

## 1. State of the project (inspection result)

As of this writing the repository is an **empty git repository**: no commits, no source files, only the planning documents being authored now. Therefore:

- **Implemented:** nothing.
- **Planned (in the earlier project plan):** the overall app skeleton — Next.js frontend, FastAPI backend, PostgreSQL, isolated workers, adapters, agent pipeline, sandboxed repair. See the original plan for folder structure and milestones.
- **Missing / this document's job:** the detailed verification logic that the earlier plan referred to only at a high level (the "deterministic core": vote counting, evidence rules, AI-reviewed vs. reproduced labelling).

This spec deliberately *supersedes and sharpens* the earlier plan's treatment of verification. Where the earlier plan spoke of "three verifier agents voting," this spec reframes voting as **one weak signal among several**, subordinate to technical evidence. See §3 and §5.

**Assumption A1:** the surrounding platform (scope enforcement, workers, adapters, DB) will be built roughly as the earlier plan described. *Validation:* this spec defines the interfaces the engine needs (§ architecture doc); if the platform diverges, those interfaces are the contract to keep stable.

---

## 2. What the engine is responsible for (and what it is not)

**In scope:**
- Turning candidate findings into verified findings with a verdict and an evidence bundle.
- Running deterministic scanner adapters and controlled, safe verification tests.
- Using AI to propose hypotheses and safe probes *that deterministic code then executes and judges*.
- Deduplicating findings and assigning severity.
- Validating proposed fixes against the original finding and regressions.
- Recording a complete, honest audit trail, including everything it could **not** test.

**Out of scope (owned by other parts of the platform):**
- Deciding *what* to scan and whether the target is authorized (the engine *enforces* authorization at execution time but the authorization *record* is created upstream).
- Generating the patch code itself (the fix agent does that; the engine *validates* it).
- Presenting results in the UI.

**Non-goals (explicit):**
- The engine does **not** attempt to conclusively auto-verify every vulnerability class. Several classes (business logic, some access-control, some race conditions) are explicitly "AI-reviewed / manual-confirm only." Claiming otherwise would be dishonest. See the coverage matrix.

---

## 3. Verdict model (the heart of the engine)

Each finding carries a **verdict** and an **evidence basis**. These are produced by the deterministic **verification-policy evaluator**, not by any model.

### 3.1 Verdicts

| Verdict | Meaning |
|---|---|
| **Confirmed** | A repeatable technical test produced evidence meeting the class-specific confirmation standard (coverage matrix). |
| **Disproven** | A repeatable technical test produced evidence meeting the class-specific *disproof* standard, or the precondition the finding depends on does not hold. |
| **Inconclusive** | Investigated, but evidence did not meet either standard (ambiguous, partial, or the only signal is AI judgement). |
| **Untested** | In scope but no applicable test ran (e.g. no adapter, environment unavailable, test skipped for safety). Distinct from Inconclusive. |
| **Verification failed** | A test was attempted but errored/timed out/crashed before producing usable evidence. **Never** silently upgraded to any other verdict. |

### 3.2 Evidence basis (orthogonal to verdict — answers "how do we know?")

Every verdict records *which kinds of evidence* support it, with independent weight:

| Basis | Source | Strength |
|---|---|---|
| `DYNAMIC_REPRODUCED` | A controlled test against the running target produced the class-specific tell-tale observation. | Strongest for exploitable web vulns. |
| `STATIC_CONFIRMED` | SAST / code analysis located the exact sink + unsanitized source with high confidence. | Strong for code-level classes; weaker for "is it reachable at runtime". |
| `DEPENDENCY_MATCH` | A dependency/version matched a known-vulnerable range in a maintained advisory DB. | Strong for *presence*; weak for *exploitability in this app*. |
| `CONFIG_OBSERVED` | A deterministic check observed a concrete misconfiguration (e.g. a missing/weak header value as returned). | Strong for the fact; impact still needs judgement. |
| `SECRET_MATCH` | A high-confidence secret pattern matched **and** (where possible) a validity check confirmed it. | Pattern alone = medium; validated = strong. |
| `AI_REVIEWED` | AI agents judged it plausible. **No technical reproduction.** | Weakest. Can never by itself produce **Confirmed**. |

### 3.3 The core rule

> **A finding may be labelled `Confirmed` only if its evidence basis includes at least one non-AI basis that meets the confirmation standard for that vulnerability class.** AI agreement adjusts *priority and explanation*, never the verdict.

This is the single most important invariant in the engine. It is enforced in one place: the policy evaluator (§ architecture). It is unit-tested directly (§ evaluation).

### 3.4 Why three "verifier agents" still exist, but differently

The earlier plan had three independent AI verifiers "voting." They remain, but their vote is **only** an `AI_REVIEWED` signal and is subject to §3.3. Their real value is:
1. Proposing the safe probe/test the engine should run (hypothesis generation).
2. Explaining *why* a reproduced result is or isn't impactful (triage).
3. Flagging likely false positives so humans look there first.

Their disagreement never blocks a technically-reproduced Confirmed, and their agreement never creates one.

---

## 4. How a finding flows through the engine

```
 candidate finding (from a specialist agent or an adapter)
        │
        ▼
 [schema validation]  ── fails ─▶ rejected + logged (never reaches a verdict)
        │ ok
        ▼
 [dedup + canonicalize]  ── merges with existing finding if same root cause
        │
        ▼
 [scope + authorization check]  ── not authorized / out of scope ─▶ Untested(reason)
        │ ok
        ▼
 [hypothesis generation (AI)]  → proposes class-appropriate SAFE test(s)
        │
        ▼
 [test planner (code)]  → selects registered tests; checks safety tier + budget
        │
        ▼
 [controlled test execution (worker)]  → collects raw evidence
        │        │
        │        └─ crash/timeout ─▶ Verification failed (recorded, retry policy)
        ▼
 [evidence collection + redaction + storage]
        │
        ▼
 [verification-policy evaluator (code)]  → applies class rules (coverage matrix)
        │
        ▼
 verdict ∈ {Confirmed, Disproven, Inconclusive, Untested} + evidence bundle
        │
        ▼
 [severity assessment (code, CVSS-style inputs)]  → severity + confidence
        │
        ▼
 stored finding → report → (optional) remediation pipeline
```

The detailed per-state rules are in [`verification-state-machine.md`](./verification-state-machine.md).

---

## 5. Evidence standards (summary; full detail per class in the matrix)

For **every** finding that reaches a non-trivial verdict, the engine records an **evidence bundle**:

- `target` and the `authorized_scope` snapshot it was tested under.
- `test_id` and `test_version` (from the versioned test registry).
- `timestamp`, `environment` (which worker image, which target environment — staging vs. production-like).
- `preconditions` and `auth_context` (role/session used, or "unauthenticated").
- `execution_evidence`: sanitized request/response pair(s), or tool output, or code location — **redacted** (see §5.1).
- `expected_vs_observed`: what a non-vulnerable system would do vs. what was seen.
- `reproduction`: the minimal, safe steps/inputs to reproduce (parameterized, pointing at the registered test).
- `impact`: concrete security consequence.
- `verdict_support`: which evidence basis/bases (§3.2) and why the policy evaluator reached its verdict.
- `limitations`: what was *not* established (e.g. "confirmed reflected XSS execution; did not assess auth-context/stored persistence").

**Crucially, the evidence threshold is per-class, not global.** A reflected XSS needs a different proof than a vulnerable dependency, which needs a different proof than an exposed secret. The coverage matrix defines each.

### 5.1 Data minimization & redaction

- Never store customer secrets or personal data unless strictly needed to evidence the finding; when needed, store a redacted/truncated form (e.g. `AKIA****` for a key, a hash for a session token).
- Credentials used for authenticated tests are referenced by vault handle, never copied into evidence.
- Response bodies are truncated and scrubbed with secret-detection before storage.
- Evidence retention has a TTL and is deletable per assessment.

---

## 6. Prioritised implementation roadmap (MVP → later)

### MVP (prove the principle on a narrow slice)
1. **Schema + policy evaluator skeleton** with the §3.3 invariant and its unit tests — *before any scanner is wired in*. This is the trust anchor.
2. **Test registry + versioning** and the evidence-bundle data model.
3. **Two deterministic adapters**: one dependency/CVE scanner (`DEPENDENCY_MATCH`) and one secret scanner (`SECRET_MATCH`) — these give real `Confirmed`/`Disproven` verdicts with the *least* intrusive testing, so they're the safest first win.
4. **Dynamic verification for exactly one web class** end-to-end against a local, intentionally-vulnerable target (reflected XSS *or* SQL injection — choose one). Proves the full dynamic loop with real evidence.
5. **Deduplication + severity** (basic).
6. **State machine + honest coverage reporting** (Untested/Verification-failed surfaced, not hidden).
7. **Audit log** for every test execution and verdict.

### Phase 2
8. Remediation + retest pipeline (§7 of the task): isolated worktree, patch inspection, before/after test, regression run, human approval gate.
9. Expand dynamic verification to the remaining *tool-verifiable* web classes (SSRF, command injection, path traversal, SSTI, XXE, open redirect, header/config, CSRF presence).
10. Authenticated scanning (session/role contexts).

### Phase 3 (advanced / explicitly harder)
11. Access-control/IDOR comparative testing (needs multiple authorized roles + careful oracle design).
12. Business-logic and race-condition *assisted* testing — likely remains `AI_REVIEWED` + manual-confirm; set expectations accordingly.
13. The full reproducible evaluation programme (§ evaluation plan) running in CI against pinned benchmark targets.

---

## 7. Unresolved architectural decisions & risks

These are open questions. Each states the risk and how we'll decide.

1. **Dynamic test environment model.** Do we require a dedicated staging/clone of the target, or allow carefully-rate-limited tests against the authorized live target? *Risk:* testing production can cause harm; testing a clone may not reflect production config. *Decision path:* default to a provided test/staging target; allow live only with an explicit per-assessment authorization flag and non-intrusive tier only. **Assumption A2:** customers can provide a staging target for intrusive classes; validated during pilot.
2. **Scanner adapter licensing/operational model.** Which specific tools ship by default vs. bring-your-own? *Risk:* license terms and false-positive rates vary. *Decision path:* define the adapter interface now; evaluate candidate tools in the evaluation programme before committing defaults.
3. **Idempotency & target mutation.** Some tests change state (create a record, trigger a callback). *Risk:* repeated/partial tests leave residue or corrupt the target. *Decision path:* classify every test by side-effect tier; require cleanup hooks; forbid state-changing tests outside explicit authorization.
4. **Out-of-band verification (SSRF/XXE/blind injection).** These need a collaborator/callback server. *Risk:* standing up and securing a collaborator is non-trivial and itself a target. *Decision path:* treat as Phase 2; until then these classes are `Inconclusive`/`AI_REVIEWED` unless an in-band signal exists.
5. **Severity model source of truth.** CVSS vector vs. a simpler internal scale? *Risk:* over-precise scores imply false rigor. *Decision path:* record CVSS-style inputs but present a coarse band (Critical/High/Med/Low/Info) + confidence.
6. **AI hypothesis safety.** AI proposes probes; how do we stop it proposing a destructive one? *Risk:* prompt injection from target content could try to coax a harmful test. *Decision path:* AI can only *select from / parameterize* registered, safety-tiered tests — it cannot emit free-form commands that execute. Enforced in code (§ architecture).
7. **Ground-truth maintenance.** Benchmark apps change. *Risk:* metrics drift silently. *Decision path:* pin benchmark versions; store expected findings per pinned version; re-baseline deliberately.

---

## 8. Standards references

- **OWASP Web Security Testing Guide (WSTG)** — used as the *methodology* reference for how each class is tested. Individual tests in the registry cite the relevant WSTG test ID.
- **OWASP ASVS 5.0.0** — used as the *requirements* reference. Findings map to the ASVS requirement they violate where applicable.

We do **not** claim OWASP certification, nor complete coverage of either document. Mappings are best-effort aids for reviewers.
