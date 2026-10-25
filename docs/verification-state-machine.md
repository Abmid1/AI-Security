# Verification State Machine

**Status:** Draft v0.1 — design only.
**Companion to:** [`verification-engine-spec.md`](./verification-engine-spec.md).

This document defines the explicit states a finding moves through, the transitions allowed, the deterministic rules that trigger them, and — most importantly — how failures are handled so that **nothing broken is ever silently reported as safe**.

**Core safety invariant:**
> A timeout, tool crash, missing evidence, unavailable environment, or AI disagreement must **never** transition a finding into `Confirmed`, `Disproven`, or `Fix verified`. These only arrive from positive, recorded technical evidence evaluated by deterministic policy code.

---

## 1. States

### Verification lifecycle
| State | Meaning | Terminal? |
|---|---|---|
| `CANDIDATE` | A finding exists (from an adapter or specialist agent), schema-valid, deduped. No verification yet. | no |
| `UNDER_INVESTIGATION` | AI hypothesis generation + test planning in progress. | no |
| `VERIFICATION_RUNNING` | One or more registered tests executing in a worker. | no |
| `CONFIRMED` | Evidence met the class confirmation standard (per matrix). | yes* |
| `DISPROVEN` | Evidence met the class disproof standard, or the precondition does not hold. | yes* |
| `INCONCLUSIVE` | Investigated; evidence met neither standard (ambiguous/partial/AI-only). | yes* |
| `UNTESTED` | In scope but no applicable test ran (no adapter, env unavailable, safety-skipped, out of authorized tier). Carries a reason. | yes* |
| `VERIFICATION_FAILED` | A test was attempted but errored/timed out/crashed before usable evidence. Carries error detail + retry count. | yes* |

\* "Terminal for the verification phase" — a finding can still enter the remediation lifecycle below.

### Remediation lifecycle (only for findings a human chose to fix)
| State | Meaning | Terminal? |
|---|---|---|
| `FIX_PROPOSED` | A patch exists in an isolated worktree/clone; not yet tested. | no |
| `FIX_TESTING` | Patch inspection + before/after test + regression suite running. | no |
| `FIX_VERIFIED` | Original vuln reproduced pre-patch **and** no longer reproduces post-patch **and** regressions pass. Awaiting human approval to apply. | no |
| `FIX_FAILED` | Any of: unrelated changes rejected, vuln still reproduces, regressions broke, or tests errored. | no |
| `FIX_APPLIED` | Human approved; patch applied to the real codebase (by the human/their pipeline). | yes |
| `FIX_REJECTED` | Human declined, or fix abandoned. | yes |

---

## 2. Transition diagram

```
                         ┌───────────────────────────────────────────────┐
                         │                                               │
  CANDIDATE ─▶ UNDER_INVESTIGATION ─▶ VERIFICATION_RUNNING ─┬─▶ CONFIRMED │
      │                   │                    │            ├─▶ DISPROVEN │
      │                   │                    │            ├─▶ INCONCLUSIVE
      │                   │                    │            └─▶ VERIFICATION_FAILED
      │                   │                    │                   │
      │                   │                    │                   │ (retry ≤ N)
      │                   │                    └───────────────────┘
      │                   │
      │                   └─▶ UNTESTED (no applicable test / env down / tier not authorized)
      │
      └─▶ UNTESTED (out of scope / not authorized)

   CONFIRMED ──(human clicks Repair)──▶ FIX_PROPOSED ─▶ FIX_TESTING ─┬─▶ FIX_VERIFIED ─(human approves)─▶ FIX_APPLIED
                                                                     └─▶ FIX_FAILED ──(human)──▶ FIX_PROPOSED | FIX_REJECTED
```

Notes:
- Only `CONFIRMED` findings may enter remediation by default. (Config/Phase-2 option: allow high-confidence Inconclusive to be fixed, but the fix test must still establish a pre-patch reproduction or it cannot reach `FIX_VERIFIED`.)
- `VERIFICATION_FAILED` may retry up to **N** times (default N=2) with backoff; after that it stays `VERIFICATION_FAILED`. It never auto-flips to a verdict.
- Re-running verification later creates a **new verification run** attached to the finding (versioned), preserving history; it does not overwrite old evidence.

---

## 3. Transition rules (deterministic)

Each transition is decided by code, with the trigger and guard recorded in the audit log.

| From → To | Trigger | Guard (must all hold) |
|---|---|---|
| CANDIDATE → UNDER_INVESTIGATION | finding dequeued | schema-valid; deduped; in authorized scope |
| CANDIDATE → UNTESTED | scope/authz check | target out of scope OR authorization absent/expired |
| UNDER_INVESTIGATION → VERIFICATION_RUNNING | test plan produced | ≥1 registered test selected; safety tier authorized; budget remaining |
| UNDER_INVESTIGATION → UNTESTED | no runnable test | no applicable registered test OR required env/collaborator unavailable OR required tier not authorized |
| VERIFICATION_RUNNING → CONFIRMED | policy evaluator | class confirmation standard met by ≥1 non-AI basis (matrix) |
| VERIFICATION_RUNNING → DISPROVEN | policy evaluator | class disproof standard met |
| VERIFICATION_RUNNING → INCONCLUSIVE | policy evaluator | tests ran, produced evidence, but neither standard met |
| VERIFICATION_RUNNING → VERIFICATION_FAILED | executor error | test crashed/timed out/could not produce evidence |
| VERIFICATION_FAILED → VERIFICATION_RUNNING | retry | retry_count < N; cause transient |
| CONFIRMED → FIX_PROPOSED | human Repair click | explicit human action; worktree created |
| FIX_PROPOSED → FIX_TESTING | pipeline start | patch present; isolated workspace verified |
| FIX_TESTING → FIX_VERIFIED | fix policy evaluator | (a) pre-patch reproduction recorded; (b) post-patch no reproduction; (c) regressions pass; (d) diff scope-clean |
| FIX_TESTING → FIX_FAILED | fix policy evaluator | any of (a)-(d) not satisfied |
| FIX_VERIFIED → FIX_APPLIED | human approval | explicit human approval record |
| any FIX_* → FIX_REJECTED | human | explicit human action |

---

## 4. The verdict decision rule (expanded)

The policy evaluator, given a finding's class and its collected evidence bundle, computes the verdict with roughly this logic (pseudocode; deterministic, no model call):

```python
def decide_verdict(finding, evidence, class_policy):
    # 1. Executor-level failure dominates — never hide it.
    if evidence.execution_errored and not evidence.has_usable_results:
        return VERIFICATION_FAILED(reason=evidence.error)

    # 2. Confirmation requires a NON-AI basis meeting the class standard.
    confirming = [e for e in evidence.signals
                  if e.basis != "AI_REVIEWED"
                  and class_policy.meets_confirmation(e)]
    if confirming:
        return CONFIRMED(bases=[e.basis for e in confirming])

    # 3. Disproof standard (class-specific).
    if class_policy.meets_disproof(evidence):
        return DISPROVEN()

    # 4. Something ran and produced evidence, but not enough.
    if evidence.any_test_ran:
        return INCONCLUSIVE(note=class_policy.gap_description(evidence))

    # 5. Nothing applicable ran.
    return UNTESTED(reason=evidence.untested_reason)
```

AI signals (`AI_REVIEWED`) are recorded on the finding and influence **priority ordering and the human-facing explanation**, but are never in the `confirming` set. This is the §3.3 invariant of the spec, localized to one function and unit-tested directly.

---

## 5. Failure handling (the required scenarios)

Each row states what the engine does. The theme: degrade to an honest state, reduce coverage, surface it.

| Scenario | Engine behavior |
|---|---|
| **Scanner crashes / times out** | Capture stderr/exit/timeout as evidence; `VERIFICATION_FAILED`; retry ≤ N with backoff; if still failing, stays failed and is counted against coverage. Never becomes Disproven ("no result" ≠ "not vulnerable"). |
| **AI agents disagree** | Disagreement is logged as separate `AI_REVIEWED` signals. It has **no** power to set a verdict. If a non-AI test confirmed, verdict stands regardless; if not, verdict is at most Inconclusive. Disagreement raises the finding's manual-review priority. |
| **Target unavailable** | Health check before/after each test; if unreachable, tests ⇒ `UNTESTED(target_unavailable)` (or `VERIFICATION_FAILED` if it died mid-test). Coverage reduced; report shows the gap. |
| **Authentication fails** | Auth-context tests ⇒ `UNTESTED(auth_unavailable)`; the auth failure itself may be a *candidate finding* (routed separately). Never assume "logged-out = secure." |
| **Test cannot safely run** | Safety tier > authorized tier, or missing isolated env/collaborator ⇒ `UNTESTED(safety_gated)` with the specific reason. |
| **Evidence incomplete** | Policy evaluator returns `INCONCLUSIVE` with a `gap_description`. Partial evidence is stored but not rounded up to Confirmed. |
| **Inconsistent / flaky results** | Tests requiring reproduction run K trials; if results are not consistent across the required threshold, verdict is `INCONCLUSIVE(flaky)` — flakiness is never read as Confirmed. |
| **Target changes during testing** | A content/version fingerprint is taken at run start and checked at key points; on drift, the run is marked `VERIFICATION_FAILED(target_changed)` and must be re-run against a stable snapshot. Mixed-state evidence is discarded. |
| **Verification env differs from production** | The environment (staging/clone/prod-like) is recorded in every evidence bundle; verdicts from a non-production environment are labelled as such, and the report states that results may not transfer to production. Config-dependent classes carry an explicit environment caveat. |

### Coverage accounting (non-negotiable)
Every finding and every planned test contributes to a **coverage ledger**:
- `tested_confirmed`, `tested_disproven`, `tested_inconclusive`
- `untested(reason)`, `failed(reason)`

The report's coverage figure is `tested / applicable`, and **`UNTESTED` + `VERIFICATION_FAILED` reduce coverage**. The engine must never present an assessment with large untested/failed areas as a clean bill of health. The summary explicitly lists what was not tested and why.

---

## 6. Remediation state rules (detail)

`FIX_VERIFIED` requires **all four** of the following, each recorded:
1. **Pre-patch reproduction:** the original vulnerability-specific test reproduced the issue on the *unpatched* code in the isolated workspace. (If it can't be reproduced pre-patch, we cannot prove the patch fixed it → `FIX_FAILED(no_baseline)` and the finding's confidence is revisited.)
2. **Post-patch non-reproduction:** the same test no longer reproduces it on the patched code.
3. **Regression pass:** the relevant existing tests (and a targeted security re-scan) pass on the patched code.
4. **Scope-clean diff:** the patch touches only files/areas related to the finding; unrelated changes are rejected (→ `FIX_FAILED(unrelated_changes)`).

Explicitly: **a successful build or green unit tests alone do NOT satisfy (2).** The security-specific before/after test is mandatory. This is enforced by the fix policy evaluator (deterministic), mirroring §4.

Nothing reaches the real codebase without `FIX_VERIFIED` **and** a separate human approval record (`FIX_APPLIED`). The engine never commits, pushes, or deploys.
