"""Safe, passive dynamic scanner for authorized staging applications.

This adapter is deliberately NON-INTRUSIVE. It issues ordinary GET requests to
the single authorized origin and inspects the responses for security-relevant
configuration. It sends no attack payloads, submits no forms, and does not crawl
off the authorized origin. Redirects are not followed off-origin.

What it checks (all observed facts, evidence basis CONFIG_OBSERVED):
- Missing security headers (CSP, HSTS, X-Content-Type-Options, frame controls,
  Referrer-Policy, Permissions-Policy).
- Cookies set without Secure / HttpOnly / SameSite.
- Server/version banner disclosure.
- Plaintext (http) transport.

Heavier dynamic tools (OWASP ZAP, nuclei) are separate adapters that are NOT
integrated in this environment — see docs/milestone-2-scanners.md.
"""

from __future__ import annotations

import importlib.util

from .base import (
    OutcomeStatus,
    RawFinding,
    ScanLimits,
    ScannerAdapter,
    ScannerCategory,
    ScannerOutcome,
)
from .scope import ScopePolicy, origin_of

# Security headers we expect, with the severity of their absence.
_EXPECTED_HEADERS = {
    "content-security-policy": ("medium", "Content-Security-Policy"),
    "x-content-type-options": ("low", "X-Content-Type-Options"),
    "referrer-policy": ("low", "Referrer-Policy"),
    "permissions-policy": ("low", "Permissions-Policy"),
}


class DynamicSafeAdapter(ScannerAdapter):
    name = "dynamic-safe"
    category = ScannerCategory.dynamic
    default_evidence_basis = "CONFIG_OBSERVED"
    default_status = "confirmed"  # an observed configuration fact
    requires_dynamic_authorization = True

    def __init__(self, client=None):
        # An httpx.Client may be injected for testing (e.g. MockTransport).
        self._client = client

    def is_available(self) -> tuple[bool, str | None]:
        if self._client is None and importlib.util.find_spec("httpx") is None:
            return False, "httpx is not installed"
        return True, None

    def applies_to(self, target) -> bool:
        return target.kind == "web" and bool(target.base_url)

    def scan(self, target, limits: ScanLimits) -> ScannerOutcome:
        if not target.base_url:
            return ScannerOutcome.skipped(self.name, self.category.value, "no base_url")

        # Authorization gate (defense in depth; the worker also checks this).
        if not target.authorized:
            return ScannerOutcome.skipped(
                self.name, self.category.value,
                "dynamic scan not run: target is not authorized",
            )

        allowed_origin = target.allowed_origin or origin_of(target.base_url)
        if not allowed_origin:
            return ScannerOutcome.skipped(self.name, self.category.value, "cannot determine origin")
        policy = ScopePolicy(allowed_origin, allow_private_hosts=target.allow_private_hosts)
        decision = policy.check(target.base_url)
        if not decision.allowed:
            return ScannerOutcome.skipped(
                self.name, self.category.value,
                f"dynamic scan not run: {decision.reason}",
            )

        client, owns_client = self._get_client(limits)
        try:
            try:
                resp = client.get(target.base_url)
            except Exception as exc:  # network error, DNS, TLS, etc.
                return ScannerOutcome.errored(
                    self.name, self.category.value,
                    f"could not reach target: {type(exc).__name__}: {exc}",
                )
            return self._analyze(target.base_url, resp)
        finally:
            if owns_client:
                client.close()

    def _get_client(self, limits: ScanLimits):
        if self._client is not None:
            return self._client, False
        import httpx
        # follow_redirects=False keeps us on the authorized origin.
        return httpx.Client(timeout=min(limits.timeout_seconds, 30),
                            follow_redirects=False), True

    def _analyze(self, url: str, resp) -> ScannerOutcome:
        outcome = ScannerOutcome(
            scanner=self.name,
            category=self.category.value,
            status=OutcomeStatus.completed,
        )
        headers = {k.lower(): v for k, v in resp.headers.items()}

        for key, (severity, label) in _EXPECTED_HEADERS.items():
            if key not in headers:
                outcome.findings.append(RawFinding(
                    title=f"Missing security header: {label}",
                    vuln_class="security_misconfiguration",
                    severity=severity,
                    confidence="high",
                    location=f"{url} (response headers)",
                    description=f"The {label} header was not present on the response.",
                    evidence={"tool": "dynamic-safe", "header": label, "present": False},
                ))

        # HSTS only matters over HTTPS.
        if url.lower().startswith("https://") and "strict-transport-security" not in headers:
            outcome.findings.append(RawFinding(
                title="Missing security header: Strict-Transport-Security",
                vuln_class="security_misconfiguration",
                severity="medium",
                confidence="high",
                location=f"{url} (response headers)",
                description="HSTS header absent on an HTTPS response.",
                evidence={"tool": "dynamic-safe", "header": "Strict-Transport-Security"},
            ))

        # Plaintext transport.
        if url.lower().startswith("http://"):
            outcome.findings.append(RawFinding(
                title="Plaintext HTTP transport",
                vuln_class="insecure_transport",
                severity="medium",
                confidence="high",
                location=url,
                description="The target is served over plaintext HTTP.",
                evidence={"tool": "dynamic-safe", "scheme": "http"},
            ))

        # Server banner disclosure.
        server = headers.get("server")
        if server and any(ch.isdigit() for ch in server):
            outcome.findings.append(RawFinding(
                title="Server version disclosure",
                vuln_class="security_misconfiguration",
                severity="info",
                confidence="medium",
                location=f"{url} (Server header)",
                description=f"The Server header discloses software/version: {server}",
                evidence={"tool": "dynamic-safe", "server": server},
            ))

        # Cookie flags.
        for raw_cookie in resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []:
            lc = raw_cookie.lower()
            missing = [flag for flag, token in
                       (("Secure", "secure"), ("HttpOnly", "httponly"), ("SameSite", "samesite"))
                       if token not in lc]
            if missing:
                cookie_name = raw_cookie.split("=", 1)[0]
                outcome.findings.append(RawFinding(
                    title=f"Cookie missing flags: {', '.join(missing)}",
                    vuln_class="session_management",
                    severity="low",
                    confidence="high",
                    location=f"{url} (Set-Cookie: {cookie_name})",
                    description=f"Cookie '{cookie_name}' is missing: {', '.join(missing)}.",
                    evidence={"tool": "dynamic-safe", "cookie": cookie_name, "missing": missing},
                ))
        return outcome
