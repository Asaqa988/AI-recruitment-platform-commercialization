"""Runs the live CrewAI pipeline directly (no web server, no database) on a made-up candidate and
saves every stage's result to data/smoke_result.json. Costs a few cents of model usage.

    .venv/Scripts/python.exe scripts/live_smoke.py [en|ar]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import engine  # noqa: E402  (importing config loads backend/.env)

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
JOB = {
    "title": "Senior Backend Engineer", "company": "Acme Payments", "passing_score": 65, "currency": "USD",
    "description": ("We are hiring a senior backend engineer to build payment services. Must have 5+ years with Python, "
                    "FastAPI or Django, PostgreSQL, AWS and event-driven design. Bachelor's degree in computer science or similar. "
                    "Nice to have: Kubernetes and PCI-DSS experience."),
    "salary_min": 3000, "salary_max": 4000, "required_documents": ["Passport copy", "Degree certificate", "CV"], "language": LANG,
}
CV = """Jane Doe - Backend Engineer
BSc Computer Science, University of Jordan, 2016-2020
2020-2022 Software Engineer, Payfast: Django REST APIs, PostgreSQL, Celery queues, 2M requests/day.
2022-present Senior Engineer, Zain Pay: FastAPI services on AWS (ECS, SQS, RDS), led a migration from a monolith to event-driven services.
Certifications: AWS Solutions Architect Associate.
Projects: open-source rate limiter library in Python (400 GitHub stars).
Skills: Python, FastAPI, Django, PostgreSQL, AWS, Docker, Redis."""
CAND = {
    "name": "Jane Doe", "email": "jane@example.com", "cv_text": CV, "transcript": "", "expected_salary": 4500, "currency": "USD",
    "submitted_documents": ["jane_cv.pdf", "BSc certificate.pdf"], "hr_outcome": None, "hr_note": "",
}

stages: dict = {}


def step(stage: str) -> dict:
    t0 = time.time()
    ctx = {"job": JOB, "candidate": CAND, "stages": stages, "params": {}}
    result = engine.run_stage(stage, ctx, lambda s, m: print(f"   [{s}] {m}"))
    stages[stage] = {"status": "completed", "result": result, "is_demo": False}
    print(f"-> {stage} done in {time.time() - t0:.0f}s")
    return result


name, reason = engine.pick_engine()
print(f"engine: {name} ({reason}), model: {engine.config.CREW_MODEL}, language: {LANG}")
if name != "crew":
    sys.exit("The live engine is not available. Set an LLM key in backend/.env and install requirements-crew.txt.")

screen = step("screen")
CAND["transcript"] = "\n".join(
    f"Q{q['n']}: {q['question']}\nA{q['n']}: I handled this on a production payments system, weighing latency against consistency, "
    "added tests and monitoring, and measured the result before and after." for q in screen["questions"]["items"])
step("evaluate")
step("salary")
step("documents")
CAND["hr_outcome"] = "pass"
step("email:final_hiring")
step("report")

out = ROOT / "data" / "smoke_result.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({k: v["result"] for k, v in stages.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved", out)
