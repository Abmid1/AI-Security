# Milestone 2 — Real Scanning (Scanner Integrations)

**Status:** implemented. Real scanning via modular adapters, run in isolated
workers. No automated code modification (that is a later milestone).

This document records what was integrated, how the pieces fit, and — honestly —
what could **not** be integrated in this environment and why.

## Architecture recap

```
API (FastAPI)  --launch-->  isolated worker process  --uses-->  ScannerRegistry
                                                                    │
      ┌───────────────┬───────────────┬───────────────┬───────────┘
      ▼               ▼               ▼               ▼
  BanditAdapter  DetectSecrets   PipAuditAdapter  DynamicSafeAdapter
   (SAST)          (secrets)        (SCA)            (dynamic, passive)
      └───────────────┴───────────────┴───────────────┘
                              │
            normalize (validate paths, redact secrets, dedupe)
                              │
                     persist findings + coverage report
```

- **Modular interface:** every scanner implements `ScannerAdapter`
  (`backend/app/scanners/base.py`). Add or replace a scanner by writing one
  adapter and registering it in `registry.py` — nothing else changes.
- **Isolated workers:** the API spawns `python -m app.workers.run_scan <job_id>`
  as a separate OS process (`services/scan_service.py`). Scans never run inside
  the web server. Tests drive `workers/runner.run_scan_job` in-process.
- **One finding format:** `scanners/normalize.py` converts every adapter's output
  into the canonical `Finding` shape, validating file paths, redacting secrets,
  assigning a dedup fingerprint, and merging duplicates across scanners.
- **Honest coverage:** each scan stores a `coverage` report listing every
  scanner's status (`completed` / `skipped` / `error`) with reasons, plus
  aggregated skipped areas and errors. Missing tools or unreachable targets
  become recorded skips/errors — never silent gaps, never a false "all clear".

## Integrated scanners

| Adapter | Category | Tool | Status | Evidence basis | Notes |
|---|---|---|---|---|---|
| `bandit` | SAST | Bandit | **Working, tested** | `STATIC_CONFIRMED` | Python source only. Non-zero exit (issues found) handled correctly. |
| `detect-secrets` | secrets | detect-secrets | **Working, tested** | `SECRET_MATCH` | We enumerate files ourselves (detect-secrets only scans git-tracked files when given a directory). Only a masked hash reference is stored — never the secret. |
| `pip-audit` | SCA | pip-audit | **Working; needs network** | `DEPENDENCY_MATCH` | Scans `requirements*.txt`. Offline/unreachable → recorded as an **error**, never as "no vulnerabilities". No manifest → recorded **skip**. |
| `dynamic-safe` | dynamic | built-in (httpx) | **Working, tested** | `CONFIG_OBSERVED` | Passive only: GETs the authorized origin and inspects security headers, cookie flags, transport, and banner. No payloads, no crawling, no off-origin redirects. |

### Authorization & scope for dynamic scanning
Dynamic scanning is gated in **code** (`scanners/scope.py`), not by AI instruction:
- The target project must have `authorization_confirmed = true`.
- Requests must stay on the single authorized origin (scheme+host+port).
- Link-local / cloud-metadata addresses (169.254.0.0/16, fe80::/10) are **always**
  blocked, even inside the authorized host (SSRF self-protection).
- Private/loopback hosts are allowed only when the authorized target is itself
  private (local staging), via `allow_private_hosts`.

The worker enforces this before invoking the dynamic adapter, and the adapter
re-checks it (defense in depth). Both paths are covered by tests.

## What could NOT be integrated (and why)

These are deferred honestly rather than faked:

1. **Heavyweight DAST (OWASP ZAP, nuclei).** Not integrated. ZAP needs a Java
   runtime / daemon and nuclei is a Go binary; neither is installable in this
   environment (no Docker, and we avoided unmanaged binary downloads). The
   `dynamic-safe` adapter provides safe passive coverage in the meantime. ZAP/
   nuclei are natural future adapters behind the same interface.
2. **Non-Python SAST.** Bandit covers Python only. JavaScript/TypeScript, Go,
   etc. need a multi-language engine (e.g. Semgrep). Semgrep's Windows support is
   unreliable, so it was not integrated here; it is a candidate adapter on Linux
   CI.
3. **Non-Python dependency scanning.** pip-audit covers Python manifests only.
   npm/yarn, Go modules, etc. need their own adapters (e.g. an OSV-scanner
   adapter). Not integrated yet.
4. **Out-of-band / active dynamic testing** (blind SSRF/XXE, injection with a
   collaborator callback) — intentionally out of scope for a *safe* M2 dynamic
   scanner; it requires a collaborator server and explicit intrusive
   authorization (see the verification engine spec).
5. **Remote git cloning at runtime** works only when `git` is installed and the
   URL is reachable; otherwise the repo workspace step records an error and the
   code/secret/dependency scanners are skipped with that reason. Scanning an
   existing local directory always works.

## Tests

- `test_normalize.py` — path-traversal rejection, secret redaction, fingerprint, dedup.
- `test_scope.py` — origin parsing, metadata blocking, off-origin rejection, private-host gating.
- `test_dynamic_scanner.py` — header/cookie findings via a mock HTTP transport; unauthorized and out-of-scope and metadata targets are skipped with **no** network request.
- `test_repo_scan_integration.py` — runs Bandit + detect-secrets for real against a temporary workspace; asserts normalized, non-mock, deduped findings, redaction, and an honest coverage report (including pip-audit's recorded outcome); and that an unauthorized web project never gets a dynamic scan.

Run them: `cd backend && pytest`.

## Explicitly NOT done in M2
- No automated code modification / patching. The "Generate Fix" button remains a
  placeholder that returns "not implemented".
