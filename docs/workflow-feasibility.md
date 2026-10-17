# Annual self-review workflow feasibility

Assessed during the hackathon on October 16, 2026.

## Conclusion

The core AWS and Box APIs support the proposed workflow. A small synthetic-data pipeline has been exercised: three Box documents -> Box AI analysis with citations -> local AWS Bedrock writing -> generated file saved to Box. This is a feasibility probe; the finished product, review loop, document-format parsing, export layout, and deployment are not yet implemented.

## Recommended implementation

1. Bind the employee, review period, and explicitly authorized Box folders.
2. Recursively enumerate folders with pagination. Record which files were processed, excluded, or could not be parsed.
3. Read each document through its original content, a text/Markdown representation, or Box AI extraction. Process long files in bounded chunks.
4. Extract project purpose, scope, audience, planned impact, measured outcomes, employee actions, collaboration, product direction, and learning. Preserve source excerpts and file versions.
5. Merge evidence by project and time. Distinguish targets from measured results, team results from individual contribution, and plans from delivered work.
6. Ask a few focused questions for facts that are absent or contradictory.
7. Generate a concise report with annual overview, key contributions, impact, collaboration, reflection, and next steps.
8. Check source references and numbers, review factual support and writing, and revise once. Remaining uncertainties go to the human reviewer.
9. Allow editing and evidence inspection, render an editable document and PDF, check the actual page count, and save the deliverables to Box.

For the first demo, use 8-15 short, authorized or synthetic documents across a few projects. Keep detailed evidence in the review interface rather than expanding the final report beyond 2-3 pages.

## Platform boundaries

- Box Ask accepts explicit file IDs; multiple-item QA supports at most 25 files. Its current API describes a 2 MB text-representation limit. It is not a recursive folder scan. Enumerate and batch documents in our application.
- Box Search is permission-bound and indexes current document versions with a content-length limit and indexing delay. Use it as a discovery aid, not proof that every relevant passage has been covered.
- Text and Markdown representations offer an alternative to AI extraction for supported formats. Availability and parsing quality for our actual PDF/DOCX/PPTX samples still need testing. Scanned pages and embedded charts need separate validation.
- The tested CCG identity is the app's service account. Access to an employee's own folders must be separately authorized and tested.
- Bedrock can perform extraction, synthesis, generation, and critique through normal model calls. Start with bounded per-document extraction and an evidence table; a managed agent service or vector database is not a prerequisite for this scoped first version.
- The first generated draft had omissions despite successful API calls and citations. Model self-review is a quality-improvement step, not proof that all facts are correct.
- DOCX/PDF generation can be implemented in application code and uploaded through the already-tested Box upload API. The exported page count still needs rendering and verification.

## Confirm with event staff before leaving

1. Does our own Box Developer account plus Box file/AI APIs and AWS Bedrock meet this track's requirements? Are any specific services mandatory for an award?
2. Are there event credits, access activations, or sample materials that must be claimed on site? Will accounts and credits remain usable from home and during judging?
3. Is a public live product URL required in addition to the GitHub source URL? Is a recording required, and how long must the demo remain accessible?
4. What timezone applies to the 1 PM deadline, where is the submission form, and must participants return on site for judging?

The underlying API implementation can continue from home. Event-specific access and submission conditions require the organizer's confirmation.

## Official references

- [Box Ask API](https://developer.box.com/reference/post-ai-ask)
- [Box folder listing](https://developer.box.com/reference/get-folders-id-items)
- [Box search indexing](https://developer.box.com/guides/search/indexing)
- [Box text representations](https://developer.box.com/guides/representations/text)
- [Box Markdown representations](https://developer.box.com/guides/representations/markdown)
- [Box CCG identities](https://developer.box.com/guides/authentication/client-credentials)
- [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
