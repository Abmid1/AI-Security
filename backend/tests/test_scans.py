def _make_project(client):
    payload = {
        "name": "Scan Target",
        "kind": "web",
        "target_url": "https://app.example.com",
        "authorization_confirmed": True,
    }
    return client.post("/api/projects", json=payload).json()


def test_start_mock_scan(client):
    project = _make_project(client)
    r = client.post("/api/scans", json={"project_id": project["id"]})
    assert r.status_code == 201
    scan = r.json()
    assert scan["status"] == "completed"
    assert scan["is_mock"] is True
    assert scan["findings_count"] > 0
    assert "MOCK" in (scan["coverage_note"] or "")


def test_start_scan_unknown_project_404(client):
    r = client.post("/api/scans", json={"project_id": "nope"})
    assert r.status_code == 404


def test_list_scans_and_filter(client):
    project = _make_project(client)
    client.post("/api/scans", json={"project_id": project["id"]})

    all_scans = client.get("/api/scans")
    assert all_scans.status_code == 200
    assert len(all_scans.json()) >= 1

    filtered = client.get("/api/scans", params={"project_id": project["id"]})
    assert filtered.status_code == 200
    assert all(s["project_id"] == project["id"] for s in filtered.json())


def test_get_scan(client):
    project = _make_project(client)
    scan = client.post("/api/scans", json={"project_id": project["id"]}).json()
    got = client.get(f"/api/scans/{scan['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == scan["id"]
