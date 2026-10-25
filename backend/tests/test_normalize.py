import os
import tempfile

from app.scanners.base import RawFinding, ScannerCategory
from app.scanners.normalize import (
    deduplicate,
    fingerprint,
    normalize_findings,
    redact_secret,
    sanitize_relative_path,
)


class _FakeAdapter:
    name = "fake"
    category = ScannerCategory.sast
    default_evidence_basis = "STATIC_CONFIRMED"
    default_status = "candidate"


def test_sanitize_rejects_traversal():
    with tempfile.TemporaryDirectory() as root:
        assert sanitize_relative_path(root, "../../etc/passwd") is None
        assert sanitize_relative_path(root, "/etc/passwd") is None
        # A legitimate in-root path is accepted and normalized.
        assert sanitize_relative_path(root, "app/main.py") == "app/main.py"


def test_redact_secret_never_returns_full_value():
    raw = "AKIAIOSFODNN7EXAMPLE"
    red = redact_secret(raw)
    assert raw not in red
    assert red.startswith("AKIA")
    assert "*" in red
    assert redact_secret("ab") == "**"
    assert redact_secret(None) == "<redacted>"


def test_normalize_drops_unsafe_paths_and_counts():
    with tempfile.TemporaryDirectory() as root:
        raws = [
            RawFinding(title="good", vuln_class="x", severity="high", confidence="high",
                       location="app/main.py:3"),
            RawFinding(title="bad", vuln_class="x", severity="high", confidence="high",
                       location="../../../etc/passwd"),
        ]
        norm, rejected = normalize_findings(_FakeAdapter(), raws, workspace_root=root)
        assert rejected == 1
        assert len(norm) == 1
        assert norm[0]["location"] == "app/main.py:3"
        assert norm[0]["evidence_basis"] == "STATIC_CONFIRMED"
        assert norm[0]["is_mock"] is False


def test_normalize_redacts_raw_secret():
    with tempfile.TemporaryDirectory() as root:
        rf = RawFinding(title="secret", vuln_class="exposed_secret", severity="high",
                        confidence="medium", location="config.py:1",
                        evidence={"secret": "supersecretvalue"})
        rf._raw_secret = "supersecretvalue"
        norm, _ = normalize_findings(_FakeAdapter(), [rf], workspace_root=root)
        ev = norm[0]["evidence"]
        assert "secret" not in ev
        assert "supersecretvalue" not in str(ev)
        assert ev["redacted_match"].startswith("supe")


def test_deduplicate_merges_provenance():
    fp = fingerprint("xss", "GET /a", "Reflected XSS")
    a = {"fingerprint": fp, "scanner": "s1", "evidence": {}}
    b = {"fingerprint": fp, "scanner": "s2", "evidence": {}}
    unique, removed = deduplicate([a, b])
    assert removed == 1
    assert len(unique) == 1
    assert unique[0]["evidence"]["also_reported_by"] == ["s2"]
