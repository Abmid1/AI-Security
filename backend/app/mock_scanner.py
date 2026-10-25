"""MOCK scanner for Milestone 1.

IMPORTANT: this does NOT perform any security scanning. It returns fixed,
illustrative sample findings so the UI and data model can be built and tested.
Every finding it produces is flagged is_mock=True and carries a mock evidence
bundle. Real scanning is a later milestone and is intentionally not present.
"""

from __future__ import annotations

from typing import Any

# A small, varied set of illustrative findings covering the distinctions the
# product cares about: severity, confidence, verdict status, and (crucially)
# the evidence basis that separates AI-reviewed from technically-reproduced.
_SAMPLE_FINDINGS: list[dict[str, Any]] = [
    {
        "title": "Reflected XSS in search parameter",
        "vuln_class": "xss",
        "severity": "high",
        "confidence": "high",
        "status": "confirmed",
        "evidence_basis": "DYNAMIC_REPRODUCED",
        "location": "GET /search?q=",
        "description": (
            "A benign marker injected via the q parameter executed in a headless "
            "browser context. (MOCK sample — not a real result.)"
        ),
        "evidence": {
            "mock": True,
            "note": "Illustrative only; no request was ever sent.",
            "expected_vs_observed": {
                "expected": "marker rendered as inert text",
                "observed": "marker executed in browser context",
            },
            "reproduction": "Registered test xss.reflected.browser-exec (sample)",
        },
    },
    {
        "title": "Vulnerable dependency: example-lib 1.2.0",
        "vuln_class": "vulnerable_dependency",
        "severity": "medium",
        "confidence": "high",
        "status": "confirmed",
        "evidence_basis": "DEPENDENCY_MATCH",
        "location": "requirements.txt",
        "description": (
            "A dependency version falls within a published-vulnerable range. "
            "Confirms PRESENCE of a known-vulnerable component, not exploitability "
            "in this app. (MOCK sample.)"
        ),
        "evidence": {
            "mock": True,
            "advisory": "SAMPLE-0000",
            "note": "Illustrative only; no advisory DB was queried.",
        },
    },
    {
        "title": "Possible IDOR on invoice endpoint",
        "vuln_class": "broken_access_control",
        "severity": "high",
        "confidence": "medium",
        "status": "inconclusive",
        "evidence_basis": "AI_REVIEWED",
        "location": "GET /api/invoices/{id}",
        "description": (
            "An agent flagged a possible access-control gap, but no ground-truth "
            "ownership oracle was available to reproduce it. AI-reviewed only — "
            "not confirmed. (MOCK sample.)"
        ),
        "evidence": {
            "mock": True,
            "note": "AI judgement only; requires manual confirmation.",
        },
    },
    {
        "title": "Missing Strict-Transport-Security header",
        "vuln_class": "security_misconfiguration",
        "severity": "low",
        "confidence": "high",
        "status": "confirmed",
        "evidence_basis": "CONFIG_OBSERVED",
        "location": "Response headers (site-wide)",
        "description": (
            "The HSTS header was absent on observed responses. Low impact on its "
            "own. (MOCK sample.)"
        ),
        "evidence": {
            "mock": True,
            "observed_headers": {"Strict-Transport-Security": "<absent>"},
        },
    },
    {
        "title": "Potential exposed API key in client bundle",
        "vuln_class": "exposed_secret",
        "severity": "critical",
        "confidence": "medium",
        "status": "candidate",
        "evidence_basis": "SECRET_MATCH",
        "location": "frontend bundle (static asset)",
        "description": (
            "A high-entropy string matching an API-key pattern was detected. "
            "Validity not verified. (MOCK sample.)"
        ),
        "evidence": {
            "mock": True,
            "redacted_match": "AKIA****************",
            "note": "Redacted; full secret is never stored.",
        },
    },
    {
        "title": "Missing rate limiting on login endpoint",
        "vuln_class": "missing_rate_limiting",
        "severity": "medium",
        "confidence": "medium",
        "status": "inconclusive",
        "evidence_basis": "DYNAMIC_REPRODUCED",
        "location": "POST /login",
        "description": (
            "A small capped burst of benign requests was accepted without any "
            "observed limiting. Limiting may exist at an edge not visible from "
            "the test vantage point. (MOCK sample.)"
        ),
        "evidence": {
            "mock": True,
            "burst_size": 10,
            "limiting_observed": False,
            "limitation": "edge/CDN limits may not be visible from this vantage",
        },
    },
]


def generate_mock_findings(project_id: str, scan_job_id: str) -> list[dict[str, Any]]:
    """Return a copy of the sample findings tied to the given scan + project.

    This is deterministic sample data. It is NOT a scan.
    """
    results: list[dict[str, Any]] = []
    for sample in _SAMPLE_FINDINGS:
        finding = dict(sample)
        finding["project_id"] = project_id
        finding["scan_job_id"] = scan_job_id
        finding["is_mock"] = True
        results.append(finding)
    return results


MOCK_COVERAGE_NOTE = (
    "MOCK scan. No real testing was performed. Sample findings only. "
    "Real scanning and verification are not implemented in this milestone."
)
