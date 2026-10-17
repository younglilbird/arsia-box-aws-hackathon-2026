"""Tests for the grounding boundary, not for the model's writing style."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.workflow import (
    BedrockEngine,
    WorkflowError,
    _citation_check,
    _find_quote,
    _parse_json,
    _report_schema,
    _validate_fact,
    _apply_report_guards,
    _missing_personal_reflections,
    _clean_questions,
    _final_questions,
    _first_person_future,
    _missing_individual_goals,
    run_workflow,
)


class GroundingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "1001", "name": "design-and-results.md", "url": "https://app.box.com/file/1001",
            "text": "The design expected a 30% latency improvement.\nThe team measured a 20% latency improvement after launch.",
        }

    def test_rejects_fabricated_or_ellipsized_quotes(self):
        self.assertIsNone(_find_quote(self.source["text"], "The team measured a 30% latency improvement"))
        self.assertIsNone(_find_quote(self.source["text"], "The design ... 30% latency improvement"))
        self.assertIsNone(_find_quote(self.source["text"], "20%"))

    def test_pdf_whitespace_is_normalized_but_numbers_are_not(self):
        text = "The team measured a\n 20% latency improvement."
        self.assertEqual(_find_quote(text, "The team measured a 20% latency improvement."), text)
        self.assertIsNone(_find_quote(text, "The team measured a 30% latency improvement."))

    def test_source_identity_and_personal_attribution_are_separate(self):
        fact = {
            "source_id": "wrong-file", "quote": "The team measured a 20% latency improvement after launch.",
            "claim": "The team improved latency 20%.", "attribution": "team", "status": "measured",
        }
        self.assertIsNone(_validate_fact(fact, self.source))
        fact["source_id"] = "1001"
        validated = _validate_fact(fact, self.source)
        self.assertEqual(validated["source_id"], "1001")
        self.assertEqual(validated["attribution"], "team")
        self.assertEqual(validated["status"], "measured")

    def test_unknown_enum_and_bad_model_types_cannot_gain_certainty(self):
        checked = _validate_fact({
            "quote": "The design expected a 30% latency improvement.", "claim": "Expected improvement.",
            "status": ["measured"], "attribution": {"employee": True}, "category": [],
        }, self.source)
        self.assertEqual(checked["status"], "uncertain")
        self.assertEqual(checked["attribution"], "uncertain")
        self.assertEqual(checked["category"], "context")

    def test_unknown_citation_ids_block_model_output(self):
        report = "# Annual review\n\n" + "Useful work and project context. " * 10 + "[E999]"
        with self.assertRaises(ValueError):
            _report_schema([{"id": "E1"}])({"report_markdown": report})
        check = _citation_check(report, [{"id": "E1"}])
        self.assertEqual(check["unknown_ids"], ["E999"])
        self.assertFalse(check["valid"])

    def test_native_folder_categories_constrain_plan_and_feedback_facts(self):
        source = {**self.source, "document_category": "Annual Plans"}
        fact = {"quote": "The design expected a 30% latency improvement.", "claim": "30% improvement.", "status": "measured", "attribution": "team", "category": "goal"}
        planned = _validate_fact(fact, source)
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["evidence_type"], "product_plan")
        feedback = _validate_fact(fact, {**source, "document_category": "Peer Feedback"})
        self.assertEqual(feedback["status"], "uncertain")
        self.assertEqual(feedback["evidence_type"], "qualitative_feedback")
        self.assertEqual(feedback["document_category"], "Peer Feedback")
        context = _validate_fact({"quote": "The team measured a 20% latency improvement after launch.", "claim": "A historical 20% pilot result.", "status": "measured", "category": "context", "attribution": "team"}, source)
        self.assertEqual(context["status"], "measured")
        self.assertEqual(context["evidence_type"], "planning_document_context")

    def test_missing_reflection_is_omitted_and_team_metrics_get_explicit_label(self):
        sources = [{"text": "No personal account of a significant challenge, lesson learned or agreed 2027 individual goals has been recorded."}]
        self.assertTrue(_missing_personal_reflections(sources))
        report = "# Annual review\n\n## Projects\n\nThe pilot showed a 20% reduction. [E1]\n\n## Growth and Challenges\n\nI gained experience and learned to lead projects.\n\n## Next-Year Priorities\n\nThe product roadmap proposes validation improvements. [E2]"
        guarded, checks = _apply_report_guards(report, [{"id": "E1", "quote": "The team measured a 20% improvement.", "attribution": "team", "status": "measured"}], True)
        self.assertNotIn("Growth and Challenges", guarded)
        self.assertNotIn("I gained experience", guarded)
        self.assertIn("team-level result", guarded)
        self.assertIn("Next-Year Priorities", guarded)
        self.assertEqual(checks["removed_unsupported_reflection_sections_or_paragraphs"], 1)

    def test_reflection_guard_preserves_business_growth_and_historical_dates(self):
        report = "# Annual review\n\n## Business Growth\n\nThe team launched the product in 2026. [E1]\n\n## Project Challenges\n\nThe source describes a cache capacity limit. [E2]"
        evidence = [{"id": "E1", "quote": "The team launched the product in 2026.", "status": "delivered", "attribution": "team", "category": "context"}]
        guarded, checks = _apply_report_guards(report, evidence, True)
        self.assertIn("Business Growth", guarded)
        self.assertIn("Project Challenges", guarded)
        self.assertNotIn("measurements", guarded)
        self.assertEqual(checks["explicit_team_outcome_disclosures_added"], 0)

    def test_json_fences_and_malformed_responses(self):
        self.assertEqual(_parse_json('```json\n{"facts": []}\n```'), {"facts": []})
        self.assertEqual(_parse_json('Here is the result: {"facts": []}'), {"facts": []})
        with self.assertRaises(ValueError):
            _parse_json('{"facts": [')


class ReviewQuestionTests(unittest.TestCase):
    def test_new_reflection_resolves_old_absence_and_growth_is_preserved(self):
        old = {"text": "Review year: 2026\nNo personal account of a significant challenge or lesson learned has been recorded."}
        new = {"text": "Review year: 2026\nPersonal reflection: My biggest challenge was inconsistent task definitions. I learned to review event boundaries with Design before instrumenting them."}
        self.assertTrue(_missing_personal_reflections([old], "2026"))
        missing = _missing_personal_reflections([old, new], "2026")
        self.assertFalse(missing)
        self.assertFalse(_missing_personal_reflections([new, old], "2026"))
        report = "# Annual review\n\n## Growth and Challenges\n\nI learned to agree event boundaries before implementation. [E1]"
        guarded, checks = _apply_report_guards(report, [{"id": "E1"}], missing)
        self.assertIn("Growth and Challenges", guarded)
        self.assertIn("I learned", guarded)
        self.assertEqual(checks["removed_unsupported_reflection_sections_or_paragraphs"], 0)

    def test_new_agreed_goals_resolve_old_not_yet_agreed_statement(self):
        old = {"text": "Alex and the manager have not yet agreed on 2027 individual goals."}
        new = {"text": "My manager and I approved my 2027 individual goals: own the pilot measurement plan and document the rollout decision."}
        self.assertTrue(_missing_individual_goals([old], "2027"))
        self.assertFalse(_missing_individual_goals([old, new], "2027"))
        self.assertFalse(_missing_individual_goals([new, old], "2027"))

    def test_other_year_and_templates_do_not_resolve_current_absence(self):
        missing_reflection = {"text": "Review year: 2026\nNo personal account of a significant challenge or lesson learned has been recorded."}
        prior_reflection = {"text": "Review year: 2025\nMy biggest challenge was debugging an old migration. I learned to improve rollback plans."}
        template = {"text": "# Template\nPersonal reflection: My biggest challenge was [describe your challenge]. I learned to [insert lesson]."}
        self.assertTrue(_missing_personal_reflections([missing_reflection, prior_reflection, template], "2026"))
        missing_goals = {"text": "Alex and the manager have not yet agreed on 2027 individual goals."}
        prior_goals = {"text": "My manager and I approved my 2026 individual goals: improve the pilot measurements."}
        proposed = {"text": "We have not agreed on 2027 individual goals. These proposed directions are only discussion topics."}
        self.assertTrue(_missing_individual_goals([missing_goals, prior_goals, proposed], "2027"))

    def test_placeholders_are_removed_and_questions_deduplicated(self):
        questions = _clean_questions(["specific material uncertainty", "material question still requiring the employee", "What personal goals need manager agreement?", "What personal goals need manager agreement?", "Specific material uncertainty regarding the broader rollout."])
        self.assertEqual(questions, ["What personal goals need manager agreement?", "the broader rollout."])

    def test_final_questions_use_whole_evidence_and_keep_unanswered_scope_distinct(self):
        evidence = [{"id": "E1", "project": "Atlas", "status": "measured", "quote": "Median setup time decreased from 10 to 8 minutes, a 20% reduction."}]
        questions = _final_questions([
            "What were the actual measured results of the Atlas pilot?",
            "What was your personal challenge or lessons learned?",
            "What individual goals have you agreed for 2027?",
            "Is there evidence of production-wide impact after the broader Atlas rollout?",
            "specific material uncertainty",
        ], evidence, True, True, "2027")
        self.assertEqual(len(questions), 3)
        self.assertIn("significant personal challenge", questions[0])
        self.assertIn("individual goals", questions[1])
        self.assertIn("production-wide", questions[2])
        self.assertNotIn("actual measured results", " ".join(questions))

    def test_actual_next_year_paragraph_uses_first_person_without_changing_evidence(self):
        report = "# Alex Chen Annual Review\n\n## Projects\n\nAlex built the prototype. [E31]\n\n## Next-Year Priorities\n\nThese are proposed directions, not completed features [E48]. Alex and the manager have not yet agreed on 2027 individual goals [E49]. The team's product roadmap must not be substituted for Alex's personal commitments [E50]."
        revised = _first_person_future(report, "Alex Chen")
        self.assertIn("Alex Chen Annual Review", revised)
        self.assertIn("Alex built the prototype", revised)
        future = revised.split("## Next-Year Priorities", 1)[1]
        self.assertNotIn("Alex", future)
        self.assertIn("My manager and I have not yet agreed", future)
        self.assertIn("my personal commitments [E50]", future)
        self.assertTrue(_missing_individual_goals([{"text": "Alex and the manager have not yet agreed on 2027 individual goals."}]))


class BoundedBedrockTests(unittest.TestCase):
    def test_revision_rejects_format_only_change_then_accepts_substantive_fix(self):
        original = "# Annual review\n\n" + "I ensured the successful delivery of this team project. " * 5 + "[E1]"
        corrected = "# Annual review\n\n" + "I owned the measurement work; the team owned delivery and rollout. " * 5 + "[E1]"
        engine = BedrockEngine.__new__(BedrockEngine)
        engine.model_id = "amazon.nova-lite-v1:0"
        engine.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}

        class Client:
            def __init__(self):
                self.calls = 0

            def converse(self, **kwargs):
                self.calls += 1
                text = original.replace("\n", "\n\n") if self.calls == 1 else corrected
                return {"output": {"message": {"content": [{"text": text}]}}, "stopReason": "end_turn"}

        engine.client = Client()
        result = engine.markdown_call("Correct the report.", {"draft": original, "review_issues": [{"message": "Overstated ownership."}]}, 2000, [{"id": "E1"}])
        self.assertEqual(result, corrected)
        self.assertEqual(engine.client.calls, 2)

    def test_invalid_json_retries_once_and_max_tokens_is_explicit(self):
        engine = BedrockEngine.__new__(BedrockEngine)
        engine.model_id = "amazon.nova-lite-v1:0"
        engine.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}

        class Client:
            def __init__(self):
                self.calls = []

            def converse(self, **kwargs):
                self.calls.append(kwargs)
                return {"output": {"message": {"content": [{"text": "invalid JSON"}]}}, "usage": {"inputTokens": 10, "outputTokens": 2}}

        client = Client()
        engine.client = client
        with self.assertRaises(WorkflowError):
            engine.json_call("Return facts", {}, 1234, lambda _: None)
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all(call["inferenceConfig"]["maxTokens"] == 1234 for call in client.calls))
        self.assertEqual(engine.usage["input_tokens"], 20)


class WorkflowIntegrationTests(unittest.TestCase):
    def test_expected_and_actual_impact_stay_distinct_and_box_failure_is_visible(self):
        text = (
            "The design expected a 30% latency improvement.\n"
            "The team measured a 20% latency improvement after launch.\n"
            "Alex implemented the query cache and wrote the rollout plan."
        )
        report = (
            "# Alex Annual Review\n\n"
            "## Project contribution\n\n"
            "I implemented the query cache and wrote the rollout plan. The team measured a 20% latency "
            "improvement after launch, compared with the design's expected 30%. My specific contribution "
            "was the query cache and rollout plan, and the measured result belongs to the team. [E1] [E2] [E3]"
        )

        class Box:
            def discover(self, folder_id, max_files):
                return {"files": [{"id": "1001", "name": "project.md", "extension": "md"}], "discovered": 1, "skipped": [], "truncated": False}

            def read_text(self, file):
                return text

            def ask(self, file_ids, prompt):
                raise RuntimeError("sensitive provider details should not be displayed")

        class Engine:
            def __init__(self, settings):
                self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

            def json_call(self, system, payload, max_tokens, validate):
                self.usage["calls"] += 1
                if "single document passage" in system:
                    value = {"missing_information": ["specific material uncertainty", "What were the actual measured results of the Atlas pilot?"], "facts": [
                        {"quote": "The design expected a 30% latency improvement.", "claim": "Design expected 30%.", "status": "planned", "attribution": "team"},
                        {"quote": "The team measured a 20% latency improvement after launch.", "claim": "Team measured 20%.", "status": "measured", "attribution": "team"},
                        {"quote": "Alex implemented the query cache and wrote the rollout plan.", "claim": "Alex implemented cache and rollout.", "status": "delivered", "attribution": "employee"},
                        {"quote": "Alex personally improved latency 90%.", "claim": "Fake result."},
                    ]}
                elif "independent source-based editor" in system:
                    self_test = payload["original_sources"][0]["text"]
                    assert self_test == text
                    value = {"issues": [], "checks": {"attribution": "Team and employee contribution are separated."}}
                else:
                    value = {"report_markdown": report, "missing_information": ["Confirm the reporting period."]}
                validate(value)
                return value

            def markdown_call(self, system, payload, max_tokens, evidence):
                self.usage["calls"] += 1
                _report_schema(evidence)({"report_markdown": report})
                return report

        updates = []
        with patch("app.workflow.BedrockEngine", Engine):
            result = run_workflow(Box(), SimpleNamespace(), {"folder_id": "0", "employee_name": "Alex", "year": 2026, "language": "en", "max_files": 12}, lambda **fields: updates.append(fields))
        self.assertEqual(len(result["evidence"]), 3)
        self.assertEqual(result["evidence"][0]["status"], "planned")
        self.assertEqual(result["evidence"][1]["status"], "measured")
        self.assertEqual(result["evidence"][1]["attribution"], "team")
        self.assertEqual(result["evidence"][2]["attribution"], "employee")
        self.assertEqual(result["review"]["box_ai"]["status"], "unavailable")
        self.assertFalse(result["review"]["revision_performed"])
        self.assertEqual(result["coverage"]["character_coverage"], 1.0)
        self.assertEqual(result["coverage"]["rejected_facts"], 1)
        self.assertNotIn("sensitive provider", json.dumps(result))
        self.assertEqual(result["usage"]["calls"], 3)
        self.assertEqual(result["missing_information"], [])
        self.assertEqual(updates[-1]["progress"], 100)


if __name__ == "__main__":
    unittest.main()
