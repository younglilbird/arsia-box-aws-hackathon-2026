#!/usr/bin/env python3
"""Export the actual application prompt text without importing credentials."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def constant(value):
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value.strip()
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "strip":
        return constant(value.func.value)
    raise ValueError("Expected a literal prompt string.")


def assignment(tree, name):
    matches = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    if len(matches) != 1:
        raise ValueError(f"Expected one {name} assignment.")
    return constant(matches[0])


def call_prompt(tree, marker):
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or not node.args:
            continue
        if node.func.attr not in {"json_call", "markdown_call"}:
            continue
        value = node.args[0]
        if isinstance(value, ast.BinOp):
            value = value.left
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and marker in value.value:
            matches.append(value.value.strip())
    if len(matches) != 1:
        raise ValueError(f"Expected one prompt containing {marker}.")
    return matches[0]


def main():
    workflow = ast.parse((ROOT / "app/workflow.py").read_text())
    evaluation = ast.parse((ROOT / "app/evaluation.py").read_text())
    improvement = ast.parse((ROOT / "app/improvement.py").read_text())
    guidelines = ast.parse((ROOT / "app/guidelines.py").read_text())
    sections = [
        ("Shared source-handling rule", assignment(workflow, "UNTRUSTED_DATA_RULE")),
        ("Evidence extraction", call_prompt(workflow, "You are extracting evidence")),
        ("Initial report writing", assignment(workflow, "writing_instruction")),
        ("Evaluation, used in two separate calls", assignment(evaluation, "EVALUATION_INSTRUCTION")),
        ("Revision from the first evaluation", call_prompt(workflow, "You are revising an annual self-review")),
        ("Employee-guided improvement of the same draft", assignment(improvement, "PATCH_INSTRUCTION")),
        ("Shared writing and template guidance", assignment(guidelines, "WRITING_GUIDANCE")),
        ("Structured-output rule", assignment(workflow, "JSON_OUTPUT_RULE")),
    ]
    lines = ["# Arsia application prompts", "",
             "These are the actual English prompts extracted from the application source. Regenerate with `python scripts/export_prompts.py` after changing them.", "",
             "Workflow: Box documents → verified evidence → first draft → evaluation 1 → revised draft → final checks → evaluation 2 → employee review and Box Word/PDF outputs.", "",
             "The shared source-handling rule is prepended to Bedrock calls. Trusted writing guidance and the versioned Leadership Principles in `app/guidelines.py` are supplied to writing, revision and evaluation. Document text, notes and model outputs remain untrusted data.", "",
             "Evaluation 2 receives the exact final report and sources, without the first evaluation's scores or its initial-draft Box AI advice. Code computes totals and report hashes. The provisional rubric is documented in [evaluation.md](evaluation.md).", ""]
    lines.extend(["After generation, employee answers patch the same report rather than creating a new draft. Each manually requested round adds only source-backed, question-relevant prose and receives a fresh evaluation. The target score is advisory; the application does not invent facts or run indefinitely to reach it.", ""])
    for title, prompt in sections:
        lines.extend(["## " + title, "", "```text", prompt, "```", ""])
    lines.extend(["## Code checks outside the prompts", "",
                  "The application matches evidence quotations to literal source text, rejects unknown evidence references, enforces the four main report sections, validates scores and principle names, and checks source versions before publishing. A prompt alone does not establish factual correctness.", "",
                  "The source contains the remaining bounded repair instructions and the optional Box AI check: [workflow.py](../app/workflow.py). The evaluations and their schema are in [evaluation.py](../app/evaluation.py).", ""])
    destination = ROOT / "docs/prompts.md"
    destination.write_text("\n".join(lines))
    print("Exported actual application prompts to docs/prompts.md.")


if __name__ == "__main__":
    main()
