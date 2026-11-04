"""End-to-end through the HTTP API with the sample engine: billing, gating, HR approval, privacy."""
import time

import pytest
from fastapi.testclient import TestClient

from app import engine
from app.main import app

CV = ("Jane Doe. Senior backend engineer.\nBSc Computer Science, University of Jordan.\n"
      "2018 - present: Python, FastAPI, PostgreSQL and AWS for a payments company. 6 years of experience.\n"
      "Certified AWS Solutions Architect. Project: migrated a monolith to services.")
JOB = {
    "title": "Senior Backend Engineer", "company": "Acme", "passing_score": 60, "currency": "USD",
    "description": "We need a senior backend engineer with Python, FastAPI, PostgreSQL and AWS experience to build payment services.",
    "salary_min": 3000, "salary_max": 4000, "required_documents": ["Passport copy", "CV"], "language": "en",
}
TRANSCRIPT = "\n".join(f"Q{i}: Question {i}?\nA{i}: " + "I designed and shipped this with measurable results and tradeoffs. " * 3 for i in range(1, 11))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def auth(client, email, name="Tester"):
    r = client.post("/api/auth/register", json={"email": email, "name": name, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def wait(client, h, cid, stage, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        s = client.get(f"/api/candidates/{cid}", headers=h).json()["stages"].get(stage)
        if s and s["status"] in ("completed", "failed"):
            return s
        time.sleep(0.2)
    raise AssertionError(f"{stage} did not finish")


def add_candidate(client, h, job_id, name="Jane Doe", **extra):
    r = client.post(f"/api/jobs/{job_id}/candidates", headers=h, data={"name": name, "email": "jane@example.com", "cv_text": CV, **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_full_pipeline_billing_and_gates(client):
    h = auth(client, "owner@example.com")
    assert client.get("/api/me", headers=h).json()["credits"] == 1
    job = client.post("/api/jobs", headers=h, json=JOB).json()
    cid = add_candidate(client, h, job["id"], expected_salary="4500", currency="USD")

    # stages that need earlier work refuse to run
    assert client.post(f"/api/candidates/{cid}/stages/evaluate", headers=h).status_code == 409
    assert client.post(f"/api/candidates/{cid}/stages/email:not_passed", headers=h).status_code == 409
    assert client.post(f"/api/candidates/{cid}/decision", headers=h, json={"outcome": "fail"}).status_code == 409

    # screening costs the only credit
    assert client.post(f"/api/candidates/{cid}/stages/screen", headers=h).status_code == 200
    screen = wait(client, h, cid, "screen")
    assert screen["status"] == "completed" and screen["is_demo"]
    res = screen["result"]
    assert 0 <= res["screening"]["score"] <= 100 and len(res["questions"]["items"]) == 10
    assert client.get("/api/me", headers=h).json()["credits"] == 0
    # re-running the same candidate is free, a second candidate is not
    cid2 = add_candidate(client, h, job["id"], name="Second Person")
    assert client.post(f"/api/candidates/{cid2}/stages/screen", headers=h).status_code == 402

    # interview needs a transcript, then the score is computed from ten 0-10 answers
    assert client.post(f"/api/candidates/{cid}/stages/evaluate", headers=h).status_code == 409
    client.patch(f"/api/candidates/{cid}", headers=h, json={"transcript": TRANSCRIPT})
    assert client.post(f"/api/candidates/{cid}/stages/evaluate", headers=h).status_code == 200
    ev = wait(client, h, cid, "evaluate")["result"]
    assert ev["answers_found"] == 10 and ev["interview_score"] == sum(i["score"] for i in ev["items"])
    assert ev["requires_hr_approval"] and ev["decision"] in ("Pass", "Fail", "Manual Review")

    # a rejection email needs a matching HR decision, and shows approval state live
    assert client.post(f"/api/candidates/{cid}/stages/email:not_passed", headers=h).status_code == 409
    client.post(f"/api/candidates/{cid}/decision", headers=h, json={"outcome": "fail", "note": "salary too high"})
    assert client.post(f"/api/candidates/{cid}/stages/email:not_passed", headers=h).status_code == 200
    mail = wait(client, h, cid, "email:not_passed")["result"]
    assert mail["requires_hr_approval"] and mail["hr_approved"]
    client.post(f"/api/candidates/{cid}/decision", headers=h, json={"outcome": "hold"})
    detail = client.get(f"/api/candidates/{cid}", headers=h).json()
    assert detail["stages"]["email:not_passed"]["result"]["hr_approved"] is False
    assert client.post(f"/api/candidates/{cid}/stages/email:final_hiring", headers=h).status_code == 409

    # salary classification is code, not model
    assert client.post(f"/api/candidates/{cid}/stages/salary", headers=h).status_code == 200
    assert wait(client, h, cid, "salary")["result"]["scenario"] == "above"

    # documents: completeness only
    client.patch(f"/api/candidates/{cid}", headers=h, json={"submitted_documents": ["jane_cv.pdf"]})
    assert client.post(f"/api/candidates/{cid}/stages/documents", headers=h).status_code == 200
    docs = wait(client, h, cid, "documents")["result"]
    assert docs["missing"] == ["Passport copy"] and not docs["complete"] and docs["reminder_body"]
    assert client.post(f"/api/candidates/{cid}/stages/email:missing_documents", headers=h).status_code == 200

    # report + csv
    assert client.post(f"/api/candidates/{cid}/stages/report", headers=h).status_code == 200
    wait(client, h, cid, "report")
    md = client.get(f"/api/candidates/{cid}/report.md", headers=h)
    assert md.status_code == 200 and "requires explicit HR approval" in md.text
    csv = client.get(f"/api/jobs/{job['id']}/export.csv", headers=h)
    assert csv.status_code == 200 and "Jane Doe" in csv.text

    # privacy: another account sees nothing, even an admin
    other = auth(client, "other@example.com")
    admin = auth(client, "admin@example.com")
    for hh in (other, admin):
        assert client.get(f"/api/candidates/{cid}", headers=hh).status_code == 404
        assert client.get(f"/api/jobs/{job['id']}", headers=hh).status_code == 404
        assert client.post(f"/api/candidates/{cid}/stages/screen", headers=hh).status_code == 404

    # running stage blocks deletion, finished candidate can be erased
    assert client.delete(f"/api/candidates/{cid}", headers=h).status_code == 200
    assert client.get(f"/api/candidates/{cid}", headers=h).status_code == 404


def test_purchase_and_admin_flow(client):
    h = auth(client, "buyer@example.com")
    p = client.post("/api/purchases", headers=h, json={"package": "starter"}).json()
    assert p["status"] == "awaiting_payment" and p["credits"] == 10
    assert client.post("/api/purchases", headers=h, json={"package": "nope"}).status_code == 422
    paid = client.post(f"/api/purchases/{p['id']}/pay", headers=h, json={}).json()
    assert paid["status"] == "paid"
    assert client.get("/api/me", headers=h).json()["credits"] == 11
    # paying twice cannot grant credits twice
    assert client.post(f"/api/purchases/{p['id']}/pay", headers=h, json={}).status_code == 409
    assert client.get("/api/me", headers=h).json()["credits"] == 11

    assert client.get("/api/admin/overview", headers=h).status_code == 403
    admin = auth(client, "admin2@example.com")  # not in ADMIN_EMAILS
    assert client.get("/api/admin/overview", headers=admin).status_code == 403


def test_failed_screening_refunds_the_credit(client, monkeypatch):
    h = auth(client, "refund@example.com")
    job = client.post("/api/jobs", headers=h, json=JOB).json()
    cid = add_candidate(client, h, job["id"])

    def boom(*_a, **_k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(engine, "run_stage", boom)
    assert client.post(f"/api/candidates/{cid}/stages/screen", headers=h).status_code == 200
    s = wait(client, h, cid, "screen")
    assert s["status"] == "failed" and "model unavailable" in s["error"]
    assert client.get("/api/me", headers=h).json()["credits"] == 1  # refunded
    monkeypatch.undo()
    assert client.post(f"/api/candidates/{cid}/stages/screen", headers=h).status_code == 200
    assert wait(client, h, cid, "screen")["status"] == "completed"
    assert client.get("/api/me", headers=h).json()["credits"] == 0


def test_validation_and_login_throttle(client):
    h = auth(client, "valid@example.com")
    bad = {**JOB, "salary_min": 5000, "salary_max": 1000}
    assert client.post("/api/jobs", headers=h, json=bad).status_code == 422
    job = client.post("/api/jobs", headers=h, json=JOB).json()
    r = client.post(f"/api/jobs/{job['id']}/candidates", headers=h, data={"name": "No CV", "cv_text": "short"})
    assert r.status_code == 422
    files = {"cv_file": ("cv.exe", b"MZ" + b"x" * 100, "application/octet-stream")}
    assert client.post(f"/api/jobs/{job['id']}/candidates", headers=h, data={"name": "Bad File"}, files=files).status_code == 422
    assert client.post("/api/jobs", json=JOB).status_code == 401
    for _ in range(8):
        client.post("/api/auth/login", json={"email": "valid@example.com", "password": "wrong-password"})
    assert client.post("/api/auth/login", json={"email": "valid@example.com", "password": "password123"}).status_code == 429
