# Verification Evaluation Plan

**Status:** Draft v0.1 — design only. **No results exist yet; no numbers are claimed.**
**Companion to:** [`verification-engine-spec.md`](./verification-engine-spec.md).

This document defines a *reproducible programme* for measuring whether the Verification Engine actually works — how well it confirms real vulnerabilities, avoids false alarms, and produces honest coverage. It defines targets, ground truth, metrics, and acceptance criteria **before** any implementation, so results can't be cherry-picked afterward.

**Honesty commitment:** we do not publish or claim any metric until the programme has run against pinned targets. Placeholders below are explicitly marked `TBD-after-run`.

---

## 1. Benchmark targets (intentionally vulnerable, maintained)

All targets run **locally in isolated containers** — never a third party's live system. Each is pinned to a specific version so ground truth stays stable.

| Target | Role | Notes |
|---|---|---|
| **OWASP Juice Shop** (pinned version) | Primary broad web benchmark | Rich, documented vuln set across many classes; actively maintained. |
| **OWASP WebGoat** (pinned) | Guided lessons per class | Good for class-specific positive cases. |
| **A deliberately-vulnerable API app** (pinned, e.g. an OWASP API-focused target) | API/IDOR/object-authz cases | Exercises the comparative-oracle path. |
| **A SAST/code benchmark corpus** (pinned) | Static-analysis cases | Known source-level sink/source samples. |
| **A dependency-vuln fixture repo** (pinned manifests) | SCA cases | Known-vulnerable + known-safe dependency sets. |
| **A secrets fixture repo** (synthetic) | Secret detection | Planted *fake* secrets + decoy placeholders; **no real credentials.** |
| **Custom "hard cases" harness** (we build) | Negatives, decoys, flaky/timeout cases | See §3. |

**Assumption E1:** these targets remain available and installable at pinned versions. *Validation:* vendor/pin each target image in the eval repo; CI fails if a pin is unresolvable, prompting a deliberate re-baseline.

---

## 2. Establishing ground truth

Ground truth = the agreed list of what is *actually* true for each pinned target, so we can score the engine against it.

1. **Start from published documentation.** Juice Shop/WebGoat publish their intended vulnerabilities; fixture repos define their planted issues. These seed the expected set.
2. **Independent manual verification.** For each expected finding we care about, a human (ideally two, independently) confirms it is reproducible in our pinned container and records the class, location, and a reference reproduction. Disagreements are resolved by a third reviewer and documented.
3. **Define the applicable set per class per target.** Not every class applies to every target; the "applicable" denominator is fixed and recorded (so coverage math is honest).
4. **Record expected negatives and decoys** (things that look vulnerable but are not) explicitly.
5. **Freeze** the ground-truth file alongside the pinned target version. Changing it requires a reviewed re-baseline.

**Assumption E2:** published vuln lists are accurate for our pinned version. *Validation:* the independent manual step (2) overrides docs on conflict; we trust reproduction over documentation.

---

## 3. Test-case design (the matrix of scenarios)

The programme must include, for each applicable class:

- **Positive cases** — a real vulnerability that should be `Confirmed` (with reproducible evidence).
- **Negative cases** — a safe-but-similar surface that should be `Disproven` or not reported (measures false positives).
- **Decoys** — intentionally misleading surfaces (e.g. reflected-but-encoded input, a placeholder that looks like a secret) that should **not** be Confirmed.
- **Static cases** — code-level issues to exercise SAST paths.
- **Dynamic cases** — runtime-reproducible issues.
- **Authenticated vs. unauthenticated** — same surface under different auth contexts (especially for access-control).
- **Ambiguous-evidence cases** — where the correct answer is `Inconclusive` (we score whether the engine correctly refuses to claim Confirmed/Disproven).
- **Tool-failure cases** — targets/tests engineered to time out or crash, where the correct outcome is `VERIFICATION_FAILED`/`UNTESTED` and *reduced coverage* — **not** a clean result.
- **Fix & regression cases** — a known vuln + a known-correct fix and a known-bad fix, to score the remediation pipeline (does it pass the good fix and fail the bad one? does it catch a fix that breaks functionality?).

The "correct outcome" for ambiguous/failure cases is as important as for positives — a key claim of this engine is that it degrades honestly.

---

## 4. Metrics (defined precisely; values `TBD-after-run`)

Scored against frozen ground truth, per class and overall.

| Metric | Definition |
|---|---|
| **Precision** | Confirmed findings that are true positives ÷ all Confirmed findings. |
| **Recall** | True vulnerabilities (applicable set) correctly Confirmed ÷ all true vulnerabilities. |
| **False-positive rate** | Things reported Confirmed that are not real ÷ reported Confirmed. |
| **False-negative rate** | Real vulnerabilities missed (not Confirmed) ÷ all real vulnerabilities. |
| **Verification success rate** | Findings reaching a decisive verdict (Confirmed/Disproven) ÷ findings where a decisive verdict was *expected*. |
| **Reproducible-evidence rate** | Confirmed findings with a stored, replayable evidence bundle ÷ all Confirmed. (Target: 100% — a Confirmed without reproducible evidence is a bug in the engine.) |
| **Coverage** | Applicable tests executed ÷ applicable tests defined (untested/failed reduce it). |
| **Honest-degradation score** | Ambiguous/failure cases given the correct non-positive outcome ÷ all such cases. |
| **Fix success rate** | Good fixes correctly reaching `FIX_VERIFIED` ÷ good-fix cases. |
| **Bad-fix rejection rate** | Bad/ineffective fixes correctly `FIX_FAILED` ÷ bad-fix cases. |
| **Regression-catch rate** | Fixes that break functionality correctly caught ÷ such cases. |
| **Runtime per assessment** | Wall-clock per target run. |
| **Cost per assessment** | LLM + compute cost per target run. |

Report per-class breakdowns, not just a single blended number — a high overall score can hide a weak class.

---

## 5. Acceptance criteria (gates, thresholds `TBD`)

These are *shapes* of criteria; the numeric thresholds are set deliberately after an initial baseline run, then held fixed.

- **Invariant gate (binary, must pass):** reproducible-evidence rate for Confirmed = **100%**. Any Confirmed lacking a replayable non-AI evidence bundle fails the build. (Directly tests spec §3.3.)
- **Honest-degradation gate (binary, must pass):** every engineered tool-failure/timeout case results in `VERIFICATION_FAILED`/`UNTESTED` and reduced coverage — **zero** such cases reported as clean/Confirmed.
- **Bad-fix gate (binary, must pass):** **zero** bad/ineffective fixes reach `FIX_VERIFIED`.
- **Precision/recall gates (tunable):** per-class minimums set after baseline; precision is weighted higher than recall for this tool (a confident false alarm is worse than a cautious miss, given the human-in-the-loop model).
- **Regression gate (tunable):** minimum regression-catch rate.

The binary gates encode the engine's core promises and are non-negotiable; the tunable gates track quality over time.

---

## 6. Reproducibility of the evaluation itself

- **Pinned everything:** target images, test registry versions, adapter versions, model identifier, and the ground-truth file are all version-pinned and committed to an `eval/` area.
- **One command to run:** `make eval` (or equivalent) stands up the pinned targets in isolation, runs the engine, scores against ground truth, and emits a report + raw evidence.
- **CI integration (Phase 3):** the programme runs in CI on a schedule and on engine changes; the binary gates block merges.
- **Independent reproduction:** because targets and ground truth are pinned and the run is scripted, a second engineer on a clean machine can reproduce the numbers. Any divergence is itself a finding.
- **No fabricated numbers:** until `make eval` runs, every metric reads `TBD-after-run`. Reports generated before a run must say so.

---

## 7. What this programme does *not* prove (stated honestly)

- Good scores on intentionally-vulnerable benchmarks do **not** guarantee equivalent performance on real, unfamiliar applications. Benchmarks are necessary, not sufficient.
- Classes marked Tier C in the coverage matrix (business logic, much IDOR, race conditions, deserialization RCE) will likely show lower automatic recall; the programme measures this rather than hiding it, and the acceptance criteria for those classes reflect "assisted," not "autonomous."
- Cost/runtime measured locally may differ from production scale.

These limitations are reported alongside any results, every time.
