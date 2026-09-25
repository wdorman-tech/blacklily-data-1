"""Extraction schema for the RIA / family-office fund-document diligence workflow.

One workflow: long private-fund offering document -> structured key terms with
section citations. This module owns the field list, the extraction prompt, and
the JSON contract shared by the Claude baseline and the local model.
"""

from __future__ import annotations

FIELDS: list[tuple[str, str]] = [
    ("fund_name", "Full legal name of the fund entity being offered."),
    ("fund_domicile", "Jurisdiction of organization of the offered entity."),
    (
        "fund_structure",
        "Open-end (redeemable) or closed-end (drawdown, no redemptions), and "
        "whether master-feeder.",
    ),
    (
        "management_fee",
        "Annual management fee rate AND the basis it is charged on. Give every "
        "class or tier.",
    ),
    (
        "performance_fee",
        "Performance allocation / incentive allocation / carried interest rate. "
        "Give every class.",
    ),
    (
        "hurdle_rate",
        "Preferred return, hurdle or benchmark the performance fee is subject "
        "to. State the type (hard/soft, catch-up) if given.",
    ),
    (
        "high_water_mark",
        "Whether a high water mark or loss carryforward applies, and whether it "
        "is perpetual or resets.",
    ),
    ("minimum_initial_investment", "Minimum INITIAL subscription or capital commitment."),
    (
        "lockup_period",
        "Lock-up. Distinguish a hard lock from a soft lock (early redemption "
        "charge). Give every class.",
    ),
    ("redemption_frequency", "How often interests may be redeemed."),
    ("redemption_notice_days", "Advance written notice required to redeem."),
    ("gate_provision", "Redemption gate: level (fund or investor) and threshold."),
    (
        "key_man_provision",
        "Key person clause: who is named and what it triggers.",
    ),
    (
        "gp_commitment",
        "Required GP / sponsor / manager commitment. A disclosed current "
        "holding is NOT a commitment.",
    ),
    ("fund_term", "Term of the fund, including extensions, or perpetual."),
    ("auditor", "Independent registered public accounting firm CURRENTLY appointed."),
    ("administrator", "Fund administrator."),
    ("prime_broker", "Prime broker(s)."),
    ("legal_counsel", "Law firm(s) acting as counsel to the fund."),
    (
        "mfn_election",
        "Whether a most favored nation election on side letters is offered, and "
        "its scope.",
    ),
]

FIELD_NAMES: list[str] = [name for name, _ in FIELDS]

NOT_FOUND = "NOT_FOUND"
NOT_APPLICABLE = "NOT_APPLICABLE"

SYSTEM_PROMPT = """You are a diligence analyst at a registered investment adviser. \
You read private fund offering documents and extract key investment terms into \
structured data for the firm's investment committee.

You are accurate above all else. An invented term is far worse than a missing \
one: a fabricated fee or lock-up sends the committee into a negotiation with the \
wrong facts. You never guess, never infer a market-standard value, and never fill \
a field from what similar funds usually do.

Rules you follow without exception:

1. Every value must be supported by text that actually appears in the document.
2. If the document does not state a term, the value is exactly NOT_FOUND.
3. If the document states that a term does not exist or does not apply to this \
fund, the value is exactly NOT_APPLICABLE, and you say so in the quote.
4. Amendments, supplements and amended-and-restated sections SUPERSEDE the \
original body text. Where a supplement changes a term, report the AMENDED value, \
not the original. Read the entire document before answering.
5. Where a term differs by share class, tier or period, report every variant in \
one value string.
6. A disclosed current holding, estimate or expectation is not a binding \
commitment. Do not report one as the other.
7. Every citation must be a section or appendix identifier that appears in the \
document.
8. Every quote must be copied verbatim from the document."""

USER_PROMPT_TEMPLATE = """Extract the key investment terms from the fund offering \
document below.

Return ONLY a JSON object. No markdown fence, no preamble, no commentary. The \
object has exactly one key per field listed. Each field maps to an object with \
exactly three string keys:

  "value"    - the extracted term, or NOT_FOUND, or NOT_APPLICABLE
  "citation" - the section or appendix where you found it (e.g. "Section 4.1", \
"Appendix A", "Supplement No. 1, Section S-2"), or "" if the value is NOT_FOUND
  "quote"    - a verbatim sentence or clause from the document that supports the \
value, or "" if the value is NOT_FOUND

Fields to extract:
{field_spec}

Reminder: a supplement or amendment at the end of the document overrides the \
original body text. Report the value that is currently in effect.

--- BEGIN DOCUMENT ---
{document}
--- END DOCUMENT ---

JSON object only:"""


# --- Ablation prompts -------------------------------------------------------
# What a reasonable person writes on the first attempt, before any of the
# grounding discipline is added. Used to measure what the prompt is worth.

NAIVE_SYSTEM_PROMPT = "You are a helpful assistant that extracts information from documents."

NAIVE_USER_PROMPT_TEMPLATE = """Read the fund document below and pull out the key \
terms. Return JSON with one key per field: {field_list}.

Each field should have a "value", a "citation", and a "quote".

{document}"""


def build_naive_user_prompt(document: str) -> str:
    return NAIVE_USER_PROMPT_TEMPLATE.format(
        field_list=", ".join(FIELD_NAMES), document=document
    )


def field_spec() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in FIELDS)


def build_user_prompt(document: str) -> str:
    return USER_PROMPT_TEMPLATE.format(field_spec=field_spec(), document=document)


def empty_record() -> dict[str, dict[str, str]]:
    return {n: {"value": "", "citation": "", "quote": ""} for n in FIELD_NAMES}
