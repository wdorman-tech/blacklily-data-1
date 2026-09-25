"""Judge prompts. Frozen with the task prompts. The judge never sees which model wrote what."""

from __future__ import annotations

T4_SYSTEM = """You are a meticulous fact-checker at an investment research firm. You check \
an analyst's investment committee brief against the earnings release it was written \
from, and nothing else: no outside knowledge of the company. You are strict about \
figures, periods and GAAP versus non-GAAP basis, and fair about wording: a correct \
paraphrase counts, and a figure rounded correctly to the precision shown counts."""

T4_USER = """Check the brief against the release.

Part 1. For each key fact listed, decide:
  stated_correctly - the brief states the fact with the right figure(s), period and basis
  misstated        - the brief addresses the fact but gets a figure, period or basis wrong
                     (for example an adjusted figure presented as reported, or a year-to-date
                     figure presented as the quarter)
  absent           - the brief does not state it
Give the brief's own words as evidence (empty if absent).

Part 2. Split the brief into atomic factual claims: one checkable assertion each. Skip \
headings. Skip questions and recommendations for monitoring unless they assert a fact. \
For each claim decide:
  supported   - the release states it, or it follows directly from the release without any
                calculation the release does not show
  unsupported - the release does not state it, contradicts it, or it needs a calculation
                or outside knowledge
Give a short note for every unsupported claim.

--- KEY FACTS ---
{facts}
--- END KEY FACTS ---

--- RELEASE ---
{release}
--- END RELEASE ---

--- BRIEF ---
{brief}
--- END BRIEF ---"""

T4_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {"type": "object", "properties": {
            "fid": {"type": "string"},
            "verdict": {"type": "string", "enum": ["stated_correctly", "misstated", "absent"]},
            "evidence": {"type": "string"}}, "required": ["fid", "verdict", "evidence"]}},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "claim": {"type": "string"},
            "verdict": {"type": "string", "enum": ["supported", "unsupported"]},
            "note": {"type": "string"}}, "required": ["claim", "verdict", "note"]}},
    },
    "required": ["facts", "claims"],
}

T6_POINTS_SYSTEM = """You check client letters against the internal fact sheet they were \
drafted from. You decide whether the letter conveys specific points from the fact sheet. \
A faithful paraphrase counts. A point stated with a wrong figure or a changed meaning is \
distorted."""

T6_POINTS_USER = """For each point below, decide whether the letter conveys it.

--- POINTS ---
{points}
--- END POINTS ---

--- FACT SHEET ---
{sheet}
--- END FACT SHEET ---

--- LETTER ---
{letter}
--- END LETTER ---"""

T6_POINTS_SCHEMA = {
    "type": "object",
    "properties": {"points": {"type": "array", "items": {"type": "object", "properties": {
        "fid": {"type": "string"},
        "verdict": {"type": "string", "enum": ["conveyed", "not_conveyed", "distorted"]},
        "evidence": {"type": "string"}}, "required": ["fid", "verdict", "evidence"]}}},
    "required": ["points"],
}

T6_PAIR_SYSTEM = """You are the head of client service at a registered investment adviser. \
You review two draft quarterly letters written from the same internal fact sheet and \
decide which one you would rather send to this client. Judge clarity and tone only: \
how easily a client without financial training follows it, and whether the tone suits \
this client as described in the tone notes. Factual accuracy is checked separately; do \
not judge it here, and do not prefer a letter for being longer."""

T6_PAIR_USER = """Which letter would you rather send? Answer for clarity, for tone, and overall.

--- FACT SHEET ---
{sheet}
--- END FACT SHEET ---

--- LETTER A ---
{a}
--- END LETTER A ---

--- LETTER B ---
{b}
--- END LETTER B ---"""

T6_PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "clarity": {"type": "string", "enum": ["A", "B", "tie"]},
        "tone": {"type": "string", "enum": ["A", "B", "tie"]},
        "overall": {"type": "string", "enum": ["A", "B", "tie"]},
        "reason": {"type": "string"},
    },
    "required": ["clarity", "tone", "overall", "reason"],
}

T5_SYSTEM = """You audit CRM records against the client meeting transcript they were \
written from. You decide whether items in the record are established by the transcript."""

T5_USER = """The CRM record below was produced from the transcript. Some of its list \
items could not be matched to the answer key automatically, and some answer-key items were \
not found in the record automatically. For each item to check, decide:

  matches_key - it is the same item as one of the unfound answer-key items listed below
                (give that key id, and say whether its owner and due date are right
                according to the final version in the transcript; answer true for both
                when the item has no owner or date)
  supported   - the transcript establishes it (a life event, an agreed account action, or
                an action item someone agreed to do) but it is not one of the key items
  duplicate   - it restates, splits or overlaps another item already in the record
  unsupported - the transcript does not establish it: invented, a deferred idea, a
                declined proposal, or materially wrong

--- ITEMS TO CHECK ---
{items}
--- END ITEMS TO CHECK ---

--- UNFOUND ANSWER-KEY ITEMS ---
{missed}
--- END UNFOUND ANSWER-KEY ITEMS ---

--- FULL RECORD ---
{record}
--- END FULL RECORD ---

--- TRANSCRIPT ---
{transcript}
--- END TRANSCRIPT ---"""

T5_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["matches_key", "supported", "duplicate", "unsupported"]},
        "key_id": {"type": "string"},
        "owner_correct": {"type": "boolean"},
        "due_correct": {"type": "boolean"},
        "note": {"type": "string"}}, "required": ["n", "verdict", "key_id", "owner_correct", "due_correct", "note"]}}},
    "required": ["items"],
}

T5LIST_SYSTEM = """You grade CRM records against the client meeting transcript they were \
written from and the answer key for that meeting. You pair each answer-key item with the \
record's item that captures it, whatever the wording, and check owners, dates and figures \
against the final version said in the meeting. You are strict about figures, owners and \
dates, and fair about wording."""

T5LIST_USER = """Grade the record's list items (life events, account actions, action items) \
against the answer key.

1. For each answer-key item, give the number of the record item that captures it, or 0 if \
none does. One record item can capture only one key item. Then say whether the record \
item's figures are right (false if it carries a figure the meeting later corrected, or any \
other wrong figure; true if it has no figures), and, for action items, whether the owner and \
the due date are the final ones said in the meeting (true when the key item has no owner or \
date).
2. For each item the meeting mentioned but did not agree to (listed as NOT ACTIONS), say \
whether the record lists it as an account action or an action item anyway.
3. For each record item not paired with a key item, decide: supported (the transcript \
establishes it), duplicate (it restates or splits another record item), or unsupported \
(invented, a deferred idea, a declined proposal, or materially wrong).

--- ANSWER KEY ITEMS ---
{key_items}
--- END ANSWER KEY ITEMS ---

--- NOT ACTIONS ---
{non_actions}
--- END NOT ACTIONS ---

--- RECORD ITEMS ---
{record_items}
--- END RECORD ITEMS ---

--- TRANSCRIPT ---
{transcript}
--- END TRANSCRIPT ---"""

T5LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "key_items": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "record_n": {"type": "integer"},
            "figures_correct": {"type": "boolean"}, "owner_correct": {"type": "boolean"},
            "due_correct": {"type": "boolean"}, "note": {"type": "string"}},
            "required": ["id", "record_n", "figures_correct", "owner_correct", "due_correct", "note"]}},
        "non_actions": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "recorded": {"type": "boolean"}}, "required": ["id", "recorded"]}},
        "extra_items": {"type": "array", "items": {"type": "object", "properties": {
            "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["supported", "duplicate", "unsupported"]},
            "note": {"type": "string"}}, "required": ["n", "verdict", "note"]}},
    },
    "required": ["key_items", "non_actions", "extra_items"],
}

T7_SYSTEM = """You are a senior reviewer on the marketing review team of an SEC-registered \
investment adviser. You check whether a candidate issue raised by a first-pass reviewer \
is worth a reviewer's time under a fixed checklist."""

T7_USER = """A first-pass reviewer raised the flags below on this draft. Some known issues \
in the draft were not matched to any flag automatically; they are listed too. For each \
flag, decide:

  matches_known - it points at the same issue as one of the unmatched known issues (give
                  its id)
  legitimate    - a careful reviewer would want to look at this text under a checklist
                  code, but it is not one of the known issues
  not_an_issue  - the text does not raise any checklist issue, or it already carries what
                  the checklist requires

--- CHECKLIST ---
{checklist}
--- END CHECKLIST ---

--- FLAGS ---
{flags}
--- END FLAGS ---

--- UNMATCHED KNOWN ISSUES ---
{missed}
--- END UNMATCHED KNOWN ISSUES ---

--- DRAFT ---
{draft}
--- END DRAFT ---"""

T7_SCHEMA = {
    "type": "object",
    "properties": {"flags": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["matches_known", "legitimate", "not_an_issue"]},
        "known_id": {"type": "string"},
        "note": {"type": "string"}}, "required": ["n", "verdict", "known_id", "note"]}}},
    "required": ["flags"],
}

EQUIV_SYSTEM = """You check an analyst's extracted answers against an answer key. For each \
pair you decide whether the analyst's answer states the same substance as the key. Wording, \
order, formatting and extra correct detail do not matter. A different value, a missing \
required element (for example one share class of two, or the basis of a fee), or a \
reversed meaning does matter. You judge only against the key; you do not second-guess it."""

EQUIV_USER = """For each numbered pair, decide:
  equivalent     - the answer states the same substance as the key
  not_equivalent - the answer differs in a value, misses a required element, or means something else

--- PAIRS ---
{pairs}
--- END PAIRS ---"""

EQUIV_SCHEMA = {
    "type": "object",
    "properties": {"pairs": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["equivalent", "not_equivalent"]},
        "note": {"type": "string"}}, "required": ["n", "verdict", "note"]}}},
    "required": ["pairs"],
}
