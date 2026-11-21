"""HR and candidate are separate accounts: roles, applying, the candidate-answered interview, documents, privacy."""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_flow import CV, JOB, wait


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email, role):
    r = client.post("/api/auth/register", json={"email": email, "name": role.title(), "password": "password123", "role": role})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == role
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_roles_are_separate(client):
    hr = signup(client, "hr-roles@example.com", "hr")
    cand = signup(client, "cand-roles@example.com", "candidate")
    assert client.get("/api/me", headers=cand).json()["credits"] == 0  # no free pipeline for applicants
    # a candidate cannot reach HR features, an HR cannot reach the candidate portal
    assert client.get("/api/jobs", headers=cand).status_code == 403
    assert client.post("/api/jobs", headers=cand, json=JOB).status_code == 403
    assert client.post("/api/purchases", headers=cand, json={"package": "starter"}).status_code == 403
    assert client.get("/api/portal/applications", headers=hr).status_code == 403
    # an applicant cannot become admin by using an admin email
    r = client.post("/api/auth/register", json={"email": "admin-cand@example.com", "name": "x", "password": "password123", "role": "candidate"})
    assert r.json()["user"]["is_admin"] is False


def test_apply_interview_documents_and_privacy(client):
    hr = signup(client, "hr-flow@example.com", "hr")
    job = client.post("/api/jobs", headers=hr, json=JOB).json()
    cand = signup(client, "cand-flow@example.com", "candidate")

    # public board shows open jobs without the private fields
    board = client.get("/api/portal/jobs").json()
    mine = next(j for j in board if j["id"] == job["id"])
    assert "passing_score" not in mine and "salary_min" not in mine and mine["application_id"] is None
    assert client.get("/api/portal/jobs", headers=cand).json()[0]["id"]

    # applying: needs a CV, once per job
    assert client.post(f"/api/portal/jobs/{job['id']}/apply", headers=cand, data={"name": "Cand Flow", "cv_text": "short"}).status_code == 422
    r = client.post(f"/api/portal/jobs/{job['id']}/apply", headers=cand,
                    data={"name": "Cand Flow", "cv_text": CV, "expected_salary": "3500", "currency": "USD"})
    assert r.status_code == 200, r.text
    app_id = r.json()["id"]
    assert client.post(f"/api/portal/jobs/{job['id']}/apply", headers=cand, data={"name": "Again", "cv_text": CV}).status_code == 409

    # the HR's welcome credit pays for the automatic screening
    assert wait(client, hr, app_id, "screen")["status"] == "completed"
    assert client.get("/api/me", headers=hr).json()["credits"] == 0
    cd = client.get(f"/api/candidates/{app_id}", headers=hr).json()
    assert cd["candidate"]["applicant"] and cd["candidate"]["email"] == "cand-flow@example.com"

    # candidate sees only a status, no questions until HR sends the interview
    view = client.get(f"/api/portal/applications/{app_id}", headers=cand).json()
    assert view["status"] == "in_review" and view["questions"] == []
    assert "stages" not in view and "hr_note" not in view and "passing_score" not in view["job"]
    assert client.post(f"/api/portal/applications/{app_id}/interview", headers=cand, json={"answers": ["x"] * 10}).status_code == 409
    assert client.post(f"/api/candidates/{app_id}/interview/send", headers=hr).status_code == 200
    view = client.get(f"/api/portal/applications/{app_id}", headers=cand).json()
    assert view["status"] == "interview" and len(view["questions"]) == 10
    assert all(isinstance(q, str) for q in view["questions"])  # text only, no difficulty or hints

    # must answer every question; then scoring starts by itself
    assert client.post(f"/api/portal/applications/{app_id}/interview", headers=cand, json={"answers": ["a long enough answer"] * 3}).status_code == 422
    answers = [f"My detailed answer number {i} with measurable results and trade-offs explained properly." for i in range(10)]
    assert client.post(f"/api/portal/applications/{app_id}/interview", headers=cand, json={"answers": answers}).status_code == 200
    ev = wait(client, hr, app_id, "evaluate")["result"]
    assert ev["answers_found"] == 10 and ev["requires_hr_approval"]
    view = client.get(f"/api/portal/applications/{app_id}", headers=cand).json()
    assert view["status"] == "interview_submitted" and view["answers"] == answers
    assert client.post(f"/api/candidates/{app_id}/interview/send", headers=hr).status_code == 409

    # documents: validated by type and content, synced to the HR's checklist
    pdf = ("Passport copy.pdf", b"%PDF-1.4 fake pdf body", "application/pdf")
    assert client.post(f"/api/portal/applications/{app_id}/documents", headers=cand, files={"file": pdf}).status_code == 200
    assert client.post(f"/api/portal/applications/{app_id}/documents", headers=cand, files={"file": ("x.exe", b"MZ", "a/b")}).status_code == 422
    assert client.post(f"/api/portal/applications/{app_id}/documents", headers=cand, files={"file": ("fake.pdf", b"not a pdf", "a/b")}).status_code == 422
    cd = client.get(f"/api/candidates/{app_id}", headers=hr).json()
    assert [d["name"] for d in cd["documents"]] == ["Passport copy.pdf"]
    assert cd["candidate"]["submitted_documents"] == ["Passport copy.pdf"]
    dl = client.get(f"/api/candidates/{app_id}/documents/{cd['documents'][0]['id']}", headers=hr)
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")
    assert client.post(f"/api/candidates/{app_id}/stages/documents", headers=hr).status_code == 200
    assert wait(client, hr, app_id, "documents")["result"]["missing"] == ["CV"]

    # the candidate learns the HR outcome only once HR records it, never the AI's view
    client.post(f"/api/candidates/{app_id}/decision", headers=hr, json={"outcome": "pass", "note": "internal note"})
    view = client.get(f"/api/portal/applications/{app_id}", headers=cand).json()
    assert view["status"] == "decided" and view["outcome"] == "pass" and "internal note" not in str(view)

    # another candidate cannot read it, and withdrawing erases everything
    other = signup(client, "cand-other@example.com", "candidate")
    assert client.get(f"/api/portal/applications/{app_id}", headers=other).status_code == 404
    assert client.delete(f"/api/portal/applications/{app_id}", headers=other).status_code == 404
    assert client.delete(f"/api/portal/applications/{app_id}", headers=cand).status_code == 200
    assert client.get(f"/api/candidates/{app_id}", headers=hr).status_code == 404
    assert client.get("/api/portal/applications", headers=cand).json() == []


def test_closed_jobs_and_no_credit_wait(client):
    hr = signup(client, "hr-closed@example.com", "hr")
    job = client.post("/api/jobs", headers=hr, json={**JOB, "is_open": False}).json()
    cand = signup(client, "cand-closed@example.com", "candidate")
    assert all(j["id"] != job["id"] for j in client.get("/api/portal/jobs").json())
    assert client.post(f"/api/portal/jobs/{job['id']}/apply", headers=cand, data={"name": "Nope Nope", "cv_text": CV}).status_code == 404
    # reopen; with no credit left the application waits for HR instead of failing
    client.put(f"/api/jobs/{job['id']}", headers=hr, json={**JOB, "is_open": True})
    from app import db
    with db.conn() as c:
        c.execute("UPDATE users SET credits=0 WHERE email='hr-closed@example.com'")
    r = client.post(f"/api/portal/jobs/{job['id']}/apply", headers=cand, data={"name": "Waits Here", "cv_text": CV})
    assert r.status_code == 200
    time.sleep(0.5)
    cd = client.get(f"/api/candidates/{r.json()['id']}", headers=hr).json()
    assert "screen" not in cd["stages"] and any("waiting for HR" in e["message"] for e in cd["events"])
    view = client.get(f"/api/portal/applications/{r.json()['id']}", headers=cand).json()
    assert view["status"] == "received"


def test_demo_accounts_are_seeded_once(client):
    from app import config, seed
    config.SEED_DEMO_ACCOUNTS = True
    try:
        seed.run()
        seed.run()  # idempotent: no second top-up, no duplicate user
    finally:
        config.SEED_DEMO_ACCOUNTS = False
    hr = client.post("/api/auth/login", json={"email": config.DEMO_HR_EMAIL, "password": config.DEMO_HR_PASSWORD})
    cand = client.post("/api/auth/login", json={"email": config.DEMO_CANDIDATE_EMAIL, "password": config.DEMO_CANDIDATE_PASSWORD})
    assert hr.status_code == 200 and hr.json()["user"]["role"] == "hr" and hr.json()["user"]["credits"] == config.DEMO_CREDITS
    assert cand.status_code == 200 and cand.json()["user"]["role"] == "candidate"
