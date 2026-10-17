"""A Box-native, bounded upload-to-draft workflow.

The scheduler calls ``process_once`` serially. The state store contains only
operational metadata; source text, model output and credentials never go there.
No public endpoint, browser workbench or Box notification is required.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Callable, Protocol, TypedDict
from uuid import uuid4

from app.box_client import MAX_FILE_BYTES, BoxError, box_id
from app.exports import make_export
from app.workflow import WorkflowError, run_workflow


CATEGORIES = ("Projects", "Peer Feedback", "Annual Plans")
MAX_FILES = 25
MAX_FOLDERS = 100
QUIET_SECONDS = 20
INPUT_EXTENSIONS = {"docx", "pdf"}


class NativeConfig(TypedDict):
    root_folder_id: str
    category_folders: dict[str, str]
    reports_folder_id: str
    employee_name: str
    year: int
    language: str


class StateStore(Protocol):
    def read(self) -> dict: ...
    def write(self, state: dict) -> None: ...


class NativeWorkflowError(RuntimeError):
    """An operational error with a fixed, safe-to-log public message."""

    def __init__(self, message: str, code: str = "native_workflow_error"):
        super().__init__(message)
        self.code = code


_STAGE_LABELS = {
    "discover": "Discovering source documents",
    "read": "Reading Word and PDF documents",
    "extract": "Extracting source-backed evidence",
    "draft": "Writing annual self-review",
    "box_review": "Checking original files with Box AI",
    "review": "Reviewing facts and attribution",
    "revise": "Revising the draft",
    "ready": "Preparing draft exports",
    "save_draft": "Saving draft Word and PDF to Reports",
}
_RETAINED_KEYS = {
    "fingerprint", "pending_fingerprint", "completed_fingerprint", "failed_fingerprint",
    "last_changed_at", "started_at", "completed_at", "failed_at", "run_id",
    "report_ids", "reports", "evidence_count", "review_issue_count",
    "missing_information_count", "revision_performed", "reviewer_confirmed",
}


def _configuration(config: dict) -> NativeConfig:
    try:
        categories = {category: box_id(config["category_folders"][category]) for category in CATEGORIES}
        root = box_id(config["root_folder_id"])
        reports = box_id(config["reports_folder_id"])
        ids = [root, reports, *categories.values()]
        employee = str(config["employee_name"]).strip()
        year = int(config["year"])
        if len(set(ids)) != len(ids) or not employee or len(employee) > 120 or not 2000 <= year <= 2100:
            raise ValueError
        if config.get("language", "en") != "en":
            raise ValueError
        return {"root_folder_id": root, "reports_folder_id": reports, "category_folders": categories,
                "employee_name": employee, "year": year, "language": "en"}
    except (KeyError, TypeError, ValueError, BoxError):
        raise NativeWorkflowError("The native Box folder configuration is invalid. Check the three input folders, Reports folder and employee details.", "configuration") from None


def _snapshot(box: Any, config: NativeConfig) -> dict:
    """List metadata, not file content, including files beyond the run limit.

    A fixed category order and numeric ID order make selection deterministic.
    Reports is excluded by ID even if it was moved under an input folder.
    """
    queue = deque((folder_id, category) for category, folder_id in config["category_folders"].items())
    category_roots = set(config["category_folders"].values())
    visited, seen_files = set(), set()
    candidates, skipped = [], []
    discovered, truncated = 0, False
    while queue and len(visited) < MAX_FOLDERS:
        current, category = queue.popleft()
        if current in visited or current == config["reports_folder_id"]:
            continue
        visited.add(current)
        folder = box.list_folder(current)
        truncated = truncated or bool(folder.get("truncated"))
        for entry in folder.get("entries", []):
            item = dict(entry)
            item_id = box_id(item.get("id", ""))
            if item.get("type") == "folder":
                if item_id == config["reports_folder_id"]:
                    skipped.append({"id": item_id, "name": str(item.get("name", "Reports")), "reason": "Generated reports are excluded from source materials.", "type": "folder"})
                elif item_id not in category_roots:
                    queue.append((item_id, category))
                continue
            if item.get("type") != "file" or item_id in seen_files:
                continue
            seen_files.add(item_id)
            discovered += 1
            extension = str(item.get("extension") or Path(str(item.get("name", ""))).suffix.lstrip(".")).lower()
            item.update(id=item_id, extension=extension, document_category=category,
                        url=f"https://app.box.com/file/{item_id}")
            if extension not in INPUT_EXTENSIONS:
                skipped.append({"id": item_id, "name": str(item.get("name", item_id)), "reason": "Only Word (.docx) and PDF input documents are supported."})
                continue
            # Fingerprint every supported document, including oversized and
            # over-limit files, so a new version cannot silently escape polling.
            candidates.append(item)
    if queue:
        truncated = True
    category_order = {category: index for index, category in enumerate(CATEGORIES)}
    candidates.sort(key=lambda item: (category_order[item["document_category"]], int(item["id"])))
    files = []
    for item in candidates:
        if int(item.get("size") or 0) > MAX_FILE_BYTES:
            reason = "File exceeds the 12 MB input limit."
        elif len(files) >= MAX_FILES:
            reason = "The 25-document limit was reached; this document is not included in the draft."
            truncated = True
        else:
            files.append(item)
            continue
        skipped.append({"id": item["id"], "name": str(item.get("name", item["id"])), "reason": reason})
    fingerprint_entries = []
    for item in candidates:
        version = item.get("file_version") or {}
        fingerprint_entries.append([item["id"], str(version.get("id") or item.get("etag") or item.get("sha1") or "unversioned"),
                                    item["document_category"], str(item.get("name", "")), int(item.get("size") or 0)])
    encoded = json.dumps(sorted(fingerprint_entries), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return {"files": files, "skipped": skipped, "discovered": discovered,
            "supported_count": len(candidates), "truncated": truncated,
            "fingerprint": hashlib.sha256(encoded).hexdigest()}


class NativeBoxAdapter:
    """Give the normal workflow one immutable snapshot of the three inputs."""

    def __init__(self, box: Any, root_folder_id: str, snapshot: dict):
        self.box, self.root_folder_id, self.snapshot = box, root_folder_id, snapshot

    def discover(self, folder_id: str, max_files: int = MAX_FILES) -> dict:
        if str(folder_id) != self.root_folder_id:
            raise NativeWorkflowError("The native workflow can only read its configured input folders.", "configuration")
        limit = max(1, min(int(max_files), MAX_FILES))
        result = {key: deepcopy(self.snapshot[key]) for key in ("files", "skipped", "discovered", "truncated")}
        overflow = result["files"][limit:]
        result["files"] = result["files"][:limit]
        result["skipped"].extend({"id": item["id"], "name": item["name"], "reason": "The document limit was reached."} for item in overflow)
        result["truncated"] = result["truncated"] or bool(overflow)
        return result

    def read_text(self, file: dict) -> str:
        return self.box.read_text(file)

    def ask(self, file_ids: list[str], prompt: str) -> dict:
        return self.box.ask(file_ids, prompt)


def _warnings(snapshot: dict) -> list[str]:
    warnings = ["Drafts require employee review; no human approval has been recorded."]
    if snapshot.get("skipped"):
        warnings.append(f"{len(snapshot['skipped'])} files or folders were excluded; review notes contain the coverage details.")
    if snapshot.get("truncated"):
        warnings.append("Discovery or document limits were reached; this draft may not cover every input document.")
    if snapshot.get("supported_count", 0) > MAX_FILES:
        warnings.append("At most 25 Word/PDF documents are analyzed per draft. Narrow the input folders for full coverage.")
    return warnings


def _safe_error(error: Exception) -> NativeWorkflowError:
    if isinstance(error, NativeWorkflowError):
        return error
    if isinstance(error, BoxError):
        return NativeWorkflowError("A Box operation failed. Check application access, source files and the Reports folder before changing the input documents to retry.", "box_operation")
    if isinstance(error, WorkflowError):
        allowed = {"no_sources", "no_readable_sources", "no_evidence", "aws_credentials", "bedrock_access", "bedrock_configuration"}
        code = error.code if error.code in allowed else "generation_failed"
        return NativeWorkflowError("Draft generation did not complete. Check source readability and AWS/Box access. This input version will not be retried automatically.", code)
    return NativeWorkflowError("The native workflow stopped unexpectedly. This input version will not be retried automatically; check the service and change an input document after resolving the problem.", "unexpected_error")


def _evaluation_notes(run: dict) -> list[str]:
    """Render only the current report's evaluation; keep earlier scores private."""
    evaluations = run.get("evaluations")
    evaluation = evaluations.get("final") if isinstance(evaluations, dict) else None
    lines = ["", "## Draft quality", ""]
    if not isinstance(evaluation, dict):
        return lines + ["No current evaluation was recorded for this run. No score has been inferred."]
    if evaluation.get("status") == "unavailable":
        return lines + ["Evaluation unavailable. Review this draft and its sources before using it. No quality score has been inferred."]
    if evaluation.get("report_hash") != hashlib.sha256(run.get("report_markdown", "").encode()).hexdigest():
        return lines + ["The report changed after evaluation. No current score is available for this version."]
    lines.append("These scores assess the written draft, not the employee's performance rating.")
    known = {item.get("id") for item in run.get("evidence", []) if isinstance(item, dict)}

    def references(item):
        return " ".join(f"[{value}]" for value in item.get("evidence_ids", []) if value in known)

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    if number(evaluation.get("overall_score")):
        lines.append(f"Current draft quality score: {evaluation['overall_score']:g}/100.")
    if evaluation.get("summary"):
        lines.append(str(evaluation["summary"]))
    for field, label in (("strengths", "Strength"), ("improvements", "Improvement")):
        lines.extend(f"- {label}: {value}" for value in evaluation.get(field, []) if isinstance(value, str))
    for dimension in evaluation.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        score = f"{dimension['score']:g}/5" if number(dimension.get("score")) else "not recorded"
        lines.extend(["", f"### {dimension.get('name', dimension.get('id', 'Dimension'))}",
                      f"Score: {score}.", f"{dimension.get('rationale', '')} {references(dimension)}"])
        for field, label in (("strengths", "Strength"), ("improvements", "Improvement")):
            lines.extend(f"- {label}: {value}" for value in dimension.get(field, []) if isinstance(value, str))
    lines.extend(["", "### Leadership principle alignment", ""])
    alignment = evaluation.get("leadership_alignment", [])
    if not alignment:
        lines.append("No evidence-backed principle mapping was recorded.")
    for item in alignment:
        if isinstance(item, dict):
            lines.append(f"- {item.get('principle', 'Principle')}: {item.get('explanation', '')} {references(item)}")
    for issue in evaluation.get("issues", []):
        if isinstance(issue, dict):
            lines.append(f"- Improvement: {issue.get('message', '')} {references(issue)}")
    return lines


def _review_document(run: dict) -> dict:
    """Keep the audit trail visible in Box without persisting it in state."""
    review = run.get("review") or {}
    coverage = run.get("coverage") or {}
    if isinstance(run.get("evaluations"), dict):
        lines = ["# Draft evaluation", "", "Review the report's facts, contribution and future commitments before confirming it."]
        lines.extend(_evaluation_notes(run))
    else:
        lines = ["# Draft review notes", "", "This report is an unconfirmed draft. The employee must review facts, personal contribution, measurements and future commitments.",
                 "", "## Automated review", "", "One revision was performed." if review.get("revision_performed") else "No revision was performed.",
                 "Review findings describe the initial draft and are not automatically certified as resolved."]
        issues = review.get("issues") or []
        if not issues:
            lines.extend(["", "No specific issue was reported by the automated reviewer. This does not prove factual correctness."])
        for issue in issues:
            if isinstance(issue, dict):
                references = " ".join(f"[{item}]" for item in issue.get("evidence_ids", []) if re.fullmatch(r"E\d+", str(item)))
                lines.append(f"- {issue.get('severity', 'review')}: {issue.get('message', '')} {references}")
        lines.extend(_evaluation_notes(run))
        box_review = review.get("box_ai") if isinstance(review.get("box_ai"), dict) else {}
        box_files = box_review.get("file_ids") if isinstance(box_review.get("file_ids"), list) else []
        box_citations = box_review.get("citations") if isinstance(box_review.get("citations"), list) else []
        lines.extend(["", "## Box AI source review", "",
                      f"Status: {box_review.get('status', 'not_run')}. Source files checked: {len(box_files)}. Returned citations: {len(box_citations)}.",
                      "Box AI findings are advisory. They must be checked against original sources and do not certify the employee or the final draft."])
        if box_review.get("answer"):
            # The export renderer accepts only text and its small Markdown subset;
            # raw HTML, embedded images and arbitrary links are never executed.
            lines.extend(["", "Box AI response (recorded as returned):", "", str(box_review["answer"])])
        else:
            lines.extend(["", str(box_review.get("message") or "Box AI source review was not available for this run. Use the source quotations and other review checks; do not assume Box AI approved the draft.")])
        if box_review.get("draft_truncated"):
            lines.extend(["", "Draft input was truncated for Box AI. It did not review the complete draft."])
        if box_review.get("note"):
            lines.extend(["", str(box_review["note"])])
    lines.extend(["", "## Employee confirmation needed", ""])
    questions = run.get("missing_information") or []
    lines.extend(f"- {question}" for question in questions)
    if not questions:
        lines.append("Confirm the accuracy of the report and the employee's contribution before treating it as final.")
    if isinstance(run.get("evaluations"), dict):
        return {**run, "report_markdown": "\n".join(lines), "reviewer_confirmed": False}
    lines.extend(["", "## Coverage", "", f"Selected documents: {coverage.get('selected_files', len(run.get('sources', [])))}. Analyzed documents: {coverage.get('analyzed_files', 0)}."])
    for warning in coverage.get("warnings", []):
        lines.append(f"- {warning}")
    for item in coverage.get("skipped", []):
        if isinstance(item, dict):
            lines.append(f"- Excluded: {item.get('name', 'Document')}. {item.get('reason', '')}")
    if not isinstance(run.get("evaluations"), dict):
        lines.extend(["", "## Source quotations", "", "Quotations were checked against extracted source text. Read the original Box documents to judge whether each claim is supported."])
        for evidence in run.get("evidence", []):
            lines.extend(["", f"### [{evidence.get('id', '')}] {evidence.get('source_name', 'Source')}",
                          f"Supports: {evidence.get('claim', '')}", f"Source excerpt: {evidence.get('quote', '')}"])
    return {**run, "report_markdown": "\n".join(lines), "reviewer_confirmed": False}


def process_once(box: Any, settings: Any, config: NativeConfig, state_store: StateStore,
                 workflow: Callable = run_workflow, clock: Callable[[], float] = time.time) -> dict:
    """Poll once and synchronously generate after a 20-second quiet period.

    Use a single scheduler worker / Lambda reserved concurrency of one. A plain
    read/write store cannot provide a distributed compare-and-swap lock. An
    interrupted ``processing`` fingerprint is left for operator intervention
    rather than risking duplicate model charges on the following poll.
    """
    config = _configuration(config)
    now = float(clock())
    try:
        previous = state_store.read() or {}
        if not isinstance(previous, dict):
            raise TypeError
    except Exception:
        raise NativeWorkflowError("The native workflow state could not be read. No generation was started.", "state_read") from None
    state = {key: deepcopy(previous[key]) for key in _RETAINED_KEYS if key in previous}
    state.update(status=previous.get("status", "waiting"), updated_at=now, reviewer_confirmed=False)
    warnings: list[str] = []

    def save() -> None:
        state["warnings"] = list(dict.fromkeys(warnings))
        state["updated_at"] = float(clock())
        try:
            state_store.write(deepcopy(state))
        except Exception:
            raise NativeWorkflowError("The native workflow state could not be saved. Stop overlapping workers and check the state store.", "state_write") from None

    def describe(label: str) -> None:
        try:
            box.request("PUT", f"/2.0/folders/{config['root_folder_id']}", json={"description": "Status: " + label})
        except Exception:
            warning = "The Box folder status could not be updated; check the Reports folder for generated drafts."
            if warning not in warnings:
                warnings.append(warning)

    try:
        snapshot = _snapshot(box, config)
        warnings.extend(_warnings(snapshot))
        fingerprint = snapshot["fingerprint"]
        state.update(source_count=snapshot["supported_count"], selected_count=len(snapshot["files"]),
                     discovered_count=snapshot["discovered"], fingerprint=fingerprint)
        if not snapshot["files"]:
            state.update(status="waiting", stage="waiting", pending_fingerprint="", last_changed_at=now)
            describe("Waiting for readable Word/PDF documents in Projects, Peer Feedback or Annual Plans.")
            save()
            return deepcopy(state)
        if fingerprint == state.get("completed_fingerprint"):
            state.update(status="completed", stage="ready")
            save()
            return {**deepcopy(state), "status": "unchanged"}
        if fingerprint == state.get("failed_fingerprint"):
            state.update(status="failed", stage="failed", error=previous.get("error") or {"code": "generation_failed", "message": "This input version failed and will not be retried automatically. Change an input document after resolving the problem."})
            save()
            return deepcopy(state)
        if previous.get("status") == "processing" and fingerprint == previous.get("fingerprint"):
            state.update(status="processing", stage="processing")
            warnings.append("This input version already has a processing run. An interrupted run requires operator attention; it is not restarted automatically.")
            save()
            return deepcopy(state)
        if fingerprint != state.get("pending_fingerprint"):
            state.update(status="settling", stage="settling", pending_fingerprint=fingerprint,
                         last_changed_at=now, failed_fingerprint="")
            describe("New input detected. Waiting for uploads to settle before generating an unconfirmed draft.")
            save()
            return deepcopy(state)
        if now - float(state.get("last_changed_at", now)) < QUIET_SECONDS:
            state.update(status="settling", stage="settling")
            save()
            return deepcopy(state)

        run_id = uuid4().hex[:16]
        state.update(status="processing", stage="discover", run_id=run_id, started_at=now,
                     report_ids={}, reports=[], evidence_count=0, review_issue_count=0,
                     missing_information_count=0, revision_performed=False)
        describe("Generating an unconfirmed annual-review draft from the three input folders.")
        save()  # Record the charge-bearing run before any model invocation.
        last_stage = ""

        def update(**fields: Any) -> None:
            nonlocal last_stage
            stage = fields.get("stage")
            if stage in _STAGE_LABELS and stage != last_stage:
                last_stage = stage
                state.update(stage=stage, progress=max(0, min(100, int(fields.get("progress", 0)))))
                describe(_STAGE_LABELS[stage] + ". Draft remains unconfirmed.")
                save()

        request = {"folder_id": config["root_folder_id"], "employee_name": config["employee_name"],
                   "year": config["year"], "language": "en", "notes": "", "max_files": MAX_FILES,
                   "category_folders": dict(config["category_folders"])}
        adapter = NativeBoxAdapter(box, config["root_folder_id"], snapshot)
        result = workflow(adapter, settings, request, update)
        if not isinstance(result, dict) or not isinstance(result.get("report_markdown"), str) or not result["report_markdown"].strip():
            raise NativeWorkflowError("The generation did not return a report. This input version will not be retried automatically.", "empty_report")
        # Models and file extraction may take several minutes. Recheck the
        # configured inputs before publishing any output from their snapshot.
        # Keep state.fingerprint on the original input version: the updated
        # fingerprint must be free to settle and run on the next polls.
        if _snapshot(box, config)["fingerprint"] != fingerprint:
            raise NativeWorkflowError(
                "Source documents changed during generation. No draft was published. The updated documents will be checked on the next scheduled poll.",
                "source_changed",
            )
        categories = {item["id"]: item["document_category"] for item in snapshot["files"]}
        run = {**result, **request, "id": run_id, "reviewer_confirmed": False}
        run["sources"] = [{**source, "document_category": categories.get(str(source.get("id")), "Unspecified")} for source in result.get("sources", [])]
        run["evidence"] = [{**item, "document_category": categories.get(str(item.get("source_id")), "Unspecified")} for item in result.get("evidence", [])]
        review = run.get("review") or {}
        coverage = run.get("coverage") or {}
        state.update(evidence_count=len(run["evidence"]), review_issue_count=len(review.get("issues") or []),
                     missing_information_count=len(run.get("missing_information") or []), revision_performed=bool(review.get("revision_performed")))
        if coverage.get("warnings"):
            warnings.append("The generation reported coverage or review warnings. Read the review-notes document before using the draft.")
        if review.get("issues") or run.get("missing_information"):
            warnings.append("Automated review found issues or questions that need employee confirmation. See review notes in Reports.")
        update(stage="save_draft", progress=96)
        safe_employee = re.sub(r"[^A-Za-z0-9-]+", "-", config["employee_name"]).strip("-")[:60] or "Employee"
        version_label = datetime.fromtimestamp(float(clock()), timezone.utc).strftime("%Y%m%d-%H%M%S")
        prefix = f"Annual-Review-{safe_employee}-{config['year']}-Draft-{version_label}"

        def upload_export(document: dict, format: str, suffix: str = "") -> None:
            data, _, mime = make_export(document, format)
            uploaded = box.upload(config["reports_folder_id"], f"{prefix}{suffix}.{format}", data, mime)
            identifier = box_id(uploaded["id"])
            key = "review_notes" if suffix else format
            state["report_ids"][key] = identifier
            state["reports"].append({"id": identifier, "name": f"{prefix}{suffix}.{format}",
                                     "url": f"https://app.box.com/file/{identifier}", "format": format})
            save()  # Preserve partial uploads if a later format fails.

        upload_export(run, "docx")
        upload_export(run, "pdf")
        upload_export(_review_document(run), "docx", "-Review-notes")
        state.update(status="completed", stage="ready", progress=100, completed_fingerprint=fingerprint,
                     completed_at=float(clock()), failed_fingerprint="")
        describe(f"Draft ready: Word, PDF and review notes are in Reports. {state['evidence_count']} evidence references. Employee review required.")
        save()
        return deepcopy(state)
    except Exception as error:
        safe = _safe_error(error)
        state.update(status="failed", stage="failed", failed_at=float(clock()),
                     failed_fingerprint=state.get("fingerprint", ""), error={"code": safe.code, "message": str(safe)})
        if safe.code == "source_changed":
            describe("Source documents changed during generation. No draft was published. Waiting for the updated uploads to settle.")
        else:
            describe("Draft generation failed. This input version will not be retried automatically. Check the service before changing an input document to retry.")
        save()
        raise safe from None
