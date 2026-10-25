from app.mock_scanner import generate_mock_findings


def _project_with_scan(client):
    project = client.post(
        "/api/projects",
        json={
            "name": "Findings Target",
            "kind": "web",
            "target_url": "https://app.example.com",
            "authorization_confirmed": True,
        },
    ).json()
    scan = client.post("/api/scans", json={"project_id": project["id"]}).json()
    return project, scan


def test_list_findings_after_scan(client):
    project, scan = _project_with_scan(client)
    r = client.get("/api/findings", params={"scan_id": scan["id"]})
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) == scan["findings_count"]
    # Every finding must be flagged as mock and carry the required fields.
    for f in findings:
        assert f["is_mock"] is True
        assert f["severity"] in {"critical", "high", "medium", "low", "info"}
        assert f["confidence"] in {"high", "medium", "low"}
        assert f["status"] in {
            "candidate", "confirmed", "disproven",
            "inconclusive", "untested", "verification_failed",
        }


def test_findings_distinguish_ai_from_reproduced(client):
    _, scan = _project_with_scan(client)
    findings = client.get("/api/findings", params={"scan_id": scan["id"]}).json()
    bases = {f["evidence_basis"] for f in findings}
    # The sample set must include both an AI-only finding and a reproduced one,
    # so the UI can show the distinction.
    assert "AI_REVIEWED" in bases
    assert "DYNAMIC_REPRODUCED" in bases


def test_get_finding_and_404(client):
    _, scan = _project_with_scan(client)
    findings = client.get("/api/findings", params={"scan_id": scan["id"]}).json()
    fid = findings[0]["id"]

    got = client.get(f"/api/findings/{fid}")
    assert got.status_code == 200
    assert got.json()["id"] == fid

    assert client.get("/api/findings/missing").status_code == 404


def test_generate_fix_placeholder(client):
    _, scan = _project_with_scan(client)
    fid = client.get("/api/findings", params={"scan_id": scan["id"]}).json()[0]["id"]
    r = client.post(f"/api/findings/{fid}/fix")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_implemented"
    assert body["finding_id"] == fid


def test_generate_fix_missing_finding_404(client):
    r = client.post("/api/findings/missing/fix")
    assert r.status_code == 404


def test_mock_scanner_shape():
    findings = generate_mock_findings(project_id="p1", scan_job_id="s1")
    assert len(findings) > 0
    for f in findings:
        assert f["is_mock"] is True
        assert f["project_id"] == "p1"
        assert f["scan_job_id"] == "s1"
        assert f["evidence"]["mock"] is True
