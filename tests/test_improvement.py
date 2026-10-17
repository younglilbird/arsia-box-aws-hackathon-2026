"""Question-scoped editing preserves prose, provenance and exact evaluation."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.evaluation import build_evaluation, report_hash, resolve_rubric
from app.guidelines import LEADERSHIP_PRINCIPLES
from app.improvement import _allowed_sections, _evidence_plan, _patch_result, improve_review
from app.workflow import WorkflowError
from tests.test_evaluation import evaluation_value


REFLECTION = "My biggest challenge was aligning the task boundary. I learned to share the definition before adding telemetry."
GOAL = "For2027, I propose a monthly validation review with my manager; these individual goals have not yet been agreed."
ANSWERS = REFLECTION + "\n" + GOAL
QUESTIONS = ["Describe a significant personal challenge and what you learned.", "What individual goals would you propose for2027, and which have you agreed with your manager?"]
PRINCIPLES = [item["name"] for item in LEADERSHIP_PRINCIPLES]


def fixture():
    old_quote = "I implemented the measurement taxonomy and validation notebook."
    old_text = old_quote + "\nThis log does not record a personal challenge or a reflection on what I would do differently.\nIndividual goals have not been agreed."
    source = {"id": "101", "name": "project.docx", "url": "https://app.box.com/file/101", "file_version": {"id": "1001"}, "status": "analyzed", "retained_evidence_count": 1, "text": old_text}
    new = {"id": "202", "name": "employee-answers.docx", "url": "https://app.box.com/file/202", "file_version": {"id": "2002"}, "document_category": "Annual Plans", "text": "Questions being addressed\n" + "\n".join(QUESTIONS) + "\nEmployee answers\n" + ANSWERS}
    evidence = [{"id": "E1", "source_id": "101", "source_name": source["name"], "source_url": source["url"], "quote": old_quote, "claim": "Implemented measurement artifacts.", "status": "delivered", "attribution": "employee", "category": "work_detail", "project": "Atlas", "evidence_type": "project_evidence"}]
    report = "# Annual Review Summary — Alex Chen —2026\n\n## Annual Review Summary\n\n### Atlas\n\nI implemented the measurement taxonomy and validation notebook for the project. This is an employee-edited sentence that must remain exactly intact. [E1]\n\nThe team used the documented measurement definitions in its review; this paragraph also remains intact. [E1]\n\n## Leadership Principles Summary\n\n### Ownership\n\nI owned the documented measurement artifacts and their verification. [E1]\n\n## Next Year Goals\n\nMy manager and I have not agreed my individual goals.\n\n## Peer Feedback Summary\n\nNo supplied peer feedback is available in this fixture."
    initial = build_evaluation(evaluation_value(evidence), report, evidence, resolve_rubric(), PRINCIPLES)
    run = {"id": "same-draft", "employee_name": "Alex Chen", "year": 2026, "created_at": "original-time", "status": "running", "report_markdown": report, "initial_draft": "Immutable original draft", "evidence": evidence,
           "sources": [{key: value for key, value in source.items() if key != "text"}], "missing_information": QUESTIONS, "reviewer_confirmed": True, "user_edited": True,
           "evaluations": {"rubric_version": "annual-review-v1", "score_label": "Draft quality", "initial": deepcopy(initial), "final": deepcopy(initial)},
           "usage": {"calls": 10, "input_tokens": 1000, "output_tokens": 100, "latency_ms": 500}, "coverage": {"discovered_files": 1, "candidate_evidence_count": 3, "warnings": []},
           "improvement_context": {"new_source": new, "answered_questions": QUESTIONS}}
    return run, source, new


class FakeBox:
    def __init__(self, sources):
        self.sources = {str(source["id"]): source["text"] for source in sources}
        self.reads = []

    def read_text(self, source):
        self.reads.append((source["id"], source["file_version"]["id"]))
        return self.sources[str(source["id"])]


class FakeEngine:
    def __init__(self):
        self.usage = {"model_id": "offline-test", "calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}
        self.model_id = "offline-test"
        self.payloads = []

    def json_call(self, system, payload, max_tokens, validate):
        self.payloads.append(deepcopy(payload))
        self.usage["calls"] += 1
        if "available_new_evidence_ids" in payload:
            first, second = payload["available_new_evidence_ids"]
            value = {"new_evidence": [{"id": first, "quote": REFLECTION, "claim": "Personal reflection supplied by the employee.", "category": "learning", "project": "Atlas", "status": "delivered", "attribution": "employee"}, {"id": second, "quote": GOAL, "claim": "Proposed individual validation review.", "category": "goal", "project": "Atlas", "status": "measured", "attribution": "employee"}],
                     "patches": [{"section": "Annual Review Summary", "operation": "append", "anchor": "", "content": "### Personal reflection\n\n" + REFLECTION + f" [{first}]"}, {"section": "Next Year Goals", "operation": "append", "anchor": "", "content": GOAL + f" [{second}]"}]}
        else:
            value = evaluation_value(payload["evidence"], score=4)
        validate(value)
        return value


def test_same_draft_keeps_employee_prose_and_initial_audit_with_one_patch_and_one_fresh_evaluation():
    run, source, new = fixture()
    before = deepcopy(run)
    engine = FakeEngine()
    updates = []
    with patch("app.improvement.workflow.BedrockEngine", return_value=engine):
        result = improve_review(FakeBox([source, new]), SimpleNamespace(), run, ANSWERS, 90, lambda **value: updates.append(value))
    assert run == before
    assert result["id"] == run["id"]
    assert result["created_at"] == "original-time"
    assert result["initial_draft"] == run["initial_draft"]
    assert result["evaluations"]["initial"] == run["evaluations"]["initial"]
    assert "This is an employee-edited sentence that must remain exactly intact." in result["report_markdown"]
    assert "The team used the documented measurement definitions in its review; this paragraph also remains intact. [E1]" in result["report_markdown"]
    assert result["evaluations"]["final"]["report_hash"] == report_hash(result["report_markdown"])
    assert len(engine.payloads) == 2
    assert "advisory_target_score" not in engine.payloads[-1]
    assert "target_score" not in engine.payloads[-1]
    assert result["improvement"]["target_reached"] is False
    assert result["evaluations"]["final"]["overall_score"] == 80
    assert result["usage"]["calls"] == 12
    assert result["reviewer_confirmed"] is False
    assert result["improvement_history"][0]["report_markdown"] == before["report_markdown"]
    assert result["improvement_history"][0]["had_user_edits"] is True
    assert result["missing_information"] == []
    assert all("report_markdown" not in value for value in updates)
    assert all("text" not in item for item in result["sources"])
    new_facts = [item for item in result["evidence"] if item["source_id"] == "202"]
    assert len(new_facts) == 2
    assert all(item["evidence_type"] == "employee_self_report" for item in new_facts)
    assert all(item["status"] != "measured" for item in new_facts)


def test_generated_question_or_header_cannot_become_answer_evidence():
    run, source, new = fixture()
    value = {"new_evidence": [{"id": "E2", "quote": QUESTIONS[0], "claim": "A reflection was supplied.", "category": "learning"}], "patches": []}
    with pytest.raises(ValueError, match="actual employee answers"):
        _patch_result(value, run["report_markdown"], run["evidence"], ["E2"], new, ANSWERS, ["Annual Review Summary"], [source, new], 2026)


def test_reflection_answer_cannot_be_relabelled_as_a_new_goal_or_gain_an_invented_outcome():
    run, source, new = fixture()
    new = {**new, "text": REFLECTION}
    assert _allowed_sections(QUESTIONS, REFLECTION) == ["Annual Review Summary"]
    for category in ("learning", "goal"):
        value = {"new_evidence": [{"id": "E2", "quote": REFLECTION, "claim": "A personal reflection.", "category": category}],
                 "patches": [{"section": "Next Year Goals", "operation": "append", "content": "For2027, I propose new telemetry standards. [E2]"}]}
        with pytest.raises(ValueError, match="actual prospective intent"):
            _patch_result(value, run["report_markdown"], run["evidence"], ["E2"], new, REFLECTION, ["Next Year Goals"], [source, new], 2026)
    value = {"new_evidence": [{"id": "E2", "quote": REFLECTION, "claim": "The new process improved clarity and effectiveness.", "category": "learning"}],
             "patches": [{"section": "Annual Review Summary", "operation": "append", "content": "This improved clarity and effectiveness. [E2]"}]}
    report, evidence, _, _ = _patch_result(value, run["report_markdown"], run["evidence"], ["E2"], new, REFLECTION, ["Annual Review Summary"], [source, new], 2026)
    assert REFLECTION in report
    assert "improved clarity and effectiveness" not in report
    assert evidence[-1]["claim"] == REFLECTION


def test_unrelated_rewrite_and_multi_sentence_gap_replacement_are_rejected():
    run, source, new = fixture()
    fact = {"id": "E2", "quote": GOAL, "claim": "A proposed goal.", "category": "goal"}
    for anchor in ("I implemented the measurement taxonomy and validation notebook for the project.", "The team direction is to improve validation. My manager and I have not agreed my individual goals."):
        report = run["report_markdown"]
        section = "Annual Review Summary"
        if anchor.startswith("The team direction"):
            report = report.replace("My manager and I have not agreed my individual goals.", anchor)
            section = "Next Year Goals"
        value = {"new_evidence": [fact], "patches": [{"section": section, "operation": "replace_span", "anchor": anchor, "content": GOAL + " [E2]"}]}
        with pytest.raises(ValueError, match="gap|information"):
            _patch_result(value, report, run["evidence"], ["E2"], new, ANSWERS, [section], [source, new], 2026)


def test_single_sentence_gap_replacement_cannot_remove_unrelated_employee_context():
    run, source, new = fixture()
    fact = {"id": "E2", "quote": GOAL, "claim": "A proposed goal.", "category": "goal"}
    mixed = "I owned the release plan and delivered the handover, but my individual goals are not agreed."
    base = run["report_markdown"].replace("My manager and I have not agreed my individual goals.", mixed)
    patch_value = {"section": "Next Year Goals", "operation": "replace_span", "anchor": mixed, "content": GOAL + " [E2]"}
    with pytest.raises(ValueError, match="complete information-gap"):
        _patch_result({"new_evidence": [fact], "patches": [patch_value]}, base, run["evidence"], ["E2"], new, ANSWERS, ["Next Year Goals"], [source, new], 2026)
    patch_value.update(operation="append", anchor="")
    report, _, _, _ = _patch_result({"new_evidence": [fact], "patches": [patch_value]}, base, run["evidence"], ["E2"], new, ANSWERS, ["Next Year Goals"], [source, new], 2026)
    assert mixed in report
    assert GOAL in report
    # The application's standalone gap can be replaced without touching any
    # preceding accomplishment or unrelated paragraph.
    standalone = "Source-backed details are needed for individual next-year goals."
    base = run["report_markdown"].replace("My manager and I have not agreed my individual goals.", standalone)
    patch_value.update(operation="replace_span", anchor=standalone)
    report, _, _, _ = _patch_result({"new_evidence": [fact], "patches": [patch_value]}, base, run["evidence"], ["E2"], new, ANSWERS, ["Next Year Goals"], [source, new], 2026)
    assert standalone not in report
    assert "This is an employee-edited sentence that must remain exactly intact." in report


def test_new_leadership_patch_uses_the_same_source_behavior_guard_as_initial_generation():
    run, source, new = fixture()
    answers = "I implemented telemetry and validated the pilot data."
    new = {**new, "text": answers}
    fact = {"id": "E2", "quote": answers, "claim": answers, "category": "work_detail", "attribution": "employee"}
    content = "### Frugality\n\nI demonstrated Frugality through the telemetry and pilot-data validation work. [E2]"
    patch_value = {"section": "Leadership Principles Summary", "operation": "append", "anchor": "", "content": content}
    with pytest.raises(ValueError, match="documented behavior for: Frugality"):
        _patch_result({"new_evidence": [fact], "patches": [patch_value]}, run["report_markdown"], run["evidence"], ["E2"], new, answers, ["Leadership Principles Summary"], [source, new], 2026)
    # An existing human interpretation is preserved; this guard owns only the
    # new addition, rather than silently correcting the employee's old text.
    existing = run["report_markdown"].replace("### Ownership", "### Frugality")
    patch_value["content"] = "### Ownership\n\nI took responsibility for the documented telemetry and validation work. [E2]"
    report, _, _, _ = _patch_result({"new_evidence": [fact], "patches": [patch_value]}, existing, run["evidence"], ["E2"], new, answers, ["Leadership Principles Summary"], [source, new], 2026)
    assert "### Frugality" in report
    assert patch_value["content"] in report


def test_uncited_slots_are_removed_but_every_cited_original_item_stays():
    quote = "A source-backed documented fact."
    items = [{"id": f"E{index}", "source_id": str(index), "quote": quote} for index in range(1, 21)]
    report = "The documented work. [E1] [E2]"
    planned_report, retained, available, audit = _evidence_plan(report, items, [])
    assert planned_report == report
    assert {"E1", "E2"} <= {item["id"] for item in retained}
    assert len(retained) == 18 and len(available) == 2
    assert not {"E1", "E2"}.intersection(audit["uncited_items_removed"])


def test_all_twenty_cited_supports_can_only_be_freed_by_literal_same_source_consolidation():
    first, second = "I drafted the measurement taxonomy.", "I validated the task-completion data."
    text = first + " " + second
    items = [{"id": f"E{index}", "source_id": str(index), "quote": "A source-backed documented fact.", "status": "delivered", "attribution": "employee", "evidence_type": "project_evidence", "claim": "A documented action."} for index in range(1, 21)]
    items[0].update(source_id="shared", quote=first)
    items[1].update(source_id="shared", quote=second)
    report = " ".join(f"[E{index}]" for index in range(1, 21))
    changed, retained, available, audit = _evidence_plan(report, items, [{"id": "shared", "text": text}])
    assert len(retained) == 19 and len(available) == 1
    assert "[E2]" not in changed and "[E1]" in changed
    assert next(item for item in retained if item["id"] == "E1")["quote"] == text
    assert audit["citation_consolidations"][0]["removed_id"] == "E2"
    with pytest.raises(WorkflowError) as failure:
        _evidence_plan(report, [{**item, "source_id": item["id"]} for item in items], [])
    assert failure.value.code == "improvement_evidence_capacity"


def test_new_outcome_is_not_independent_measurement_and_unknown_ids_still_fail():
    run, source, new = fixture()
    answers = "I estimate a20% reduction, but this is not independently measured."
    new = {**new, "text": answers}
    fact = {"id": "E2", "quote": answers, "claim": "An employee estimate.", "category": "work_detail", "attribution": "employee", "status": "measured"}
    for prose in ("I achieved a20% reduction. [E2]", "I estimate a20% reduction. [E999]"):
        value = {"new_evidence": [fact], "patches": [{"section": "Annual Review Summary", "operation": "append", "content": prose}]}
        with pytest.raises(ValueError):
            _patch_result(value, run["report_markdown"], run["evidence"], ["E2"], new, answers, ["Annual Review Summary"], [source, new], 2026)


def test_model_source_context_is_bounded_but_literal_validation_can_read_full_pinned_text():
    run, source, new = fixture()
    source["text"] += " X" * 100000
    engine = FakeEngine()
    with patch("app.improvement.workflow.BedrockEngine", return_value=engine):
        result = improve_review(FakeBox([source, new]), SimpleNamespace(), run, ANSWERS)
    source_context = engine.payloads[-1]["original_sources"]
    assert sum(len(item["text"]) for item in source_context) <= 160000
    assert all(len(item["text"]) <= 30000 for item in source_context)
    assert result["coverage"]["improvement_source_context"]["truncated"] is True
    assert any("bounded excerpts" in text for text in result["coverage"]["warnings"])


def test_unsupported_existing_quote_is_preserved_but_cannot_escape_current_review():
    run, source, new = fixture()
    invented = 'A colleague said: "This invented praise was never supplied by any reviewer." [E1]'
    run["report_markdown"] = run["report_markdown"].replace("## Leadership Principles Summary", invented + "\n\n## Leadership Principles Summary")
    engine = FakeEngine()
    with patch("app.improvement.workflow.BedrockEngine", return_value=engine):
        result = improve_review(FakeBox([source, new]), SimpleNamespace(), run, ANSWERS)
    assert invented in result["report_markdown"]
    assert result["evaluations"]["final"]["report_hash"] == report_hash(result["report_markdown"])
    audit = engine.payloads[-1]["deterministic_report_guards"]["complete_body_quote_audit"]
    assert audit["unsupported_paragraph_count"] == 1
    assert audit["existing_prose_preserved"] is True
    assert any("direct quotation" in issue["message"] for issue in result["evaluations"]["final"]["issues"])
    assert any("correct or remove" in value for value in result["evaluations"]["final"]["improvements"])
    assert any("Employee wording was preserved" in value for value in result["coverage"]["warnings"])


def test_only_exact_resolved_neutral_gaps_are_cleaned_before_fresh_evaluation():
    run, source, new = fixture()
    reflection_gap = "Source-backed details are needed for a personal reflection."
    goals_gap = "Source-backed details are needed for individual next-year goals."
    run["report_markdown"] = run["report_markdown"].replace("## Leadership Principles Summary", reflection_gap + "\n\n## Leadership Principles Summary")
    run["report_markdown"] = run["report_markdown"].replace("My manager and I have not agreed my individual goals.", goals_gap + "\n\nMy manager and I have not agreed my individual goals.")
    engine = FakeEngine()
    with patch("app.improvement.workflow.BedrockEngine", return_value=engine):
        result = improve_review(FakeBox([source, new]), SimpleNamespace(), run, ANSWERS)
    assert reflection_gap not in result["report_markdown"]
    assert goals_gap not in result["report_markdown"]
    assert "My manager and I have not agreed my individual goals." in result["report_markdown"]
    assert "This is an employee-edited sentence that must remain exactly intact." in result["report_markdown"]
    assert engine.payloads[-1]["draft"] == result["report_markdown"]
    assert result["evaluations"]["final"]["report_hash"] == report_hash(result["report_markdown"])


@pytest.mark.parametrize("target", [float("nan"), float("inf"), True, 0, 101])
def test_invalid_score_target_cannot_enter_the_model(target):
    run, source, new = fixture()
    with pytest.raises(WorkflowError):
        improve_review(FakeBox([source, new]), SimpleNamespace(), run, ANSWERS, target)
