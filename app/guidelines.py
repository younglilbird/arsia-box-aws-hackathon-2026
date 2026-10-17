"""Versioned writing guidance, separate from employee evidence and templates."""
from __future__ import annotations

LEADERSHIP_SOURCE = "https://www.amazon.jobs/content/en/our-workplace/leadership-principles"
WRITING_SOURCE = "https://hr.ucdavis.edu/performance-appraisals/writing-resources/ee"

REPORT_TEMPLATE = (
    {"heading": "Annual Review Summary", "purpose": "Describe three to five supported accomplishments, including personal responsibility, actions, customer impact and reflection."},
    {"heading": "Leadership Principles Summary", "purpose": "Explain how specific documented behavior demonstrates relevant leadership principles and helps customers."},
    {"heading": "Next Year Goals", "purpose": "Describe specific growth actions and customer-impact priorities, clearly separating proposals from agreed commitments."},
    {"heading": "Peer Feedback Summary", "purpose": "Synthesize the supplied qualitative feedback, retaining reviewer attribution, strengths and constructive feedback."},
)

# Principle names are Amazon's; descriptions are concise application guidance.
LEADERSHIP_PRINCIPLES = [
    {"name": "Customer Obsession", "description": "Connect decisions to a documented customer need."},
    {"name": "Ownership", "description": "Show sustained responsibility and thoughtful handover."},
    {"name": "Invent and Simplify", "description": "Explain a practical simplification and its effect."},
    {"name": "Are Right, A Lot", "description": "Show judgment tested against alternative evidence."},
    {"name": "Learn and Be Curious", "description": "Describe documented learning applied to work."},
    {"name": "Hire and Develop the Best", "description": "Use concrete examples of developing others."},
    {"name": "Insist on the Highest Standards", "description": "Explain checks that prevent recurring defects."},
    {"name": "Think Big", "description": "Connect a broader opportunity to specific actions."},
    {"name": "Bias for Action", "description": "Show a considered decision under uncertainty."},
    {"name": "Frugality", "description": "Document effective use of limited resources."},
    {"name": "Earn Trust", "description": "Show candid communication and reliable collaboration."},
    {"name": "Dive Deep", "description": "Explain investigation behind a finding or decision."},
    {"name": "Have Backbone; Disagree and Commit", "description": "Document constructive disagreement and subsequent commitment."},
    {"name": "Deliver Results", "description": "Connect personal execution to supported outcomes."},
    {"name": "Strive to be Earth’s Best Employer", "description": "Show actions improving colleagues' working experience."},
    {"name": "Success and Scale Bring Broad Responsibility", "description": "Consider documented consequences beyond immediate delivery."},
]

WRITING_GUIDANCE = """
Build the self-review around meaningful accomplishments. For each project,
explain the problem and audience, the employee's own responsibility, specific
actions and decisions, and the supported outcome. Include available baselines,
observed results, dates, population and limitations. Distinguish personal
deliverables from team results and targets from measurements. Use concrete
verbs and concise first-person prose. Include documented collaboration,
feedback, challenges, learning and future goals when supported. Ask the employee
for missing personal context instead of inventing it.

Write with confidence and economy. Lead with the strongest supported actions
and customer impact. Use only the curated fifteen-to-twenty key evidence items,
or fewer when the material is sparse. Dates, authors and routine metadata are
context, not accomplishments. Keep important limitations and correct attribution,
but state them naturally once rather than repeating apologetic disclaimers.
Explain what I owned and delivered; pair that contribution with the measured
team result without claiming sole credit or unsupported causation.

Use exactly four main sections, in this order: Annual Review Summary,
Leadership Principles Summary, Next Year Goals, Peer Feedback Summary. Use
subsections for individual accomplishments and other useful groupings. Aim for
three to five distinct accomplishments when the source material supports them;
never invent or duplicate achievements to reach a count. Keep all four main
sections even when evidence is missing, and state the specific gap briefly.
Future actions may be grounded proposals, clearly labeled for discussion,
rather than fabricated agreements. Peer feedback represents supplied opinions,
not independently measured impact. Do not assume the employee can access
feedback that has not actually been provided to this workspace.

Use Leadership Principles as an interpretive writing guide. Select only
principles supported by specific behavior and cite that evidence. Explain the
connection naturally within the accomplishment; avoid a checklist or generic
claims that the employee embodies a principle. Do not reward the number of
principles mentioned. Prefer two to five strong connections over broad coverage.
Using SQL or instrumentation does not establish Frugality without documented
resource constraints or savings. Task coordination does not establish hiring,
coaching or developing others. Completing work does not by itself establish
risk-taking or decision-making under uncertainty. An unsupported principle is
omitted, not a weakness in the employee. Evaluate the quality of the draft and its supporting evidence,
not the employee's performance rating or promotion eligibility.
""".strip()


def guideline_context() -> dict:
    """Return trusted application guidance without mixing in source facts."""
    return {
        "version": "amazon-lp-writing-v2-four-sections",
        "official_source": LEADERSHIP_SOURCE,
        "writing_source": WRITING_SOURCE,
        "principles": [dict(item) for item in LEADERSHIP_PRINCIPLES],
        "report_template": [dict(item) for item in REPORT_TEMPLATE],
        "writing_guidance": WRITING_GUIDANCE,
    }
