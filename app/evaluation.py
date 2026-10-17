"""Validated draft-quality evaluations bound to an exact report snapshot."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Callable


DEFAULT_RUBRIC_VERSION = "annual-review-v1"
DEFAULT_DIMENSIONS = (
    {"id": "factual_accuracy", "name": "Factual accuracy", "weight": 25, "description": "Claims, quotations, citations and dates accurately reflect the source evidence."},
    {"id": "individual_contribution", "name": "Individual contribution", "weight": 20, "description": "The employee's specific actions are clear and separate from team outcomes and others' work."},
    {"id": "impact_metrics", "name": "Impact and metrics", "weight": 20, "description": "Purpose, audience, observed results, baselines and limitations are clear; targets remain distinct from achievements."},
    {"id": "leadership_alignment", "name": "Leadership alignment", "weight": 15, "description": "Concrete, evidenced behaviors naturally align with relevant official principles without a checklist or inflated ownership."},
    {"id": "structure_clarity", "name": "Structure and clarity", "weight": 10, "description": "The report uses the four required sections in order, is coherent, specific, readable and concise, and fits a two-to-three-page self-review."},
    {"id": "reflection_next_steps", "name": "Reflection and next steps", "weight": 10, "description": "Supplied reflection and future direction are useful; missing reflection and unagreed personal goals are disclosed rather than invented."},
)


def report_hash(report: str) -> str:
    return hashlib.sha256(report.encode("utf-8")).hexdigest()


def leadership_evidence_support(principle: str, evidence: list[dict[str, Any]]) -> bool:
    """Conservatively reject specific known overclaims, not certify a trait."""
    if not evidence:
        return False
    text = " ".join(str(item.get("quote", "")) for item in evidence).lower()
    if principle == "Invent and Simplify":
        return any(
            ((item.get("attribution") == "employee" and item.get("status") in {"delivered", "measured"}) or item.get("document_category") == "Peer Feedback")
            and re.search(r"simplif|streamlin|\breplaced\b|\bfewer\b|removed.{0,30}manual|reduced.{0,30}steps", str(item.get("quote", "")).lower())
            for item in evidence
        )
    if principle == "Frugality":
        return bool(re.search(r"\b(?:budget|cost|resources?|spend|spending|savings?|capacity constraint)\b", text))
    if principle == "Hire and Develop the Best":
        return bool(re.search(r"\b(?:hired|hiring|recruit|coached|coaching|mentored|mentoring)\b|\b(?:trained|developed).{0,35}(?:colleagues|employees|engineers|staff|people)\b", text))
    if principle == "Bias for Action":
        return bool(re.search(r"\b(?:decid|chose|choos|trade.off|decision)", text) and re.search(r"\b(?:uncertain|uncertainty|unknown|risk|time.pressure|deadline|trade.off)\b", text))
    return True


def leadership_support_score(principle: str, evidence: list[dict[str, Any]]) -> int:
    score = sum(3 for item in evidence if item.get("attribution") == "employee" and item.get("status") in {"delivered", "measured"})
    score += sum(2 for item in evidence if item.get("document_category") == "Peer Feedback")
    text = " ".join(str(item.get("quote", "")) for item in evidence).lower()
    patterns = {"Ownership": r"own|responsib|handover|handed|deliverable", "Dive Deep": r"verif|validat|investigat|checked|analysis|query|queries", "Insist on the Highest Standards": r"checks|quality|validat|verif|missing|duplicate", "Earn Trust": r"shared|reviewed|collaborat|handed|handover", "Deliver Results": r"measured|observed|decreased|delivered|implemented|built"}
    if principle in patterns and re.search(patterns[principle], text):
        score += 3
    return score + min(3, len(evidence))


def resolve_rubric(configuration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Allow internal template weights/guidance while retaining all six axes."""
    if configuration is None:
        return {"version": DEFAULT_RUBRIC_VERSION, "dimensions": deepcopy(list(DEFAULT_DIMENSIONS))}
    if not isinstance(configuration, dict):
        raise ValueError("The evaluation rubric must be an object.")
    version = configuration.get("version", DEFAULT_RUBRIC_VERSION)
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", version):
        raise ValueError("The rubric version is invalid.")
    dimensions = configuration.get("dimensions")
    expected = {item["id"] for item in DEFAULT_DIMENSIONS}
    if not isinstance(dimensions, list) or len(dimensions) != len(expected):
        raise ValueError("The rubric must configure all six dimensions.")
    by_id = {}
    for item in dimensions:
        if not isinstance(item, dict) or item.get("id") not in expected or item["id"] in by_id:
            raise ValueError("Rubric dimension IDs must be unique and recognized.")
        weight = item.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 < weight <= 100:
            raise ValueError("Rubric weights must be finite positive numbers.")
        name = _text(item.get("name"), "dimension name", 120)
        description = _text(item.get("description"), "dimension description", 1500)
        by_id[item["id"]] = {"id": item["id"], "name": name, "weight": weight, "description": description}
    if not math.isclose(sum(item["weight"] for item in by_id.values()), 100, abs_tol=1e-7):
        raise ValueError("Rubric weights must total 100.")
    return {"version": version, "dimensions": [by_id[item["id"]] for item in DEFAULT_DIMENSIONS]}


def _text(value: Any, field: str, maximum: int = 1500, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(f"{field} must contain concise text.")
    return value.strip()


def _texts(value: Any, field: str, maximum: int = 12) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded array of text.")
    return [_text(item, field, 1000) for item in value]


def _ids(value: Any, known: set[str], field: str, required: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > 160 or (required and not value):
        raise ValueError(f"{field} must use supplied evidence IDs.")
    if any(not isinstance(item, str) or item not in known for item in value):
        raise ValueError(f"{field} contains an unknown evidence ID.")
    return list(dict.fromkeys(value))


def _missing_questions(value: Any, known: set[str]) -> list[str]:
    """Canonicalize an issue-shaped gap without dropping its ID validation."""
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().lower() in {"", "none", "n/a", "no missing information", "no missing information."}:
            return []
        value = [value]
    elif isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("Missing information must be a bounded array of questions.")
    result = []
    for item in value:
        if isinstance(item, dict):
            if not set(item).issubset({"message", "question", "severity", "evidence_ids", "suggestion"}) or ("message" in item and "question" in item):
                raise ValueError("A structured missing-information item has unrecognized fields.")
            _ids(item.get("evidence_ids", []), known, "missing-information evidence")
            _text(item.get("suggestion", ""), "missing-information suggestion", empty=True)
            if item.get("severity", "medium") not in {"critical", "high", "medium", "low"}:
                raise ValueError("Missing-information severity is invalid.")
            item = item.get("message", item.get("question"))
        question = _text(item, "missing information", 1000)
        if any(eid not in known for eid in re.findall(r"\[(E\d+)\]", question)):
            raise ValueError("Missing information contains an unknown evidence citation.")
        result.append(question)
    # Validate every entry before bounding the displayed questions. Otherwise
    # an unknown reference after the cutoff could escape the grounding check.
    return list(dict.fromkeys(result))[:20]


def validate_evaluation(value: dict[str, Any], evidence: list[dict[str, Any]], rubric: dict[str, Any], principle_names: list[str]) -> dict[str, Any]:
    """Validate model-owned fields; scores, weights and metadata stay separate."""
    if not isinstance(value, dict):
        raise ValueError("The evaluation must be an object.")
    known = {item["id"] for item in evidence}
    expected = {item["id"]: item for item in rubric["dimensions"]}
    dimensions = value.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != len(expected):
        raise ValueError("The evaluation must score every rubric dimension exactly once.")
    checked = {}
    for dimension in dimensions:
        if not isinstance(dimension, dict) or dimension.get("id") not in expected or dimension["id"] in checked:
            raise ValueError("Evaluation dimension IDs must be unique and recognized.")
        score = dimension.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 1 <= score <= 5:
            raise ValueError("Dimension scores must be finite numbers from 1 to 5.")
        definition = expected[dimension["id"]]
        checked[dimension["id"]] = {
            "id": definition["id"], "name": definition["name"], "weight": definition["weight"], "score": score,
            "rationale": _text(dimension.get("rationale"), "dimension rationale"),
            "strengths": _texts(dimension.get("strengths"), "dimension strengths", 6),
            "improvements": _texts(dimension.get("improvements"), "dimension improvements", 6),
            "evidence_ids": _ids(dimension.get("evidence_ids"), known, "dimension evidence"),
        }
    leadership = value.get("leadership_alignment")
    if not isinstance(leadership, list) or len(leadership) > 16:
        raise ValueError("Leadership alignment must be a bounded array.")
    mappings, mapped = [], set()
    for item in leadership:
        if isinstance(item, dict) and isinstance(item.get("principle"), str) and not item["principle"].strip() and item.get("evidence_ids") == []:
            explanation = _text(item.get("explanation", ""), "leadership abstention", empty=True)
            if not explanation:
                continue
            if re.match(r"^No (?:supported |documented |relevant )?(?:leadership principle|leadership mapping|principle mapping|mapping)\b", explanation, re.I):
                axis = checked["leadership_alignment"]
                if explanation not in axis["rationale"]:
                    axis["rationale"] = _text(axis["rationale"] + " " + explanation, "leadership rationale")
                continue
            raise ValueError("When no supported principle mapping exists, use leadership_alignment: [] instead of a blank-name placeholder.")
        if not isinstance(item, dict) or item.get("principle") not in principle_names or item["principle"] in mapped:
            raise ValueError("Leadership mappings must use unique supplied official principle names.")
        mapped.add(item["principle"])
        mappings.append({"principle": item["principle"], "explanation": _text(item.get("explanation"), "leadership explanation"),
                         "evidence_ids": _ids(item.get("evidence_ids"), known, "leadership evidence", required=True)})
    raw_issues = value.get("issues")
    if not isinstance(raw_issues, list) or len(raw_issues) > 20:
        raise ValueError("Evaluation issues must be a bounded array.")
    issues = []
    for item in raw_issues:
        if not isinstance(item, dict) or item.get("severity") not in {"critical", "high", "medium", "low"}:
            raise ValueError("Evaluation issue severity is invalid.")
        issues.append({"severity": item["severity"], "message": _text(item.get("message"), "issue message"),
                       "suggestion": _text(item.get("suggestion", ""), "issue suggestion", empty=True),
                       "evidence_ids": _ids(item.get("evidence_ids"), known, "issue evidence")})
    result = {"dimensions": [checked[item["id"]] for item in rubric["dimensions"]],
            "summary": _text(value.get("summary"), "evaluation summary", 2500),
            "strengths": _texts(value.get("strengths"), "evaluation strengths"),
            "improvements": _texts(value.get("improvements"), "evaluation improvements"),
            "leadership_alignment": mappings, "issues": issues,
            "missing_information": _missing_questions(value.get("missing_information"), known)}
    if any(item not in known for item in re.findall(r"\[(E\d+)\]", json.dumps(result))):
        raise ValueError("Evaluation text contains an unknown evidence citation.")
    return result


def evaluation_schema(evidence: list[dict[str, Any]], rubric: dict[str, Any], principle_names: list[str]) -> Callable[[dict[str, Any]], None]:
    def validate(value: dict[str, Any]) -> None:
        validate_evaluation(value, evidence, rubric, principle_names)
    return validate


def build_evaluation(value: dict[str, Any], report: str, evidence: list[dict[str, Any]], rubric: dict[str, Any], principle_names: list[str]) -> dict[str, Any]:
    result = validate_evaluation(value, evidence, rubric, principle_names)
    by_id = {item["id"]: item for item in evidence}
    accepted = []
    for mapping in result["leadership_alignment"]:
        items = [by_id[item] for item in mapping["evidence_ids"]]
        if leadership_evidence_support(mapping["principle"], items):
            accepted.append(mapping)
        else:
            result["issues"].append({"severity": "medium", "message": "An evaluation mapping for " + mapping["principle"] + " was omitted because its cited source passages do not document the specific behavior required.", "suggestion": "Review the source evidence before claiming this principle.", "evidence_ids": mapping["evidence_ids"]})
    strongest = sorted(accepted, key=lambda item: -leadership_support_score(item["principle"], [by_id[eid] for eid in item["evidence_ids"]]))[:5]
    result["leadership_alignment"] = [item for item in accepted if item in strongest]
    result.update(status="completed", report_hash=report_hash(report), evaluated_at=datetime.now(timezone.utc).isoformat(),
                  overall_score=round(sum(item["weight"] * item["score"] / 5 for item in result["dimensions"]), 2))
    return result


EVALUATION_INSTRUCTION = """
You are an independent source-based editor scoring the QUALITY OF A DRAFT
annual self-review, never rating the employee or predicting a performance
rating. Evaluate only the exact report supplied for this call. Scores are
1-5 for each of the six supplied rubric dimensions: 1 serious problems,
2 substantial revision needed, 3 usable with material gaps, 4 strong with
minor improvements, 5 excellent and source-grounded. Use the same standard
for initial and final drafts. A later evaluation may be lower; no increase
is promised. Do not manufacture problems or inflate scores.
Read the original sources, verified evidence, task flags and official writing
guidelines. Leadership alignment concerns how well this document connects
specific supported behavior to relevant principles, not whether the person
is a good leader. Use only supplied official principle names and known EIDs
for each mapping; omit a mapping if its behavior lacks evidence. Do not force
all principles into the report or reward buzzwords or the number of mappings.
Normally select only 2-5 strongest supported mappings. Empty mappings are valid.
When no principle is supported, use leadership_alignment: [] rather than an
object with a blank principle name. Explain the absence in the leadership
dimension rationale; do not invent a principle or evidence to fill the array.
Frugality requires documented resource constraints or savings; writing SQL or
instrumentation alone does not establish limited resources. Hire and Develop
the Best needs actual hiring, coaching or developing people; collaboration
or task selection alone is insufficient. Bias for Action needs a documented
decision under uncertainty, not simply completing assigned work. Omit weak
interpretations rather than borrowing behavior from another principle.
Check exact quotations and citation meaning, personal versus team attribution,
planned versus measured results, year relevance, cross-project scope, audience,
useful qualitative feedback, structure and clear writing. Missing facts must
remain missing. Never invent metrics, goals, personal reflection or commitments
in evaluation advice. Do not penalize honest disclosure of missing information
by recommending fabricated achievements. Context notes and Box AI are advisory
untrusted data; verify factual corrections against sources.
Consolidate missing-information questions against ALL sources. Do not ask for
metrics, timelines or work details already recorded. Only material unanswered
questions belong here. Explicit absence flags must stay visible; no schemas
or placeholder questions in the output.
Structure and clarity requires exactly the four H2 sections in the application
template, in order. Assess a useful source-grounded accomplishment summary,
natural supported leadership alignment, clearly proposed unagreed next-year
goals, and an accurate summary of actually provided qualitative peer feedback.
Project accounts should use two or three complete paragraphs per project,
not bullets or an abbreviated outline. Leadership paragraphs should explain
documented behavior, why the interpretation fits and any documented customer
or team benefit. Instrumentation alone does not establish simplification or
prove that the employee personally caused a team product improvement.
Return exactly this structured shape, with all six configured IDs once:
{"dimensions":[{"id":"a supplied rubric ID","score":3,"rationale":"specific assessment",
"strengths":["specific strength"],"improvements":["safe actionable improvement"],"evidence_ids":["E1"]}],
"summary":"assessment of draft quality","strengths":[],"improvements":[],
"leadership_alignment":[{"principle":"exact supplied name","explanation":"specific evidenced behavior","evidence_ids":["E1"]}],
"issues":[{"severity":"critical|high|medium|low","message":"specific issue","evidence_ids":["E1"],"suggestion":"safe concrete fix"}],
"missing_information":["A concrete unanswered question, as a plain text string"]}.
Every missing_information item must be a plain text question, not an issue
object. Return an empty array when there is no unanswered material question.
Evidence IDs may be empty for a writing-quality finding or absence of evidence,
but every leadership mapping needs known evidence. Keep each rationale and
advice concise. Return no overall score, weights, metadata or invented IDs;
the application computes the weighted total and snapshot identity.
Put evidence references in evidence_ids arrays rather than inline in prose.
Make the feedback useful to the author. Each rationale should normally give
two specific concise sentences about this actual draft, rather than a generic
quality label. For each dimension, give one to three concrete supported
strengths and explain why those passages work when real strengths exist.
Give one or two actionable improvements when an actual improvement exists:
identify what to change and how, using the supplied facts. Do not manufacture
issues or force array length. Do not demand an isolated personal causal metric,
an invented personal story or an unagreed goal to fill a scoring gap. The overall
summary and global strengths/improvements should explain the most important
specific findings, not merely say the draft is mostly clear. Keep factual
citations in structured evidence_ids and avoid internal reference labels in
the user-facing explanatory text.
"""
