# Zyndesk Hire

A web platform that sells the work of the `ai_recruitment_hiring_pipeline` CrewAI crew as a service.
A recruiter creates a job, adds candidates (CV upload or pasted text), and the agents screen the CV, write the
interview, score the answers, recommend a decision, draft the emails, check salary and documents, and compile the
HR report. Customers buy credit packs (1 credit = 1 candidate through the whole pipeline). Bilingual EN/AR (RTL),
same "Kinetic Brutalism" design as Zyndesk Leads.

## How the crew became a product

| Original crew (zip)                                         | In the platform                                                                                     |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| One `kickoff()` with 14 inputs, all 8 tasks in a row         | Stages the customer triggers: screen, evaluate, salary, documents, emails, report. Real pipelines wait for a human (the interview, the documents) |
| `cv_url` fetched by `URLReadTool`, `OCRTool` for documents   | CV is uploaded/pasted text. No tool fetches user-supplied URLs (a public service would be an SSRF hole). Documents are checked by name for completeness only |
| Prose outputs                                                | Every task returns pydantic JSON (`engine/crew_engine.py`)                                           |
| "Advisory only", "never send without HR approval" in prompts | Enforced in code: `engine/rules.py` and `check_ready()`                                              |
| Hard-coded "John Doe" knowledge file, one company            | Company, passing score, salary range, required documents and language come from the job             |

Original agent/task YAML is kept in `backend/app/engine/original_config_reference/`.

## Two sides: HR and candidate

| HR account (employer)                                           | Candidate account (job seeker)                                              |
| --------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Posts job info (description, passing score, salary range, documents) and opens/closes it | Browses the public job board (`/portal`) and applies with a CV           |
| Sees applicants, scores, AI recommendations, emails, report     | Sees only a status, never scores, AI output, the passing score or the salary range |
| Clicks *Send interview*; reviews; records the HR decision       | Answers the ten questions in their own account; uploads requested documents |
| Pays credits; an application is screened automatically on the HR's credit (it waits if they have none) | Can withdraw and erase the application at any time |

Pick the role when registering. Sessions are stored per browser tab (`sessionStorage`), so HR and a candidate can be signed in at the
same time in two tabs; closing a tab signs it out. Applicants get no free credit; the admin flag is HR-only.

## Decision rules (code, not prompts)

* Interview score = sum of ten 0-10 answer scores, added up by code. The model's own total is not trusted.
* The passing score applies to the interview score; the CV must also not be "Does Not Meet Criteria".
* The AI recommendation is forced to **Manual Review** when: fewer than 10 answers were found, the model says Pass below the
  passing score or with a failed CV, or says Fail at/above the passing score. The reason is stored and shown.
* Salary class (within / below / above) and the document checklist are computed in code; the model only writes the replies.
* A rejection email needs a recorded HR decision of `fail`; a final-hiring email needs `pass`. Enforced by the API.
* The platform never sends email. Admins cannot read candidates (owner-only), and deleting a candidate or job erases it.

## Run it

```bash
# backend (port 8788; 8787 is Zyndesk Leads)
cd backend
uv venv --python 3.13 .venv        # crewai needs Python < 3.14
uv pip install --python .venv/Scripts/python.exe -r requirements.txt -r requirements-crew.txt -r requirements-dev.txt
cp .env.example .env               # edit it
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8788

# frontend: dev server with /api proxy, or build and let FastAPI serve dist/
cd frontend && npm install
npm run dev                        # http://localhost:5274
npm run build                      # then open http://localhost:8788
node scripts/check-i18n.mjs        # EN/AR key parity + missing keys

# tests (sample engine, temp database)
cd backend && .venv/Scripts/python.exe -m pytest -q tests
```

Register with an email listed in `ADMIN_EMAILS` to get `/admin` (purchases, grant credits, failed runs; no candidate data).

## Engines

* `ENGINE=auto` (default): live crew when `crewai` is installed and an LLM key is set, else the sample-data engine.
  Sample runs are flagged `is_demo` and show a banner; their output is fictional and not an LLM.
* Live: set `CREW_MODEL` (default `openai/gpt-4o-mini`; the original used `openai/gpt-5.6-luna`) and its key. Optional
  `CREW_WRITER_MODEL` for emails, salary reply and report. No search key is needed (no web tools).
* `scripts/live_smoke.py [en|ar]` runs the whole live pipeline on a made-up candidate and saves `data/smoke_result.json`.

### Verification status

| What                                   | Status                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------- |
| API, billing, gates, roles, portal, privacy, refunds | 19 automated tests pass (sample engine)                                       |
| UI                                     | Walked through in a browser (EN, AR/RTL, mobile width) against the sample engine            |
| Live CrewAI crew                       | Run end to end on 2026-11-04 with `gpt-4o-mini` (`scripts/live_smoke.py`, English and Arabic, ~70 s per candidate, a few cents): 10 questions, scores, salary class, document gaps and report all came back structured. Fixed along the way: the decision agent quoted the CV score as the interview score (now handed the computed numbers); a hiring email claimed an attachment. Arabic body text was clean, the email subject came back English (prompt now asks for Arabic, not re-tested) |

Known limits seen in testing: the document check matches words, so "BSc certificate" does not satisfy "Degree certificate" (the agent
flags it, HR decides); a model grading generic answers harshly is expected, so keep the HR decision step.

## Payments

`PAYMENT_MODE=manual` (default): customer pays by bank transfer / CliQ, submits a reference, you confirm in `/admin`
and the credits are added (idempotent). `PAYMENT_MODE=demo` adds credits instantly for testing. A card gateway
(Stripe is not available to Jordan-based merchants; check Paymob, Tap, HyperPay, MyFatoorah) would hook in at
`POST /api/purchases/{id}/pay` plus a webhook calling `_mark_paid()`.

## Before taking real money

* Prices are placeholders in `backend/app/pricing.py`.
* Add Terms and a Privacy policy. This processes personal data (CVs, interviews) with a third-party model provider and
  supports hiring decisions, which some jurisdictions regulate (automated decision-making, AI in employment). Have a
  lawyer review, and require customers to tell candidates their data is processed by AI.
* Welcome credit is per account with no email verification: add verification or a payment-method check before relying on it.
* Set a strong `APP_SECRET` (`APP_ENV=production` refuses the default), serve over HTTPS, back up `data/`.
  Login throttling is in-memory (one process). SQLite is fine to start; use Postgres for several server processes.
* Arabic output is readable but a native speaker should skim drafts; scanned-image CVs are not read (no OCR).
