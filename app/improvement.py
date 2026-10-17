"""Question-scoped edits to one existing draft and a fresh exact-body evaluation.

The caller owns source-version checks, persistence and Box publishing. This
module performs no writes outside memory and never re-extracts the old files.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Callable

from app.evaluation import EVALUATION_INSTRUCTION, build_evaluation, evaluation_schema, report_hash, resolve_rubric
from app.guidelines import LEADERSHIP_PRINCIPLES, REPORT_TEMPLATE, guideline_context
from app import workflow


PATCH_INSTRUCTION = """
Improve the SAME annual-review draft using the supplied employee answers.
Make only question-relevant edits. Preserve existing project structure and
unrelated prose, including any employee edits. This is a patch task, not a
request to rewrite or shorten the report. Existing metrics and contributions
must stay intact. Use append operations for new context; replace_span is only
for an exact old information-gap or unagreed-goal sentence that the answer now
resolves. Never replace an entire section or an unrelated accomplishment.
Employee answers are self-reported, not independent measurements or peer
feedback. Bind each new fact to an exact contiguous quote IN THE ANSWERS,
not the generated questions or document header. Do not invent a reflection,
agreement, metric or commitment. Goals remain proposals unless agreement is
explicitly reported. A new quantitative outcome needs an explicit self-report
qualification; a proposed numeric target must be clearly a proposal.
Use at most the supplied new_evidence_limit, never more than four new evidence
items. Use only the provided available IDs for those items and only existing
or validated new IDs in patches. Cover each actually answered topic. Separate
personal reflections may need separate quotes, and a proposed next-year goal
needs its own literal goal evidence. Do not spend every slot on reflections
then write an unsupported goals patch. Evidence
quotes allow whitespace differences only. Do not emit source_id; the program
binds new facts to the actual answer document. New goal status is planned;
new answers cannot become independently measured evidence.
Return JSON with this shape:
{"new_evidence":[{"id":"a provided available ID","quote":"literal answer",
"claim":"concise self-reported fact","category":"learning|goal|work_detail|context",
"project":"project or Unspecified","period":"relevant year",
"status":"planned|delivered|uncertain","attribution":"employee"}],
"patches":[{"section":"an allowed exact H2 section name",
"operation":"append|replace_span","anchor":"exact old gap sentence for replace_span, otherwise empty",
"content":"new prose citing the exact matching new_evidence.id in square brackets"}]}
Every emitted patch MUST cite at least one new_evidence item that you emitted
in this response. Existing evidence alone cannot support a new personal answer.
Use individual bracket references, with one ID in each pair of brackets.
Leave unanswered questions, sections and existing information gaps unchanged.
Do not emit a patch merely to state that an answer was not provided. If only
the reflection question was answered, do not patch the goals section.
Keep all four H2 sections and their order; patches must not contain H1/H2
headings. Use complete first-person prose; no project or leadership bullets.
Add a useful reflection or specific proposed next steps when actually supplied.
Do not repeat the existing project narrative, add generic praise, force more
principles, or fabricate questions to chase the advisory target score. Empty
arrays are valid when the answer contains no useful source-backed addition.
""".strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sections(report: str) -> dict[str, tuple[int, int]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", report, re.M))
    return {match[1]: (match.end(), matches[index + 1].start() if index + 1 < len(matches) else len(report)) for index, match in enumerate(matches)}


def _replaceable_gap(text: str) -> bool:
    """Recognize only a complete gap statement, never a mixed factual sentence."""
    plain = re.sub(r"\s+", " ", workflow.CITATION_PATTERN.sub("", text)).strip()
    patterns = (
        r"Source-backed details are needed (?:for a personal reflection|for individual next-year goals|to complete this section)[.!]?",
        r"My manager and I have not (?:yet )?agreed (?:on )?my (?:individual|personal) goals(?: for 20\d{2})?[.!]?",
        r"I have not (?:yet )?agreed (?:on )?my (?:individual|personal) goals(?: for 20\d{2})? with my manager[.!]?",
        r"(?:My )?(?:individual|personal) goals(?: for 20\d{2})? (?:have not|haven't) (?:yet )?been (?:agreed|recorded|documented)[.!]?",
        r"No (?:personal reflection|personal challenge|peer feedback) (?:has been (?:recorded|documented|supplied)|is (?:recorded|documented|available))[.!]?",
    )
    return any(re.fullmatch(pattern, plain, re.I) for pattern in patterns)


def _prospective_personal_intent(text: str) -> bool:
    return bool(re.search(r"\bI\s+(?:propose|plan|intend|aim|will|would like|want)\b|\bmy\s+(?:individual\s+|personal\s+)?goals?\s+(?:is|are|include)\b", text, re.I) or workflow._positive_individual_goals({"text": text}))


def _allowed_sections(questions: list[str], answers: str = "") -> list[str]:
    text = (" ".join(questions) if questions else answers).lower()
    allowed = set()
    if re.search(r"goal|next.year|future|commitment", text):
        allowed.add("Next Year Goals")
    if re.search(r"challenge|reflect|learn|contribut|responsib|impact|metric|accomplish", text):
        allowed.add("Annual Review Summary")
    if re.search(r"leadership|principle", text):
        allowed.add("Leadership Principles Summary")
    if re.search(r"peer|feedback|reviewer", text):
        allowed.add("Peer Feedback Summary")
    answered = set()
    if _prospective_personal_intent(answers):
        answered.add("Next Year Goals")
    if workflow._positive_personal_reflection({"text": answers}) or re.search(r"\bI\s+(?:built|implemented|drafted|validated|delivered|owned|wrote|designed|led)\b", answers, re.I):
        answered.add("Annual Review Summary")
        answered.add("Leadership Principles Summary")
    if re.search(r"peer|feedback|reviewer", answers, re.I):
        answered.add("Peer Feedback Summary")
    return [item["heading"] for item in REPORT_TEMPLATE if item["heading"] in allowed.intersection(answered)]


def _evidence_plan(report: str, evidence: list[dict], sources: list[dict], reserve: int = 2) -> tuple[str, list[dict], list[str], dict]:
    """Reserve bounded answer slots without removing currently cited support."""
    if len(evidence) > 20:
        raise workflow.WorkflowError("This draft needs its existing evidence set reviewed before adding answers.", "improvement_evidence_capacity")
    reserve = min(4, max(1, int(reserve)))
    retained_limit = 20 - reserve
    items = deepcopy(evidence)
    known = {item["id"] for item in items}
    cited = set(workflow.CITATION_PATTERN.findall(report))
    if cited - known:
        raise workflow.WorkflowError("The draft contains an unavailable source reference. Its text has been preserved; review the reference before improving it.", "improvement_citations")
    dropped, consolidated = [], []
    while len(items) > retained_limit:
        unused = next((item for item in reversed(items) if item["id"] not in cited), None)
        if unused is None:
            break
        dropped.append(unused["id"])
        items.remove(unused)
    texts = {str(source["id"]): source["text"] for source in sources}
    while len(items) > retained_limit:
        merged = False
        for index, first in enumerate(items):
            for second in items[index + 1:]:
                if any(first.get(key) != second.get(key) for key in ("source_id", "status", "attribution", "evidence_type")):
                    continue
                text = texts.get(str(first.get("source_id")), "")
                quotes = [workflow._find_quote(text, item.get("quote", "")) for item in (first, second)]
                if not all(quotes):
                    continue
                starts = [text.find(quote) for quote in quotes]
                start, end = min(starts), max(position + len(quote) for position, quote in zip(starts, quotes))
                combined = text[start:end]
                if len(combined) > 1200:
                    continue
                first["quote"] = combined
                first["claim"] = (first.get("claim", "") + "; " + second.get("claim", ""))[:1500]
                first["consolidated_from"] = workflow._unique(first.get("consolidated_from", [first["id"]]) + second.get("consolidated_from", [second["id"]]))
                report = report.replace("[" + second["id"] + "]", "[" + first["id"] + "]")
                report = re.sub(r"(\[E\d+\])(?:[ \t]+\1)+", r"\1", report)
                consolidated.append({"retained_id": first["id"], "removed_id": second["id"], "reason": "Same pinned source, attribution and status; the retained literal quote contains both original quotations."})
                items.remove(second)
                cited.discard(second["id"])
                merged = True
                break
            if merged:
                break
        if not merged:
            break
    capacity = 20 - len(items)
    if capacity < 1:
        raise workflow.WorkflowError("All evidence slots are in use and their references cannot be consolidated safely. The current draft has been preserved.", "improvement_evidence_capacity")
    used = {item["id"] for item in items}
    available = [f"E{index}" for index in range(1, 101) if f"E{index}" not in used][:min(reserve, capacity)]
    return report, items, available, {"uncited_items_removed": dropped, "citation_consolidations": consolidated}


def _patch_result(value: dict, base: str, old_evidence: list[dict], available: list[str], source: dict,
                  answers: str, allowed: list[str], sources: list[dict], year: int) -> tuple[str, list[dict], list[str], list[dict]]:
    raw_facts, patches = value.get("new_evidence"), value.get("patches")
    if not isinstance(raw_facts, list) or len(raw_facts) > len(available):
        raise ValueError("new_evidence must use at most the provided available evidence slots.")
    if not isinstance(patches, list) or len(patches) > 8:
        raise ValueError("patches must be a bounded list of question-relevant edits.")
    facts, seen = [], set()
    answer_source = {**source, "text": answers}
    for raw in raw_facts:
        if not isinstance(raw, dict) or raw.get("id") not in available or raw["id"] in seen:
            raise ValueError("New evidence IDs must be unique provided available IDs.")
        checked = workflow._validate_fact(raw, answer_source)
        if checked is None or workflow._find_quote(source["text"], raw.get("quote", "")) is None:
            raise ValueError("Each new evidence quote must occur literally in both the actual employee answers and their pinned document, not in generated questions.")
        if checked["category"] not in {"learning", "goal", "work_detail", "context"}:
            raise ValueError("New answer facts must describe personal context, learning, work or goals, not independent peer feedback.")
        checked.update(id=raw["id"], evidence_type="employee_self_report", verification_status="employee_provided_not_independently_verified")
        checked["claim"] = re.sub(r"\s+", " ", checked["quote"]).strip()
        checked["status"] = "planned" if checked["category"] == "goal" else "uncertain"
        facts.append(checked)
        seen.add(raw["id"])
    evidence = deepcopy(old_evidence) + facts
    known = {item["id"] for item in evidence}
    new_ids = {item["id"] for item in facts}
    referenced = set()
    for patch in patches:
        if isinstance(patch, dict) and isinstance(patch.get("content"), str):
            referenced.update(workflow.CITATION_PATTERN.findall(workflow._canonicalize_report_headings(patch["content"], None)))
    # A provider can extract a valid personal answer but omit its patch. Apply
    # only these already literal-verified reflections/goals, never a generated
    # inference or a missing work-detail/context claim. The normal patch guards
    # below also validate every synthesized addition.
    patches = list(patches)
    for item in facts:
        if item["id"] in referenced:
            continue
        section = {"learning": "Annual Review Summary", "goal": "Next Year Goals"}.get(item["category"])
        if section not in allowed or (item["category"] == "goal" and not _prospective_personal_intent(item["quote"])):
            continue
        patches.append({"section": section, "operation": "append", "anchor": "", "content": item["quote"] + " [" + item["id"] + "]"})
        item["application_method"] = "literal_answer_completion"
    used_new_ids = set()
    changed, report, section_categories = [], base, {}
    for patch in patches:
        if not isinstance(patch, dict) or patch.get("section") not in allowed or patch.get("operation") not in {"append", "replace_span"}:
            raise ValueError("Only append or replace_span operations in allowed question-relevant sections are supported.")
        content = patch.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > 7000 or re.search(r"^#{1,2}\s", content, re.M):
            raise ValueError("Patch content must be bounded prose without H1/H2 headings.")
        content = workflow._canonicalize_report_headings(content.strip(), None)
        ids = set(workflow.CITATION_PATTERN.findall(content))
        if ids - known or not ids.intersection(new_ids):
            details = {"section": patch["section"], "patch_reference_ids": sorted(ids)[:10], "new_answer_ids": sorted(new_ids), "available_ids": available}
            raise ValueError("Each patch needs known evidence and at least one literal new answer reference. Leave unanswered sections unchanged. Reference metadata: " + json.dumps(details, separators=(",", ":")))
        referenced_new = [item for item in facts if item["id"] in ids]
        if patch["section"] == "Next Year Goals":
            if not any(item["category"] == "goal" and _prospective_personal_intent(item["quote"]) for item in referenced_new):
                raise ValueError("A goals patch needs literal new goal evidence with the employee's actual prospective intent; a reflection cannot be reused as an invented future goal.")
        if referenced_new and all(item["category"] in {"learning", "goal"} for item in referenced_new):
            # Preserve the employee's actual reflection/intent rather than
            # accepting plausible but unsupported outcome embellishment.
            literal = " ".join(re.sub(r"\s+", " ", item["quote"]).strip() for item in referenced_new)
            content = literal + " " + " ".join("[" + item["id"] + "]" for item in referenced_new)
            if patch["operation"] == "append" and patch["section"] == "Annual Review Summary":
                content = "### Personal reflection\n\n" + content
            ids = set(workflow.CITATION_PATTERN.findall(content))
        used_new_ids.update(ids.intersection(new_ids))
        if workflow._percent_citation_check(content, evidence):
            raise ValueError("Every percentage in new prose must occur in its cited evidence quote.")
        guarded, quote_checks = workflow._guard_direct_quotes(content, evidence, sources)
        if quote_checks["removed_unsupported_quote_paragraphs"] or guarded != content:
            raise ValueError("Patch prose contains an unsupported direct quotation.")
        reflection_missing = workflow._missing_personal_reflections(sources, str(year))
        checked_content, _ = workflow._apply_report_guards(content, evidence, reflection_missing)
        if checked_content != content:
            raise ValueError("New prose must not invent personal reflection or omit the team qualification for a measured outcome.")
        if patch["section"] == "Leadership Principles Summary":
            # Validate just the addition. Existing employee prose must remain
            # untouched even when it would need a separate human correction.
            _, leadership_checks = workflow._guard_leadership_section("## Leadership Principles Summary\n\n" + content, evidence)
            if leadership_checks["removed_principles"]:
                raise ValueError("New leadership prose lacks the documented behavior for: " + "; ".join(leadership_checks["removed_principles"]) + ". Use a supported interpretation without rewriting existing employee prose.")
        if re.search(r"\d+(?:\.\d+)?\s*(?:%|(?:minutes?|hours?|seconds?|customers?|users?|agents?)\b)", content, re.I):
            if not re.search(r"self.report|I (?:report|estimate|propose|would)|propos|target|aim|not independently", content, re.I):
                raise ValueError("A new quantitative answer needs a self-report qualification or must clearly be a proposed target.")
        if re.search(r"\b(?:agreed|approved|confirmed|finalized)\b", content, re.I) and not workflow._positive_individual_goals({"text": answers}, str(year + 1)):
            for sentence in re.split(r"(?<=[.!?])\s+", content):
                if re.search(r"\b(?:agreed|approved|confirmed|finalized)\b", sentence, re.I) and not re.search(r"\b(?:not|no|never|haven't|unagreed|pending|proposed)\b", sentence, re.I):
                    raise ValueError("Do not assert agreed individual goals unless the employee explicitly reports that agreement.")
        heading = patch["section"]
        start, end = _sections(report)[heading]
        current = report[start:end]
        if patch["operation"] == "append":
            if patch.get("anchor") not in {None, ""}:
                raise ValueError("Append patches must have an empty anchor.")
            replacement = current.rstrip() + "\n\n" + content + "\n\n"
        else:
            anchor = patch.get("anchor")
            if not isinstance(anchor, str) or not anchor or len(anchor) > 600 or current.count(anchor) != 1 or re.search(r"^#", anchor, re.M):
                raise ValueError("replace_span needs one exact bounded information-gap sentence in its section.")
            plain_anchor = workflow.CITATION_PATTERN.sub("", anchor).strip()
            if re.search(r"\n\s*\n", plain_anchor) or len(re.split(r"(?<=[.!?])\s+(?=\S)", plain_anchor)) != 1:
                raise ValueError("replace_span may replace exactly one gap sentence, never a multi-sentence paragraph.")
            if not _replaceable_gap(anchor):
                raise ValueError("Only a complete information-gap or unagreed-goal statement may be replaced. Append the answer when a sentence also contains employee accomplishments or other context.")
            replacement = current.replace(anchor, content, 1)
        report = report[:start] + replacement + report[end:]
        changed.append(heading)
        section_categories.setdefault(heading, set()).update(item["category"] for item in referenced_new)
    if used_new_ids != new_ids:
        raise ValueError("Every new evidence item must support an actual question-relevant patch.")
    # Remove only these exact generated neutral-gap paragraphs in the section
    # receiving matching literal context. A still-unagreed goal remains so.
    neutral_gaps = {
        "Annual Review Summary": ("learning", "Source-backed details are needed for a personal reflection."),
        "Next Year Goals": ("goal", "Source-backed details are needed for individual next-year goals."),
    }
    for heading, (category, sentence) in neutral_gaps.items():
        if category not in section_categories.get(heading, set()):
            continue
        start, end = _sections(report)[heading]
        body = report[start:end]
        body = re.sub(r"(?:\A[ \t\r\n]*|(?<=\n\n))" + re.escape(sentence) + r"(?=\n\n|\Z)", "", body, count=1)
        report = report[:start] + body + report[end:]
    sections = [item["heading"] for item in REPORT_TEMPLATE]
    workflow._report_schema(evidence, sections)({"report_markdown": report})
    if any(patch["section"] in {"Annual Review Summary", "Leadership Principles Summary"} and re.search(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", patch["content"], re.M) for patch in patches):
        raise ValueError("Project and leadership additions must use complete prose, not bullets.")
    return report, evidence, workflow._unique(changed), facts


def improve_review(box: Any, settings: Any, run: dict, answers: str, target_score: float = 90,
                   update: Callable[..., None] = lambda **values: None) -> dict:
    """Return a complete candidate; failures never mutate the supplied run."""
    if not isinstance(answers, str) or not answers.strip() or len(answers) > 16000:
        raise workflow.WorkflowError("Add a concrete answer before improving this draft.", "improvement_answers")
    if isinstance(target_score, bool) or not isinstance(target_score, (int, float)) or not math.isfinite(target_score) or not 1 <= target_score <= 100:
        raise workflow.WorkflowError("The advisory target score must be between 1 and 100.", "improvement_target")
    original = deepcopy(run)
    context = original.get("improvement_context") or {}
    new_source = deepcopy(context.get("new_source") or {})
    if not all(new_source.get(key) for key in ("id", "name", "url", "text")) or not (new_source.get("file_version") or {}).get("id"):
        raise workflow.WorkflowError("The uploaded answer document needs a pinned source version before improvement.", "improvement_source")
    new_source.update(document_category="Employee Answers", status="analyzed", total_characters=len(new_source["text"]), analyzed_characters=len(new_source["text"]), text_truncated=False)
    sources = []
    update(stage="improve_read", progress=8, message="Rechecking the pinned sources and the employee's answer document.")
    for saved in original.get("sources", []):
        if str(saved.get("id")) == str(new_source["id"]):
            continue
        source = deepcopy(saved)
        if not (source.get("file_version") or {}).get("id"):
            raise workflow.WorkflowError("An existing source has no pinned version. The current draft has been preserved.", "improvement_source")
        source["text"] = box.read_text(source)
        sources.append(source)
    # Read the uploaded answer version as well. The supplied text only provides
    # an independent consistency check against the actual persisted document.
    persisted_answer = box.read_text(new_source)
    if re.sub(r"\s+", " ", persisted_answer).strip() != re.sub(r"\s+", " ", new_source["text"]).strip():
        raise workflow.WorkflowError("The uploaded answers changed before improvement. The current draft has been preserved.", "improvement_source")
    sources.append(new_source)
    new_budget = min(workflow.MAX_DOCUMENT_CHARACTERS, len(new_source["text"]))
    old_budget = min(workflow.MAX_DOCUMENT_CHARACTERS, (workflow.MAX_SOURCE_CHARACTERS - new_budget) // max(1, len(sources) - 1))
    model_sources = [{"id": source["id"], "name": source["name"], "text": source["text"][:new_budget if str(source["id"]) == str(new_source["id"]) else old_budget]} for source in sources]
    model_context_truncated = any(len(model["text"]) < len(source["text"]) for model, source in zip(model_sources, sources))
    by_source = {str(source["id"]): source for source in sources}
    for item in original.get("evidence", []):
        source = by_source.get(str(item.get("source_id")))
        if source is None or workflow._find_quote(source["text"], item.get("quote", "")) is None:
            raise workflow.WorkflowError("An existing evidence quote could not be rechecked against its pinned source. The current draft has been preserved.", "improvement_source")
    questions = context.get("answered_questions") or original.get("missing_information", [])
    reserve = min(4, max(2, len(questions)))
    base, retained, available, planning = _evidence_plan(original["report_markdown"], original.get("evidence", []), sources, reserve)
    allowed = _allowed_sections([item for item in questions if isinstance(item, str)], answers)
    engine = workflow.BedrockEngine(settings)
    rubric = resolve_rubric()
    names = [item["name"] for item in LEADERSHIP_PRINCIPLES]
    trusted = "\nTrusted application writing guidance:\n" + json.dumps(guideline_context())
    payload = {"employee_name": original.get("employee_name"), "year": original.get("year"), "current_report": base,
               "existing_evidence": retained, "available_new_evidence_ids": available, "new_evidence_limit": len(available), "questions_being_answered": questions,
               "employee_answers": answers, "answer_source_kind": "Self-reported employee answers, checked against their pinned Box document.", "allowed_sections": allowed,
               "advisory_target_score": target_score, "target_note": "A drafting goal only. Never manufacture achievements or agreement to reach it."}

    def validate_patch(value):
        _patch_result(value, base, retained, available, new_source, answers, allowed, sources, int(original["year"]))

    update(stage="improve_patch", progress=28, message="Adding only the source-backed context addressed by your answers.")
    override = "\nImprovement-specific override: shared writing guidance supplies style only. Add new future goals, outcomes or commitments only when the actual employee answers supply them. Do not generate a proposal from a lesson, infer an outcome from a reflection, or fill unanswered questions. These patch-specific restrictions take precedence over general initial-report guidance."
    patch_value = engine.json_call(PATCH_INSTRUCTION + trusted + override, payload, 4500, validate_patch)
    report, evidence, changed, new_facts = _patch_result(patch_value, base, retained, available, new_source, answers, allowed, sources, int(original["year"]))
    # A no-op must not create citation-only churn or remove uncited material.
    if not changed:
        report, evidence, planning = original["report_markdown"], deepcopy(original.get("evidence", [])), {"uncited_items_removed": [], "citation_consolidations": []}
        new_facts = []
    new_source["retained_evidence_count"] = len(new_facts)
    year = int(original["year"])
    reflection_missing = workflow._missing_personal_reflections(sources, str(year))
    supplied_personal_goals = any(item.get("category") == "goal" and item.get("attribution") == "employee" and item.get("evidence_type") == "employee_self_report" and re.search(r"\b(?:I|my|individual|personal)\b", item.get("quote", "")) for item in evidence)
    goals_missing = workflow._missing_individual_goals(sources, str(year + 1)) and not supplied_personal_goals
    task = deepcopy(original.get("task") or workflow._task_context(original))
    task.update(personal_reflection_missing_in_sources=reflection_missing, individual_goals_missing_in_sources=goals_missing,
                employee_answers_are_self_reported=True, individual_goals_agreed_in_answers=workflow._positive_individual_goals({"text": answers}, str(year + 1)))
    guards = {"citations": workflow._citation_check(report, evidence), "question_scoped_patches": changed, "evidence_plan": planning,
              "new_self_reported_evidence_ids": [item["id"] for item in new_facts], "existing_unrelated_prose_preserved": True,
              "literal_answer_completions": [item["id"] for item in new_facts if item.get("application_method") == "literal_answer_completion"],
              "literal_employee_reflection_and_goal_rendering": True,
              "actual_word_count": len(workflow.CITATION_PATTERN.sub("", report).split()), "advisory_word_goal": [800, 1050],
              "source_context": {"model_characters": sum(len(source["text"]) for source in model_sources), "limit": workflow.MAX_SOURCE_CHARACTERS, "truncated": model_context_truncated, "literal_quotes_checked_against_full_pinned_text": True}}
    # Existing human prose is audited, never automatically removed. New patch
    # quotations were already rejected if unsupported before application.
    _, full_quote_check = workflow._guard_direct_quotes(report, evidence, sources)
    quotation_issues = []
    if full_quote_check["removed_unsupported_quote_paragraphs"]:
        quotation_issues = [{"severity": "high", "message": "An existing direct quotation does not occur in the pinned source documents. Its wording was preserved for your review.", "suggestion": "Check the quotation against the original material and correct or remove it before approving the draft.", "evidence_ids": workflow._unique([eid for issue in full_quote_check["issues"] for eid in issue.get("evidence_ids", [])]), "verification_status": "unsupported_existing_quotation_preserved_for_employee_review"}]
    guards["complete_body_quote_audit"] = {"unsupported_paragraph_count": full_quote_check["removed_unsupported_quote_paragraphs"], "unsupported_quotes": full_quote_check["unsupported_quotes"], "existing_prose_preserved": True, "issues": quotation_issues}
    update(stage="final_evaluation", progress=76, message="Independently evaluating the exact updated draft; the target score is advisory.")
    evaluation_payload = {"phase": "final", "task": task, "draft": report, "evidence": evidence,
                          "original_sources": model_sources,
                          "rubric": rubric, "deterministic_report_guards": guards,
                          "self_report_note": "Employee answers supply personal context, not independently measured project outcomes. Score this exact draft without forcing an increase or rewarding more principle labels."}
    value = engine.json_call(EVALUATION_INSTRUCTION + trusted, evaluation_payload, 6000, evaluation_schema(evidence, rubric, names))
    final = build_evaluation(value, report, evidence, rubric, names)
    for issue in quotation_issues:
        if issue["message"] not in {item["message"] for item in final["issues"]}:
            final["issues"].append(deepcopy(issue))
        if issue["suggestion"] not in final["improvements"]:
            final["improvements"].insert(0, issue["suggestion"])
    final["missing_information"] = workflow._final_questions(final["missing_information"], evidence, reflection_missing, goals_missing, str(year + 1))
    result = deepcopy(original)
    result.pop("improvement_context", None)
    result.update(report_markdown=report, evidence=evidence, sources=[{key: val for key, val in source.items() if key != "text"} for source in sources],
                  missing_information=final["missing_information"], task=task)
    evaluations = deepcopy(original.get("evaluations") or {"rubric_version": rubric["version"], "score_label": "Draft quality"})
    evaluations["final"] = final
    if evaluations.get("initial"):
        evaluations["overall_delta"] = round(final["overall_score"] - evaluations["initial"]["overall_score"], 2)
    result["evaluations"] = evaluations
    timestamp = _now()
    history = result.setdefault("improvement_history", [])
    history.append({"at": timestamp, "report_markdown": original["report_markdown"], "evaluation": deepcopy((original.get("evaluations") or {}).get("final")),
                    "report_hash": report_hash(original["report_markdown"]), "evidence": deepcopy(original.get("evidence", [])), "had_user_edits": bool(original.get("user_edited")), "changed_sections": changed})
    result["improvement"] = {"status": "completed", "round": len(history), "target_score": target_score, "target_reached": final["overall_score"] >= target_score,
                             "changed_sections": changed, "note": "The target is an advisory draft-quality goal. Scores can rise or fall; no achievement or additional question was invented to reach it."}
    review = deepcopy(original.get("review") or {})
    review.setdefault("checks", {})["latest_improvement"] = {"at": timestamp, **guards, "actual_model_usage": deepcopy(engine.usage)}
    review["unresolved_issues"] = [{**item, "verification_status": "needs_human_confirmation_after_final_evaluation"} for item in final["issues"]]
    review["human_review_required"] = True
    review["note"] = "Employee answers were saved as a self-reported source. Only question-relevant patches were applied, and a separate evaluation scored the exact current body. Prior prose and evaluations remain in private history."
    result["review"] = review
    coverage = deepcopy(original.get("coverage") or {})
    coverage.update(evidence_count=len(evidence), candidate_evidence_count=coverage.get("candidate_evidence_count", len(original.get("evidence", []))) + len(new_facts),
                    read_files=len(sources), analyzed_files=len(sources), selected_files=len(sources),
                    discovered_files=max(coverage.get("discovered_files", 0), len(sources)), improvement_source_context=guards["source_context"])
    warnings = list(coverage.get("warnings", []))
    if not new_facts:
        warnings.append("The answer document was read, but no useful new source-verified context was retained. The previous report was preserved.")
    if model_context_truncated:
        warnings.append("The improvement evaluator received bounded excerpts of the source documents. Evidence quotations were rechecked against the full pinned text; excerpt coverage is not full-document semantic verification.")
    if quotation_issues:
        warnings.append("An existing direct quotation could not be found in the pinned source text. Employee wording was preserved; correction and review remain required.")
    coverage["warnings"] = workflow._unique(warnings)
    result["coverage"] = coverage
    usage = deepcopy(original.get("usage") or {"model_id": engine.model_id})
    for key in ("calls", "input_tokens", "output_tokens", "latency_ms"):
        usage[key] = usage.get(key, 0) + engine.usage.get(key, 0)
    result["usage"] = usage
    result["updated_at"] = timestamp
    if report != original["report_markdown"]:
        result.update(reviewer_confirmed=False, confirmed_at=None)
    update(stage="improve_ready", progress=95, message="Updated draft evaluated. Preparing the same draft's saved files.")
    return result


improve_workflow = improve_review
