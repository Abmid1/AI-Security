def _web_payload(**overrides):
    payload = {
        "name": "My App",
        "kind": "web",
        "target_url": "https://app.example.com",
        "authorization_confirmed": True,
        "authorization_note": "I own this.",
    }
    payload.update(overrides)
    return payload


def test_create_web_project(client):
    r = client.post("/api/projects", json=_web_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My App"
    assert body["kind"] == "web"
    assert body["authorization_confirmed"] is True
    assert "id" in body


def test_create_project_requires_authorization(client):
    # authorization_confirmed=False must be rejected.
    r = client.post("/api/projects", json=_web_payload(authorization_confirmed=False))
    assert r.status_code == 422


def test_web_project_requires_target_url(client):
    r = client.post("/api/projects", json=_web_payload(target_url=None))
    assert r.status_code == 422


def test_repo_project_requires_repo_url(client):
    payload = {
        "name": "My Repo",
        "kind": "repo",
        "authorization_confirmed": True,
    }
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 422


def test_create_repo_project(client):
    payload = {
        "name": "My Repo",
        "kind": "repo",
        "repo_url": "https://example.com/org/repo.git",
        "authorization_confirmed": True,
    }
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 201
    assert r.json()["kind"] == "repo"


def test_list_and_get_project(client):
    created = client.post("/api/projects", json=_web_payload()).json()
    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert any(p["id"] == created["id"] for p in listing.json())

    got = client.get(f"/api/projects/{created['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]


def test_get_missing_project_404(client):
    r = client.get("/api/projects/does-not-exist")
    assert r.status_code == 404
