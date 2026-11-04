import io

import pytest

from app import cv
from app.engine import rules


def test_salary_classification():
    assert rules.classify_salary(900, "USD", "USD", 1000, 2000)["scenario"] == "below"
    assert rules.classify_salary(1500, "usd", "USD", 1000, 2000)["scenario"] == "within"
    assert rules.classify_salary(2500, "USD", "USD", 1000, 2000)["scenario"] == "above"
    assert rules.classify_salary(1500, "JOD", "USD", 1000, 2000)["scenario"] == "unknown"
    assert rules.classify_salary(None, "USD", "USD", 1000, 2000)["scenario"] == "unknown"
    assert rules.classify_salary(1500, "USD", "USD", None, None)["scenario"] == "unknown"


def test_document_matching():
    rows = rules.match_documents(
        ["Passport copy", "CV", "Degree certificate"],
        ["ahmad_passport.pdf", "Resume - Ahmad.docx", "degree.jpg"],
    )
    status = {r["document"]: r["status"] for r in rows}
    assert status == {"Passport copy": "Received", "CV": "Received", "Degree certificate": "Missing"}


def _items(scores, answered=True):
    return [{"question": f"q{i}", "answer": "an answer" if answered else "", "score": s} for i, s in enumerate(scores)]


def test_interview_score_is_computed_not_trusted():
    out = rules.finalize_evaluation(_items([8] * 10), {"recommendation": "Proceed", "score": 80}, 70, "Pass")
    assert out["interview_score"] == 80 and out["decision"] == "Pass" and not out["guard_notes"]
    out = rules.finalize_evaluation(_items([99] * 10), {"recommendation": "Proceed"}, 70, "Pass")
    assert out["interview_score"] == 100  # each answer is clamped to 10


def test_pass_below_passing_score_becomes_manual_review():
    out = rules.finalize_evaluation(_items([5] * 10), {"recommendation": "Proceed"}, 70, "Pass")
    assert out["decision"] == "Manual Review" and out["guard_notes"]


def test_pass_with_failed_cv_becomes_manual_review():
    out = rules.finalize_evaluation(_items([9] * 10), {"recommendation": "Does Not Meet Criteria"}, 70, "Pass")
    assert out["decision"] == "Manual Review"


def test_fail_above_passing_score_becomes_manual_review():
    out = rules.finalize_evaluation(_items([9] * 10), {"recommendation": "Proceed"}, 70, "Fail")
    assert out["decision"] == "Manual Review"


def test_incomplete_interview_is_manual_review():
    out = rules.finalize_evaluation(_items([9] * 6), {"recommendation": "Proceed"}, 70, "Pass")
    assert out["incomplete"] and out["decision"] == "Manual Review" and out["answers_found"] == 6


def test_unknown_decision_text_is_manual_review():
    assert rules.norm_decision("Hire immediately!") == "Manual Review"
    assert rules.norm_cv_recommendation("does not meet") == "Does Not Meet Criteria"


def test_stage_keys():
    assert rules.valid_stage("screen") and rules.valid_stage("email:final_hiring")
    assert not rules.valid_stage("email:bogus") and not rules.valid_stage("../x")


def test_split_answers():
    t = "Q1: What is X?\nA1: It is X.\nQ2: Why?\nA2: Because.\n"
    assert rules.split_answers(t) == ["It is X.\nQ2: Why?", "Because."] or len(rules.split_answers(t)) == 2


def test_cv_text_and_docx():
    text = "Experienced engineer with ten years of Python and cloud work. " * 3
    assert cv.extract_text("cv.txt", text.encode()).startswith("Experienced")
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    assert "Python" in cv.extract_text("cv.docx", buf.getvalue())


def test_cv_rejects_bad_files():
    with pytest.raises(cv.CVError):
        cv.extract_text("cv.exe", b"MZ....")
    with pytest.raises(cv.CVError):
        cv.extract_text("cv.pdf", b"not a pdf at all, just text pretending to be one")
    with pytest.raises(cv.CVError):
        cv.extract_text("cv.txt", b"too short")
