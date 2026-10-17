"""Evaluation integrity checks without model calls or employee ratings."""
from copy import deepcopy
import hashlib

import pytest

from app.evaluation import build_evaluation, leadership_evidence_support, resolve_rubric, validate_evaluation
from app.guidelines import LEADERSHIP_PRINCIPLES


def evaluation_value(evidence=None, score=3):
    ids = [item["id"] for item in evidence or []][:2]
    return {"dimensions": [{"id": item["id"], "score": score, "rationale": "The report distinguishes documented actions from team results.",
                            "strengths": ["Specific contribution is clear."], "improvements": [], "evidence_ids": ids}
                           for item in resolve_rubric()["dimensions"]],
            "summary": "A usable source-grounded draft.", "strengths": ["Clear individual contribution."],
            "improvements": [], "leadership_alignment": [], "issues": [], "missing_information": []}


EVIDENCE = [{"id": "E1"}]
PRINCIPLES = [item["name"] for item in LEADERSHIP_PRINCIPLES]


def test_weighted_score_and_snapshot_identity_are_computed_by_code():
    value = evaluation_value(EVIDENCE, score=3)
    value.update(overall_score=100, report_hash="fabricated", evaluated_at="fabricated", status="approved")
    value["dimensions"][0].update(weight=1000, name="Invented label")
    report = "# Annual review\n\nA specific action. [E1]"
    result = build_evaluation(value, report, EVIDENCE, resolve_rubric(), PRINCIPLES)
    assert result["overall_score"] == 60
    assert result["report_hash"] == hashlib.sha256(report.encode("utf-8")).hexdigest()
    assert result["status"] == "completed"
    assert result["evaluated_at"] != "fabricated"
    assert result["dimensions"][0]["weight"] == 25
    assert result["dimensions"][0]["name"] == "Factual accuracy"
    assert build_evaluation(value, report + " ", EVIDENCE, resolve_rubric(), PRINCIPLES)["report_hash"] != result["report_hash"]


@pytest.mark.parametrize("score", [True, False, float("nan"), float("inf"), 0, 5.1, "4"])
def test_scores_must_be_finite_numeric_values_on_the_rubric_scale(score):
    value = evaluation_value(EVIDENCE)
    value["dimensions"][0]["score"] = score
    with pytest.raises(ValueError):
        validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)


def test_all_six_unique_dimensions_and_known_evidence_are_required():
    value = evaluation_value(EVIDENCE)
    for invalid in (value["dimensions"][:-1], [value["dimensions"][0]] * 6):
        with pytest.raises(ValueError):
            validate_evaluation({**value, "dimensions": invalid}, EVIDENCE, resolve_rubric(), PRINCIPLES)
    value["dimensions"][0]["evidence_ids"] = ["E999"]
    with pytest.raises(ValueError, match="unknown evidence"):
        validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)


def test_real_model_shape_accepts_all_known_evidence_and_canonicalizes_gap_objects():
    evidence = [{"id": f"E{index}"} for index in range(1, 47)]
    value = evaluation_value(evidence)
    value["dimensions"][0]["evidence_ids"] = [item["id"] for item in evidence]
    value["issues"] = [{"severity": "medium", "message": "Clarify individual ownership.", "evidence_ids": ["E1"]}]
    value["missing_information"] = [{"severity": "medium", "message": "What personal challenge would you reflect on?", "evidence_ids": []}]
    checked = validate_evaluation(value, evidence, resolve_rubric(), PRINCIPLES)
    assert len(checked["dimensions"][0]["evidence_ids"]) == 46
    assert checked["issues"][0]["suggestion"] == ""
    assert checked["missing_information"] == ["What personal challenge would you reflect on?"]
    value["missing_information"][0]["evidence_ids"] = ["E999"]
    with pytest.raises(ValueError, match="unknown evidence"):
        validate_evaluation(value, evidence, resolve_rubric(), PRINCIPLES)


def test_leadership_mapping_requires_an_official_name_and_supported_evidence_id():
    value = evaluation_value(EVIDENCE)
    value["leadership_alignment"] = [{"principle": "Dive Deep", "explanation": "The documented validation work examines task boundaries.", "evidence_ids": ["E1"]}]
    checked = validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)
    assert checked["leadership_alignment"][0]["principle"] == "Dive Deep"
    for change in ({"principle": "Invented principle"}, {"evidence_ids": []}, {"evidence_ids": ["E999"]}):
        invalid = deepcopy(value)
        invalid["leadership_alignment"][0].update(change)
        with pytest.raises(ValueError):
            validate_evaluation(invalid, EVIDENCE, resolve_rubric(), PRINCIPLES)


def test_blank_leadership_abstention_preserves_its_explanation_without_inventing_a_mapping():
    value = evaluation_value(EVIDENCE)
    explanation = "No leadership principle is established in this draft."
    value["leadership_alignment"] = [{"principle": "", "explanation": explanation, "evidence_ids": []}]
    checked = validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)
    assert checked["leadership_alignment"] == []
    assert explanation in next(item for item in checked["dimensions"] if item["id"] == "leadership_alignment")["rationale"]
    for invalid in ({"principle": "Invented principle", "explanation": explanation, "evidence_ids": []}, {"principle": "", "explanation": "Ownership is clearly demonstrated.", "evidence_ids": []}, {"principle": "", "explanation": explanation, "evidence_ids": ["E1"]}):
        value["leadership_alignment"] = [invalid]
        with pytest.raises(ValueError):
            validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)


def test_evaluation_omits_unsupported_resource_people_and_uncertainty_mappings():
    evidence = [{"id": "E1", "quote": "I wrote SQL queries and selected representative evaluation tasks.", "attribution": "employee", "status": "delivered"}]
    value = evaluation_value(evidence)
    value["leadership_alignment"] = [{"principle": name, "explanation": "An unsupported interpretation.", "evidence_ids": ["E1"]} for name in ("Frugality", "Hire and Develop the Best", "Bias for Action")]
    result = build_evaluation(value, "A draft. [E1]", evidence, resolve_rubric(), PRINCIPLES)
    assert result["leadership_alignment"] == []
    assert len(result["issues"]) == 3
    assert result["overall_score"] == 60


def test_invent_and_simplify_requires_documented_simplification_not_instrumentation():
    instrumentation = [{"quote": "I implemented telemetry and validated the pilot data.", "attribution": "employee", "status": "delivered"}]
    simplification = [{"quote": "I replaced three manual validation steps with one automated check.", "attribution": "employee", "status": "delivered"}]
    assert not leadership_evidence_support("Invent and Simplify", instrumentation)
    assert leadership_evidence_support("Invent and Simplify", simplification)


def test_configurable_internal_rubric_preserves_axes_and_validates_total():
    rubric = resolve_rubric()
    rubric["version"] = "annual-review-custom-v2"
    rubric["dimensions"][0]["weight"] = 30
    rubric["dimensions"][1]["weight"] = 15
    assert resolve_rubric(rubric)["version"] == "annual-review-custom-v2"
    rubric["dimensions"][1]["weight"] = 20
    with pytest.raises(ValueError, match="total 100"):
        resolve_rubric(rubric)


def test_unknown_issue_evidence_and_missing_advice_shape_are_rejected():
    value = evaluation_value(EVIDENCE)
    value["issues"] = [{"severity": "high", "message": "A claim lacks support.", "suggestion": "Remove it.", "evidence_ids": ["E999"]}]
    with pytest.raises(ValueError):
        validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)
    value = evaluation_value(EVIDENCE)
    value["summary"] = "An assertion with an unknown reference [E999]."
    with pytest.raises(ValueError, match="unknown evidence citation"):
        validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)
    value = evaluation_value(EVIDENCE)
    del value["dimensions"][0]["improvements"]
    with pytest.raises(ValueError):
        validate_evaluation(value, EVIDENCE, resolve_rubric(), PRINCIPLES)
