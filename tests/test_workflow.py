"""Tests for the grounding boundary, not for the model's writing style."""

import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.evaluation import evaluation_schema, report_hash, resolve_rubric
from app.guidelines import LEADERSHIP_PRINCIPLES, REPORT_TEMPLATE
from tests.test_evaluation import evaluation_value

from app.workflow import (
    BedrockEngine,
    WorkflowError,
    _citation_check,
    _find_quote,
    _parse_json,
    _report_schema,
    _validate_fact,
    _apply_report_guards,
    _guard_direct_quotes,
    _literal_peer_feedback,
    _enrich_peer_feedback,
    _restore_template_gaps,
    _canonicalize_report_headings,
    _select_evidence,
    _guard_leadership_section,
    _percent_citation_check,
    _validate_writing_constraints,
    _dense_writing_constraints,
    _writing_length_warning,
    _missing_personal_reflections,
    _clean_questions,
    _final_questions,
    _first_person_future,
    _missing_individual_goals,
    run_workflow,
)


def template_report(summary, feedback="No source-verified peer feedback is supplied in this test."):
    return ("# Annual review\n\n## Annual Review Summary\n\n" + summary
            + "\n\n## Leadership Principles Summary\n\nThe documented actions remain scoped to the employee's contribution."
            + "\n\n## Next Year Goals\n\nIndividual goals require manager agreement."
            + "\n\n## Peer Feedback Summary\n\n" + feedback)


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

    def test_final_direct_quote_guard_removes_invention_despite_known_citation(self):
        invented = "Alex's attention to detail in measurement and instrumentation was crucial for the success of both projects."
        source = {"id": "1001", "name": "manager-context.pdf", "text": "The manager asks for concrete deliverables and personal contribution."}
        report = '# Annual review\n\nI prepared the measurement notebook. [E54]\n\nOne useful piece of feedback was: "' + invented + '" [E54]'
        guarded, checks = _guard_direct_quotes(report, [{"id": "E54", "source_id": "1001"}], [source])
        self.assertNotIn(invented, guarded)
        self.assertIn("I prepared the measurement notebook", guarded)
        self.assertEqual(checks["removed_unsupported_quote_paragraphs"], 1)
        self.assertEqual(checks["unsupported_quotes"], [invented])
        self.assertEqual(checks["issues"][0]["verification_status"], "unsupported_quotation_paragraph_removed_by_code")
        self.assertIn("No replacement was invented", checks["warnings"][0])

    def test_literal_peer_quotes_survive_whitespace_wrapping_and_apostrophes(self):
        source = {"id": "2001", "name": "peer-feedback.pdf", "text": "Alex's validation notebook\nmade the handoff clearer. Alex’s work helped our team."}
        report = '# Annual review\n\nPriya wrote: "Alex\'s validation notebook made the handoff clearer." [E1]\n\nSam wrote: ‘Alex’s work helped our team.’ [E1]\n\nMy team\'s work continued.'
        guarded, checks = _guard_direct_quotes(report, [{"id": "E1", "source_id": "2001"}], [source])
        self.assertEqual(guarded, report)
        self.assertEqual(checks["removed_unsupported_quote_paragraphs"], 0)
        self.assertEqual(checks["warnings"], [])

    def test_removing_only_peer_paragraph_removes_empty_heading_but_keeps_title(self):
        report = '# Annual review\n\n## Projects\n\nI prepared the notebook. [E1]\n\n## Peer Feedback\n\nA peer wrote: "An invented endorsement." [E1]'
        guarded, checks = _guard_direct_quotes(report, [{"id": "E1", "source_id": "1"}], [{"id": "1", "name": "project.docx", "text": "I prepared the notebook."}])
        self.assertTrue(guarded.startswith("# Annual review"))
        self.assertIn("## Projects", guarded)
        self.assertNotIn("## Peer Feedback", guarded)
        self.assertEqual(checks["removed_empty_section_headings"], 1)

    def test_read_source_with_zero_retained_facts_has_explicit_coverage_warning(self):
        sources = [{"id": "1", "name": "project.docx", "text": "Project facts."}, {"id": "2", "name": "peer-feedback.pdf", "text": "A readable peer observation.", "analyzed_characters": 28}]
        _, checks = _guard_direct_quotes("# Annual review\n\nI prepared the notebook. [E1]", [{"id": "E1", "source_id": "1"}], sources)
        self.assertEqual(checks["files_without_verified_evidence"], ["peer-feedback.pdf"])
        self.assertIn("peer-feedback.pdf", checks["warnings"][0])
        self.assertIn("do not imply factual coverage", checks["warnings"][0])

    def test_strict_peer_fallback_retains_only_literal_real_quotes_and_reviewer_context(self):
        from app.box_client import extract_text
        path = Path(__file__).resolve().parents[1] / "demo-materials/files/09-peer-feedback.pdf"
        source = {"id": "2001", "name": path.name, "url": "https://app.box.com/file/2001", "text": extract_text(path.read_bytes(), "pdf"), "document_category": "Peer Feedback"}
        facts = _literal_peer_feedback(source)
        self.assertEqual(len(facts), 2)
        self.assertEqual([item["project"] for item in facts], ["Atlas", "Beacon"])
        for fact in facts:
            self.assertIn(fact["quote"], source["text"])
            self.assertEqual(fact["claim"], fact["quote"])
            self.assertEqual(fact["attribution"], "other")
            self.assertEqual(fact["status"], "uncertain")
            self.assertEqual(fact["evidence_type"], "qualitative_feedback")
        self.assertIn("Priya Shah", facts[0]["reviewer_context"])
        self.assertIn("Sam Wilson", facts[1]["reviewer_context"])
        already_extracted = [{"source_id": source["id"], "quote": '"' + facts[1]["quote"] + '"', "project": "Unspecified"}]
        _enrich_peer_feedback(source, already_extracted)
        self.assertIn("Sam Wilson", already_extracted[0]["reviewer_context"])
        self.assertEqual(already_extracted[0]["project"], "Beacon")
        self.assertEqual(_literal_peer_feedback({**source, "document_category": "Projects"}), [])
        self.assertEqual(_literal_peer_feedback({**source, "text": "A paraphrased summary without any direct quotation."}), [])

    def test_required_template_order_is_checked_and_guard_gaps_restore_all_four_sections(self):
        headings = [item["heading"] for item in REPORT_TEMPLATE]
        report = template_report("I prepared the measurement notebook. " * 6 + "[E1]")
        _report_schema([{"id": "E1"}], headings)({"report_markdown": report})
        with self.assertRaises(ValueError):
            _report_schema([{"id": "E1"}], headings)({"report_markdown": report.replace("## Peer Feedback Summary", "## Other Feedback")})
        without_peer = report.split("## Peer Feedback Summary")[0].strip()
        restored, gaps = _restore_template_gaps(without_peer, headings)
        self.assertEqual(gaps, ["Peer Feedback Summary"])
        self.assertIn("Source-backed details are needed to complete this section.", restored)
        _report_schema([{"id": "E1"}], headings)({"report_markdown": restored})

    def test_template_header_normalization_accepts_numbering_not_missing_or_unknown_sections(self):
        headings = [item["heading"] for item in REPORT_TEMPLATE]
        report = template_report("I prepared the measurement notebook. " * 6 + "[E1]")
        decorated = report
        for index, heading in enumerate(headings, 1):
            decorated = decorated.replace("## " + heading, f"## {index}. **{heading}:**")
        canonical = _canonicalize_report_headings(decorated, headings)
        _report_schema([{"id": "E1"}], headings)({"report_markdown": canonical})
        self.assertEqual(canonical, report)
        with self.assertRaises(ValueError):
            _report_schema([{"id": "E1"}], headings)({"report_markdown": _canonicalize_report_headings(decorated.replace("Peer Feedback Summary", "Made Up Feedback"), headings)})
        with self.assertRaises(ValueError):
            _report_schema([{"id": "E1"}], headings)({"report_markdown": canonical.replace("[E1]", "[E999]")})
        hierarchy = report
        for heading in headings:
            hierarchy = hierarchy.replace("## " + heading, "# " + heading)
        hierarchy = hierarchy.replace("I prepared", "## Project detail\n\nI prepared", 1)
        restored = _canonicalize_report_headings(hierarchy, headings)
        self.assertTrue(restored.startswith("# Annual review"))
        self.assertIn("### Project detail", restored)
        _report_schema([{"id": "E1"}], headings)({"report_markdown": restored})

    def test_evidence_selection_caps_twenty_without_losing_metrics_roles_feedback_or_limits(self):
        def fact(quote, project, category, status, attribution="team", document_category="Projects"):
            return {"id": "old", "quote": quote, "claim": quote, "project": project, "category": category, "status": status, "attribution": attribution, "document_category": document_category, "source_name": "project.docx", "source_id": project}
        critical = [
            fact("The Atlas team pilot covered 300 administrators and reduced setup from 10 to 8 minutes, or 20%.", "Atlas", "impact", "measured"),
            fact("The Beacon team reduced search from 4.2 to 3.1 minutes, or 26.2%.", "Beacon", "impact", "measured"),
            fact("Atlas design target was 30%, from 10 to 7 minutes.", "Atlas", "impact", "planned"),
            fact("Beacon design target was 35%, from 4.2 to 2.7 minutes.", "Beacon", "impact", "planned"),
            fact("I owned the Atlas instrumentation and validation notebook.", "Atlas", "work_detail", "delivered", "employee"),
            fact("I built the Beacon prototype and evaluation harness.", "Beacon", "work_detail", "delivered", "employee"),
            fact("The pilot does not isolate Alex's individual causal impact.", "Atlas", "context", "uncertain"),
            fact("Beacon results are limited to the pilot, not a broader rollout.", "Beacon", "context", "uncertain"),
            fact("Priya said the Atlas verification queries clarified the task boundary.", "Atlas", "feedback", "uncertain", "other", "Peer Feedback"),
            fact("Sam said the Beacon harness made the pilot repeatable.", "Beacon", "feedback", "uncertain", "other", "Peer Feedback"),
            fact("Proposed next year: measure Atlas validation changes.", "Atlas", "product_direction", "planned"),
            fact("Proposed next year: evaluate Beacon knowledge freshness.", "Beacon", "product_direction", "planned"),
        ]
        filler = [fact(f"I implemented validation checks for measurement stage {index} and documented the decision.", "Atlas", "work_detail", "delivered", "employee") for index in range(40)]
        metadata = fact("Project design\nDate: 2026-01-01\nAuthor: Alex\nProject: Atlas\nStatus: complete", "Atlas", "context", "delivered")
        duplicate = {**critical[0], "source_name": "stale-status-snapshot.pdf"}
        selected = _select_evidence(critical + filler + [metadata, duplicate], limit=100)
        self.assertEqual(len(selected), 20)
        self.assertEqual([item["id"] for item in selected], [f"E{index}" for index in range(1, 21)])
        quotes = [item["quote"] for item in selected]
        self.assertTrue(all(item["quote"] in quotes for item in critical))
        self.assertEqual(quotes.count(critical[0]["quote"]), 1)
        self.assertNotIn(metadata["quote"], quotes)
        self.assertEqual(len(_select_evidence([metadata, critical[0]])), 1)

    def test_selection_does_not_fill_twenty_with_metadata_and_weak_technical_fragments(self):
        weak = [{"quote": f"I added event {index}.", "claim": "Added an event.", "category": "work_detail", "status": "delivered", "attribution": "employee"} for index in range(30)]
        self.assertEqual(_select_evidence(weak), [])

    def test_final_leadership_screen_removes_known_unsupported_inferences(self):
        report = template_report("I implemented source-backed work. " * 6 + "[E1]")
        body = "\n\n".join(["**Ownership**\n\nI owned the measurement and handover. [E1]", "**Dive Deep**\n\nI investigated and validated the data. [E1]", "**Frugality**\n\nI used limited resources by writing SQL. [E1]", "**Hire and Develop the Best**\n\nI developed others by selecting tasks. [E1]", "**Bias for Action**\n\nI made decisions under uncertainty by writing checks. [E1]"])
        report = report.replace("The documented actions remain scoped to the employee's contribution.", body)
        guarded, checks = _guard_leadership_section(report, [{"id": "E1", "quote": "I owned measurement, wrote SQL queries, investigated the data and handed over validation checks.", "attribution": "employee", "status": "delivered"}])
        self.assertIn("**Ownership**", guarded)
        self.assertIn("**Dive Deep**", guarded)
        self.assertNotIn("**Frugality**", guarded)
        self.assertNotIn("**Hire and Develop", guarded)
        self.assertNotIn("**Bias for Action**", guarded)
        self.assertEqual(len(checks["issues"]), 3)
        self.assertEqual(len(checks["retained_principles"]), 2)
        _report_schema([{"id": "E1"}], [item["heading"] for item in REPORT_TEMPLATE])({"report_markdown": guarded})

    def test_unselected_verified_document_does_not_become_a_zero_fact_gap(self):
        sources = [{"id": "1", "name": "selected.docx", "text": "Selected fact."}, {"id": "2", "name": "not-selected.docx", "text": "Another verified fact."}]
        selected = [{"id": "E1", "source_id": "1"}]
        _, checks = _guard_direct_quotes("# Annual review\n\nSelected fact. [E1]", selected, sources, all_evidence=selected + [{"id": "E2", "source_id": "2"}])
        self.assertEqual(checks["files_without_verified_evidence"], [])
        self.assertEqual(checks["warnings"], [])

    def test_citation_digits_without_metric_do_not_add_team_measurement_boilerplate(self):
        report = "# Annual review\n\nI investigated the task boundaries and shared the findings. [E17]"
        evidence = [{"id": "E17", "quote": "The team measured a 20% improvement.", "status": "measured", "attribution": "team", "category": "impact"}]
        guarded, checks = _apply_report_guards(report, evidence, False)
        self.assertEqual(guarded, report)
        self.assertEqual(checks["explicit_team_outcome_disclosures_added"], 0)

    def test_percentage_claim_must_be_supported_by_its_own_paragraph_citations(self):
        evidence = [{"id": "E1", "quote": "The design target was 30%."}, {"id": "E2", "quote": "The team pilot observed a 20% reduction."}]
        report = template_report("The team pilot observed a 20% reduction, against a 30% target. [E1] " + "The employee supplied the measurement work. " * 4)
        self.assertEqual(_percent_citation_check(report, evidence)[0]["percentages"], ["20%"])
        with self.assertRaisesRegex(ValueError, "percentage claims"):
            _report_schema(evidence, [item["heading"] for item in REPORT_TEMPLATE])({"report_markdown": report})
        corrected = report.replace("[E1]", "[E1] [E2]")
        self.assertEqual(_percent_citation_check(corrected, evidence), [])
        _report_schema(evidence, [item["heading"] for item in REPORT_TEMPLATE])({"report_markdown": corrected})

    def test_percentage_matching_preserves_sign_and_complete_numeric_value(self):
        mismatches = (("-20%", "20%"), ("\u221220%", "20%"), ("1,000%", "0%"), (".5%", "20%"), ("-.5%", ".5%"))
        for claimed, recorded in mismatches:
            with self.subTest(claimed=claimed, recorded=recorded):
                evidence = [{"id": "E1", "quote": "The team measured " + recorded + "."}]
                report = template_report("The team measured " + claimed + ". [E1] " + "The documented work supplied measurement context. " * 3)
                self.assertTrue(_percent_citation_check(report, evidence))
                with self.assertRaisesRegex(ValueError, "percentage claims"):
                    _report_schema(evidence, [item["heading"] for item in REPORT_TEMPLATE])({"report_markdown": report})
        equivalents = (("-20%", "\u221220%"), ("1,000%", "1000%"), (".5%", "0.5%"), ("+20%", "20%"), ("\u22121,000.5%", "-1000.50%"))
        for claimed, recorded in equivalents:
            with self.subTest(claimed=claimed, recorded=recorded):
                self.assertEqual(_percent_citation_check("The team measured " + claimed + ". [E1]", [{"id": "E1", "quote": "The team measured " + recorded + "."}]), [])

    def test_grouped_references_are_expanded_without_accepting_unknown_ids(self):
        report = template_report("Documented work " * 20 + "[E1, E2]")
        normalized = _canonicalize_report_headings(report, [item["heading"] for item in REPORT_TEMPLATE])
        self.assertIn("[E1] [E2]", normalized)
        _report_schema([{"id": "E1"}, {"id": "E2"}])({"report_markdown": normalized})
        normalized = _canonicalize_report_headings(report.replace("E2]", "E999]"), None)
        with self.assertRaises(ValueError):
            _report_schema([{"id": "E1"}, {"id": "E2"}])({"report_markdown": normalized})

    def test_dense_prose_constraint_rejects_abbreviated_project_and_preserves_sparse_inputs(self):
        fact = {"project": "Atlas", "status": "delivered", "attribution": "employee"}
        self.assertIsNone(_dense_writing_constraints([fact] * 3, 8))
        constraints = _dense_writing_constraints([fact] * 20, 62)
        self.assertEqual(constraints["min_words"], 600)
        paragraph = "I implemented and verified the documented measurement work with the project team. " * 5
        report = template_report("### Atlas\n\n" + paragraph)
        with self.assertRaisesRegex(ValueError, "at least two complete prose paragraphs"):
            _validate_writing_constraints(report, constraints)
        report = template_report("### Atlas\n\n" + paragraph * 6 + "\n\n" + paragraph * 6)
        _validate_writing_constraints(report, constraints)
        short_but_complete = template_report("### Atlas\n\n" + paragraph + "\n\n" + paragraph)
        _validate_writing_constraints(short_but_complete, constraints)
        self.assertIsNotNone(_writing_length_warning(short_but_complete, constraints))
        _validate_writing_constraints(template_report("Brief source-grounded work."), None)
        self.assertIsNotNone(_writing_length_warning(template_report("Brief source-grounded work."), constraints))
        self.assertIsNone(_writing_length_warning(template_report("Brief source-grounded work."), None))

    def test_json_fences_and_malformed_responses(self):
        self.assertEqual(_parse_json('```json\n{"facts": []}\n```'), {"facts": []})
        self.assertEqual(_parse_json('Here is the result: {"facts": []}'), {"facts": []})
        with self.assertRaises(ValueError):
            _parse_json('{"facts": [')


class ReviewQuestionTests(unittest.TestCase):
    def test_negated_reflection_description_cannot_resolve_its_own_absence(self):
        statement = "This log does not record a personal challenge or a reflection on what I would do differently."
        for text in (statement, statement.replace("a reflection", "a\nreflection")):
            with self.subTest(text=text):
                self.assertTrue(_missing_personal_reflections([{"text": text}], "2026"))

        actual_reflection = "Personal reflection: My biggest challenge was inconsistent event definitions. I learned to agree the boundaries before implementation."
        self.assertFalse(_missing_personal_reflections([{"text": statement + " " + actual_reflection}], "2026"))

    def test_actual_demo_documents_still_require_personal_reflection(self):
        from app.box_client import extract_text

        materials = Path(__file__).resolve().parents[1] / "demo-materials"
        manifest = json.loads((materials / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 9)
        sources = []
        for name in manifest:
            file = materials / "files" / name
            sources.append({"name": name, "text": extract_text(file.read_bytes(), file.suffix[1:])})

        self.assertIn("what I would do differently", " ".join(source["text"] for source in sources))
        self.assertTrue(_missing_personal_reflections(sources, "2026"))

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

    def test_addendum_goal_question_is_not_evidence_of_agreement(self):
        old = {"text": "Alex and the manager have not yet agreed on 2027 individual goals."}
        question = "What individual goals would you propose for 2027, and which have you agreed with your manager?"
        addendum = {"text": "Employee-supplied annual-review addendum\nReview year: 2026\nQuestions being addressed\n" + question + "\nEmployee answers\nI learned to agree event boundaries before implementation."}
        self.assertTrue(_missing_individual_goals([old, addendum], "2027"))
        addendum["text"] += "\nMy manager and I approved my 2027 individual goals: own the pilot measurement plan."
        self.assertFalse(_missing_individual_goals([old, addendum], "2027"))

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
    def test_required_evaluation_invalid_twice_fails_instead_of_fabricating_scores(self):
        engine = BedrockEngine.__new__(BedrockEngine)
        engine.model_id = "amazon.nova-lite-v1:0"
        engine.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}
        value = evaluation_value([{"id": "E1"}])
        value["dimensions"][0]["score"] = 6

        class Client:
            def converse(self, **kwargs):
                return {"output": {"message": {"content": [{"text": json.dumps(value)}]}}, "stopReason": "end_turn"}

        engine.client = Client()
        with self.assertRaises(WorkflowError) as error:
            engine.json_call("Score this draft.", {}, 6000, evaluation_schema([{"id": "E1"}], resolve_rubric(), [item["name"] for item in LEADERSHIP_PRINCIPLES]))
        self.assertEqual(error.exception.code, "model_output")
        self.assertIn("Dimension scores", error.exception.validation_reason)
        self.assertNotIn("Dimension scores", str(error.exception))
        self.assertEqual(engine.usage["calls"], 2)

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
    def test_two_fresh_evaluations_surround_mandatory_revision_and_final_guards(self):
        text = "Alex prepared the measurement notebook and validated the pilot sample."
        initial = template_report("I prepared the measurement notebook and checked the pilot sample. " * 4 + "[E1]")
        revised = template_report("I prepared the notebook; the team used it to review the pilot sample. " * 4 + "[E1]", 'A peer wrote: "An invented endorsement." [E1]')
        calls, evaluations, revisions = [], [], []

        class Box:
            def discover(self, folder_id, max_files):
                return {"files": [{"id": "1", "name": "project.docx"}], "discovered": 1}

            def read_text(self, file):
                return text

            def ask(self, file_ids, prompt):
                return {"answer": "Advisory review of the initial draft only.", "citations": []}

        class Engine:
            def __init__(self, settings):
                self.usage = {"calls": 0}

            def json_call(self, system, payload, max_tokens, validate):
                self.usage["calls"] += 1
                if "single document passage" in system:
                    calls.append("extract")
                    value = {"facts": [{"quote": text, "claim": "Prepared notebook and validated sample.", "attribution": "employee", "status": "delivered"}]}
                else:
                    calls.append(payload["phase"] + "_evaluation")
                    evaluations.append(payload)
                    value = evaluation_value(payload["evidence"], score=4 if payload["phase"] == "initial" else 3)
                    if payload["phase"] == "initial":
                        value["improvements"] = ["Clarify individual actions and the team's use of the notebook."]
                validate(value)
                return value

            def markdown_call(self, system, payload, max_tokens, evidence):
                self.usage["calls"] += 1
                if "initial_evaluation" in payload:
                    calls.append("revision")
                    revisions.append(payload)
                    return revised
                calls.append("draft")
                return initial

        updates = []
        with patch("app.workflow.BedrockEngine", Engine):
            result = run_workflow(Box(), SimpleNamespace(), {"folder_id": "0", "employee_name": "Alex Chen", "year": 2026}, lambda **fields: updates.append(fields))
        self.assertEqual(calls, ["extract", "draft", "initial_evaluation", "revision", "final_evaluation"])
        self.assertEqual(revisions[0]["review_issues"], [])
        self.assertTrue(revisions[0]["improvement_advice"])
        self.assertEqual(evaluations[0]["draft"], result["initial_draft"])
        self.assertEqual(evaluations[1]["draft"], result["report_markdown"])
        self.assertNotIn("An invented endorsement", evaluations[1]["draft"])
        self.assertIn("## Peer Feedback Summary", evaluations[1]["draft"])
        self.assertIn("Source-backed details are needed to complete this section.", evaluations[1]["draft"])
        self.assertNotIn("box_ai_review", evaluations[1])
        self.assertNotIn("initial_evaluation", evaluations[1])
        self.assertEqual(result["evaluations"]["initial"]["report_hash"], report_hash(result["initial_draft"]))
        self.assertEqual(result["evaluations"]["final"]["report_hash"], report_hash(result["report_markdown"]))
        self.assertEqual(result["evaluations"]["initial"]["overall_score"], 80)
        self.assertEqual(result["evaluations"]["final"]["overall_score"], 60)
        self.assertEqual(result["evaluations"]["overall_delta"], -20)
        self.assertEqual(result["review"]["revision_rounds"], 1)
        self.assertEqual(result["review"]["checks"]["direct_quotes"]["removed_unsupported_quote_paragraphs"], 1)
        self.assertTrue(any(update.get("stage") == "revise" and update.get("evaluations", {}).get("initial") for update in updates))
        self.assertTrue(any(update.get("stage") == "final_evaluation" and update.get("progress") == 93 for update in updates))

    def test_misclassified_work_detail_does_not_resolve_personal_reflection_gap(self):
        work_detail = "I checked the pilot sample and verified the event timestamps."
        text = "Review year: 2026\nNo personal account of a significant challenge or lesson learned has been recorded.\n" + work_detail
        report = template_report("I checked the pilot data and verified task timestamps. " * 5 + "[E1]\n\n### Growth and Challenges\n\nI improved my skills and learned to lead the project. [E1]")

        class Box:
            def discover(self, folder_id, max_files):
                return {"files": [{"id": "1001", "name": "work-log.docx", "document_category": "Projects"}], "discovered": 1}

            def read_text(self, file):
                return text

            def ask(self, file_ids, prompt):
                return {"answer": "Personal reflection is still missing.", "citations": []}

        class Engine:
            def __init__(self, settings):
                self.usage = {"calls": 0}

            def json_call(self, system, payload, max_tokens, validate):
                self.usage["calls"] += 1
                if "single document passage" in system:
                    value = {"facts": [{"quote": work_detail, "claim": "Checked the pilot sample.", "category": "learning", "attribution": "employee", "status": "delivered"}]}
                else:
                    value = evaluation_value(payload["evidence"])
                validate(value)
                return value

            def markdown_call(self, system, payload, max_tokens, evidence):
                self.usage["calls"] += 1
                return report

        with patch("app.workflow.BedrockEngine", Engine):
            result = run_workflow(Box(), SimpleNamespace(), {"folder_id": "0", "employee_name": "Alex Chen", "year": 2026, "language": "en"}, lambda **fields: None)
        self.assertEqual(result["evidence"][0]["category"], "learning")
        self.assertTrue(result["task"]["personal_reflection_missing_in_sources"])
        self.assertIn("significant personal challenge", result["missing_information"][0])
        self.assertNotIn("Growth and Challenges", result["report_markdown"])

    def test_expected_and_actual_impact_stay_distinct_and_box_failure_is_visible(self):
        text = (
            "The design expected a 30% latency improvement.\n"
            "The team measured a 20% latency improvement after launch.\n"
            "Alex implemented the query cache and wrote the rollout plan."
        )
        report = template_report(
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
                    value = evaluation_value(payload["evidence"])
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
        self.assertTrue(result["review"]["revision_performed"])
        self.assertEqual(result["coverage"]["character_coverage"], 1.0)
        self.assertEqual(result["coverage"]["rejected_facts"], 1)
        self.assertNotIn("sensitive provider", json.dumps(result))
        self.assertEqual(result["usage"]["calls"], 5)
        self.assertEqual(result["missing_information"], [])
        self.assertEqual(updates[-1]["progress"], 100)


if __name__ == "__main__":
    unittest.main()
