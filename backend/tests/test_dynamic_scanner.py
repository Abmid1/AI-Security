import httpx

from app.scanners.base import ScanLimits, ScanTarget
from app.scanners.dynamic_safe import DynamicSafeAdapter


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _target(**kw):
    base = dict(project_id="p", kind="web", base_url="https://staging.example.com/",
                authorized=True, allowed_origin="https://staging.example.com",
                allow_private_hosts=False)
    base.update(kw)
    return ScanTarget(**base)


def test_missing_headers_and_cookie_flags_detected():
    def handler(request):
        return httpx.Response(
            200,
            headers=[("content-type", "text/html"), ("set-cookie", "sid=abc123")],
        )

    adapter = DynamicSafeAdapter(client=_client(handler))
    outcome = adapter.scan(_target(), ScanLimits())
    assert outcome.status.value == "completed"
    titles = " ".join(f.title for f in outcome.findings)
    assert "Content-Security-Policy" in titles
    assert "Strict-Transport-Security" in titles  # https + absent
    assert "Cookie missing flags" in titles
    # Every dynamic finding is an observed config fact.
    assert all(f.evidence_basis in (None, "CONFIG_OBSERVED") for f in outcome.findings)


def test_unauthorized_is_skipped_without_request():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200)

    adapter = DynamicSafeAdapter(client=_client(handler))
    outcome = adapter.scan(_target(authorized=False), ScanLimits())
    assert outcome.status.value == "skipped"
    assert "not authorized" in outcome.reason
    assert called["n"] == 0  # no network request was made


def test_out_of_scope_is_skipped():
    def handler(request):
        return httpx.Response(200)

    adapter = DynamicSafeAdapter(client=_client(handler))
    # base_url origin differs from the authorized origin.
    outcome = adapter.scan(
        _target(base_url="https://evil.example.com/", allowed_origin="https://staging.example.com"),
        ScanLimits(),
    )
    assert outcome.status.value == "skipped"
    assert "out of scope" in outcome.reason


def test_metadata_target_is_skipped():
    def handler(request):
        return httpx.Response(200)

    adapter = DynamicSafeAdapter(client=_client(handler))
    outcome = adapter.scan(
        _target(base_url="http://169.254.169.254/", allowed_origin="http://169.254.169.254",
                allow_private_hosts=True),
        ScanLimits(),
    )
    assert outcome.status.value == "skipped"
    assert "link-local" in outcome.reason
