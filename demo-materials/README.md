# Synthetic annual-review demo materials

All people, products, documents, metrics and organizations in this folder are
fictional. These are reproducible demonstration fixtures, not real employee,
customer or company data. Upload only the nine `.docx` and `.pdf` files in
`files/` to one Box demo folder. The Markdown files are versioned authoring
sources, not demo inputs. Rebuild the four Word and five PDF documents with
`python scripts/build_demo_documents.py`. This README is explanatory and is
excluded from report inputs. The earlier mixed feedback and direction Markdown
file remains an authoring reference; it is not a final demo input.

The native Box folder structure is:

```
Annual Review - Alex Chen - 2026/
  Projects/          # Source documents 02 through 07
  Peer Feedback/     # Qualitative peer feedback document 09
  Annual Plans/      # Review context 01 and proposed product directions 08
  Reports/           # Generated reports and human review outputs
```

`manifest.json` maps each actual document filename to its source category.
Run `python scripts/setup_box_demo.py` to create this structure under the Box
identity configured by `.env`, upload the real documents, and save private
non-secret IDs in `.local/native-config.json` (mode 600). To reuse a dedicated
existing root, supply `--root-folder-id ID`. Existing identical content is
reused; different existing content is not overwritten. Unrelated files and
folders remain untouched.

The report subject is Alex Chen, a product engineer. The reporting year is 2026,
with evidence available through October 14. This is an annual-review draft, so
the agent must not imply that November or December results already exist.

The intentionally different sources test whether the agent can distinguish:

- Atlas design target: 30% faster onboarding, from 10 to 7 minutes.
- Atlas observed pilot result: 20% faster, from 10 to 8 minutes, 300 participants.
- Alex's Atlas contribution: instrumentation and verification, not leadership of
  the entire project. The onboarding improvement belongs to the team.
- Beacon design target: about 35% faster search; the prototype target is not the
  final result.
- Beacon observed pilot result: 4.2 to 3.1 minutes (about 26.2% lower median time).
- Alex's Beacon contribution: prototype and evaluation; production rollout was
  owned by another engineer.
- Product audience and next-year opportunities versus delivered impact.
- A stale Atlas status page that repeats the target after pilot data exists.
- Missing personal challenge, lessons learned and next-year employee goals. The
  agent should ask Alex or leave them pending, rather than manufacture a story.

Suggested checks: no report should say "Alex led Atlas", "Atlas improved by
30%", "Beacon achieved 35%", "all customers improved", or treat next-year
direction as completed work. A defensible report can say Alex instrumented and
verified an Atlas pilot in which the team observed a 20% improvement, and
prototyped/evaluated Beacon search with a 4.2-to-3.1-minute pilot result.

Use the Box file IDs and versions created during upload as the authoritative
source identities. Filenames and this README are not substitutes for citations
to the numbered source documents.
