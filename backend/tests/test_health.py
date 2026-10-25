def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["milestone"] == "M1"
    assert body["mock_mode"] is True


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    assert "version" in body


def test_health_db(client):
    r = client.get("/api/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "reachable"
