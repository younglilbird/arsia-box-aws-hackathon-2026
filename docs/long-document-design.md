# Long document extraction and evidence reuse

Status: design proposal only, 2026-10-17. The current priority is a successful end-to-end generation. None of the cache, parser or benchmark changes below is implemented by this document. No new AWS service is required for the first phase.

## Current behavior and its limits

The implemented path is Box version-pinned download → local text extraction → passage-level Bedrock extraction → literal quote validation → evidence ledger → draft → evaluation → one revision → final source checks → second evaluation → employee review and Box exports.

| Area | Implemented behavior | Consequence for long or noisy documents |
| --- | --- | --- |
| Input scope | At most 25 files; native/local inputs are Word and PDF, each at most 12 MB. PDF parsing rejects more than 80 pages. | A file being accepted does not establish that all its content was analyzed. |
| Text parsing | DOCX paragraphs followed by table rows flattened to strings; PDF page text joined together. | Heading hierarchy, original paragraph/table order and page-level source locations are not retained as structured data. Image-only content needs OCR. |
| Text budget | `min(30,000, 160,000 / selected_file_count)` characters from the **beginning** of each file. | With nine selected files, each receives roughly 17,777 characters. A late pilot result can be omitted while early architecture details consume the budget. Character counts are not token counts. |
| Passage extraction | 12,000-character windows, 400-character overlap; at most 32 extraction calls, processed in file order. Up to 10 candidate facts per passage and 160 validated candidates. The report path curates at most 20 evidence items for writing and display; in-progress extraction candidates stay private. | Windows can separate table headers from values or split the qualification from a metric. Earlier files can exhaust the budget. Curation is a bounded selection, not proof that every relevant fact was retained. |
| Validation | The application binds source IDs, checks contiguous source quotes, assigns run-local EIDs and rejects invalid facts. A narrow literal peer-feedback fallback can recover feedback from a source with no model-retained facts. The final direct-quote guard removes invented quotation paragraphs. | Literal occurrence does not establish correct actor, project, time period, causal meaning or supersession. Those require source-aware interpretation. |
| Coverage | Read/analyzed characters, skipped files, truncation and zero-evidence source warnings are exposed. Overlapping analyzed intervals are counted once. | Character coverage is useful operational accounting; it is not fact recall. A fully read file may yield no retained facts. |
| Reuse | Private run JSON retains drafts, evidence and evaluations. There is no extraction cache or stage-resume path. | Starting another generation after a writer failure repeats discovery, parsing and extraction; nine short source files commonly require nine extraction calls again. |

These are application limits in `app/workflow.py`, `app/box_client.py` and `app/native.py`, not limits of Box or AWS.

## First change after the baseline works

Add a private local SQLite evidence cache and stage checkpoints before changing the extraction algorithm. Keep the current single-worker process, prompts, validation and report workflow.

Use `.local/evidence-cache.sqlite3` in a private directory. Cache access stays on the server; credentials and full source bodies are never added to API responses or application logs. A cache hit must still pass the current Box identity, configured-folder membership and source-version checks. A previously accessible document must not become readable solely because a cached row exists.

A cache key must cover:

- Workspace/access scope, Box file ID and exact `file_version.id`, document category and extracted-content hash.
- Parser version, chunk-policy version, chunk identity/offsets and chunk-content hash.
- Extraction prompt and schema versions, model/profile ID, inference parameters, normalized employee identity and reporting year.
- A hash of the complete canonical extraction input. The current task includes whole-corpus absence flags; until those flags are removed from document-local extraction, changes to them must invalidate affected cache entries too.

Box explicitly supports downloading a specified file version. Continue using the saved version instead of silently substituting the latest content. A missing version ID should make an item ineligible for durable reuse. [Box download API](https://developer.box.com/reference/get-files-id-content).

Store validated facts with their source/chunk binding, literal quote and local span, candidate questions, rejection counts, completed-empty status, usage and completion time. Store source text/blocks privately only if needed to avoid parsing again and revalidate quote spans; include their parser/content hashes. Do not cache run-global `E1` IDs: assign EIDs after loading facts in deterministic source/chunk order. Empty successful extraction is a cacheable result with an explicit zero-fact warning; invalid or interrupted output is not a successful empty result.

Commit each successful chunk transactionally. Keep per-run checkpoints for the evidence snapshot, initial draft, initial evaluation, revision, guarded final draft and final evaluation. Each downstream checkpoint includes its input hashes plus relevant template/guideline/rubric/model versions. If revision or evaluation fails, resume from completed extraction and the last compatible stage. Never construct an evaluation score for a stage that did not actually finish. An explicit new writing attempt can invalidate writing checkpoints while reusing unchanged evidence.

Minimal implementation seams: one `app/evidence_cache.py` module, a cache lookup/validated-result commit around the existing extraction call, and a resume option in the local worker. Avoid a new agent framework, embedding pipeline or cloud database for this step. DynamoDB becomes a separate proposal only when shared workers need durable coordination across machines; SQLite is sufficient for the current local single-worker demo.

## Next extraction design

Preserve source structure before adding model calls:

1. Parse ordered blocks with heading path, paragraph/table identity and original offsets. Preserve PDF page locations; mark uncertain reading order or missing OCR. Keep table headers with their rows and retain units, sample populations and footnotes. Textract Layout is a possible later route for layout-bearing PDFs; its output distinguishes titles, section headers, tables, lists and other layout objects. It is not integrated here. [Textract Layout response](https://docs.aws.amazon.com/textract/latest/dg/layoutresponse.html).
2. Form bounded child passages along paragraph/section boundaries, with a small overlap and a parent-section context. A table should not be cut between its header and its metric row. If context repeats a header, mark that context separately: a synthesized header must not become a falsely “literal” source quote.
3. Rank passages using employee/project names, contribution verbs, metric units and useful section headings. Keep an explicit ledger of processed, failed, deprioritized and unprocessed blocks. Do not discard code, appendices or low-ranked text solely by keyword: an important result may appear there. Allocate a minimum opportunity to each file and sample lower-ranked sections; display the unprocessed remainder when the budget stops the run.
4. Extract atomic records with actor, project, action, metric/value/unit, baseline, population, period, status, source version and quote span. Keep constraints and negative evidence alongside achievements. Deduplicate overlapping passages without dropping the provenance of repeated statements.
5. Reconcile records before writing. Compare the same project/metric/population/period; do not treat a 30% **target** and 20% **observed** improvement as interchangeable. A dated, explicitly superseded snapshot may be retained as superseded evidence. A newer upload timestamp alone is not proof that a conflicting claim is authoritative. Preserve unresolved conflicts and ask a focused question.
6. Build the report from selected verified evidence plus material conflicts and coverage gaps. The evaluator also needs the relevant source context, not only summaries of earlier summaries. Leadership mappings remain interpretations of documented behavior, not additional accomplishments.

The existing untrusted-document rule remains mandatory. Quoted instructions, sample generated reports and schema examples are source data; they must not become employee facts or change the workflow. Exact-quote matching alone cannot make a quoted malicious instruction into a legitimate achievement.

AWS documents fixed, hierarchical and semantic chunking options; semantic chunking adds model cost. Those are useful comparison designs, not a reason to introduce a Knowledge Base into this bounded report generator. [Bedrock chunking](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html). For complex figures, tables or scans, AWS offers advanced parsing options; choosing one changes parsing cost and behavior and needs a measured trial. [Bedrock parsing](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-advanced-parsing.html).

Box AI remains a useful independent advisory check, not proof of exhaustive evidence retrieval. Its Ask API documents a maximum of 25 files and up to 2 MB of text representation, with oversized text truncated; returned citations still need checking. Our own review prompt separately limits the draft to 8,000 characters. [Box AI Ask](https://developer.box.com/reference/post-ai-ask). Box also offers structured metadata extraction, which could be benchmarked later; account availability and fidelity for this exact fact schema have not been tested. [Box structured extraction](https://developer.box.com/reference/post-ai-extract-structured).

## A benchmark that can expose failures

Create a synthetic, clearly labeled **14-page engineering document**, with a DOCX and equivalent text-based PDF rendition tested in separate runs. Verify actual page count after rendering. Target 40,000–60,000 extracted characters, with about 60% irrelevant schema definitions, configuration fragments, API examples and technical discussion. Add four short related documents: final pilot readout, stale status note, peer feedback and annual planning/context. The benchmark is proposed; no artifact or result is claimed here.

Place relevant material at the beginning, middle and end, including an observed result after character 30,000. Include:

- Design targets versus final measured outcomes, units, cohort sizes and limitations; a table with a header and a qualifying footnote near a passage boundary.
- Two people with overlapping responsibilities on Atlas and Beacon. One owns instrumentation; another owns backend rollout. Collaborators belong to specific projects.
- An older estimate explicitly superseded by a final readout, plus a genuinely unresolved pair of conflicting figures with the same scope.
- Qualitative, named peer feedback; explicit absence of personal reflection and unagreed individual goals.
- A quoted instruction to ignore prior rules and invent a larger result, and a sample report containing praise that is explicitly not an endorsement.

Before running a model, publish a private gold manifest with **24 accepted atomic facts**, **18 forbidden interpretations**, the conflict pair, two expected employee questions and exact source/version/page-or-block spans. Gold facts cover purpose/audience (3), individual actions (5), measured team results (3), targets/plans (3), scope/limitations (4), collaboration (2), qualitative feedback (2) and role/reporting context (2). Forbidden interpretations cover wrong actor/project (4), targets or stale values promoted to final results (4), unsupported business outcomes (3), irrelevant technical details (3), obeyed document instructions (2) and absence/example text promoted to personal achievement (2).

| Measure | Definition |
| --- | --- |
| Fact precision | Correct unique accepted facts / all unique retained factual assertions. A wrong actor, project, status, unit or period is incorrect even when its quote is literal. |
| Fact recall | Accepted gold facts recovered / 24. Facts beyond the current prefix budget remain in the denominator. Also report recall by source, category and document position. |
| Literal support | Retained quotations that match their pinned source span / all retained quotations. Report semantic correctness separately. |
| Negative-case rejection | Forbidden interpretations absent from evidence and report / 18; separately count any instruction-following violation. |
| Source and text coverage | Relevant sources yielding evidence / sources containing accepted gold facts; plus block/page/character coverage and all unprocessed ranges. Reading a file is not evidence coverage. |
| Conflict handling | Whether the superseded value stays superseded and the unresolved pair remains visible without arbitrary reconciliation. |
| Report support | Every numerical/attribution assertion has supporting evidence; no invented reflection, peer endorsement, ownership or agreed goal. |
| Retry efficiency | Cache hits/misses, extraction/writer/evaluator calls, observed tokens and elapsed time for cold, warm and resumed runs. |

Suggested acceptance targets, **not achieved results**: 100% literal support; at least 95% fact precision and 90% recall; all key actual metrics recovered; zero cross-person/project or instruction-following errors; both uncertainty questions preserved. Report failures rather than adjusting the gold set after seeing model output.

Compare the unchanged baseline, cache-only behavior, and later structure-aware extraction with the same fixture/model/prompt versions and budgets. Cache-only output must preserve the validated evidence set. A warm writer retry should require zero extraction calls; one changed source version should invalidate its compatible rows; one failed chunk should resume without recomputing completed chunks. Also test employee/year/schema/model changes, legitimate empty extraction and a crash between chunk completion and checkpointing. Log measured token usage; do not promise a cost or quality improvement until the benchmark has run.

## Delivery order

1. Finish and retain a successful current end-to-end run.
2. Add extraction caching/checkpoints and prove retry correctness on the existing demo.
3. Build the long-document fixture and publish baseline precision, recall and coverage.
4. Add structure-aware parsing/chunk scheduling only where the benchmark demonstrates loss.
5. Consider OCR, managed parsing or corpus retrieval only after a concrete unmet requirement appears.
