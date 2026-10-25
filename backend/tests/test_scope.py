from app.scanners.scope import ScopePolicy, origin_of


def test_origin_of():
    assert origin_of("https://a.example.com/path?x=1") == "https://a.example.com"
    assert origin_of("http://host:8080/") == "http://host:8080"
    assert origin_of("not a url") is None


def test_metadata_is_never_in_scope():
    p = ScopePolicy("http://169.254.169.254", allow_private_hosts=True)
    d = p.check("http://169.254.169.254/latest/meta-data/")
    assert d.allowed is False
    assert "link-local" in d.reason


def test_off_origin_rejected():
    p = ScopePolicy("https://staging.example.com")
    d = p.check("https://evil.example.com/")
    assert d.allowed is False
    assert "out of scope" in d.reason


def test_private_host_gated():
    # Not allowed by default.
    p = ScopePolicy("http://127.0.0.1:3000", allow_private_hosts=False)
    assert p.check("http://127.0.0.1:3000/").allowed is False
    # Allowed when explicitly permitted (local staging).
    p2 = ScopePolicy("http://127.0.0.1:3000", allow_private_hosts=True)
    assert p2.check("http://127.0.0.1:3000/").allowed is True


def test_public_in_scope_allowed():
    p = ScopePolicy("https://staging.example.com")
    assert p.check("https://staging.example.com/login").allowed is True
