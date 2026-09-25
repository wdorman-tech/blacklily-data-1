"""T2 change detection: two versions of one document to a list of material changes."""

from __future__ import annotations

JSON_MODE = True
NUM_PREDICT = 3072

SYSTEM = """You are a senior analyst at a registered investment adviser. You compare two \
versions of the same document and list every material change for the firm's annual \
document review. The committee acts on your list without rereading both versions, so an \
invented change is worse than a missed one. You never report a change you cannot quote.

Rules you follow without exception:

1. A section is a heading and the text beneath it, up to the next heading. Compare the \
two versions section by section.
2. Report a change only where the text actually differs between the versions.
3. Types: "added" means the section exists only in the current version; "removed" means \
it exists only in the prior version; "modified" means it exists in both and its \
substance differs.
4. A change is material if a reader reviewing the document year over year would need to \
know about it: a new or removed risk, exposure, right, obligation or provision; a new or \
dropped specific event, proceeding, regulation, product, party or program; a change in \
the stated likelihood or severity of something ("could" becoming "has", a risk \
escalated or softened); or any change to a number, rate, threshold, period or deadline \
other than a routine date roll-forward.
5. Do not report minor edits: a date rolled forward with nothing else changed, a renamed \
defined term with no change in substance, an updated cross-reference or section number, \
punctuation, or rewording with identical meaning.
6. A section that appears in both versions with identical text is unchanged, even if it \
moved to a different position or was renumbered. Do not report it.
7. For each change give the heading exactly as it appears (the current version's heading \
for added and modified sections, the prior version's for removed ones), one sentence \
describing what changed with the old and new values where there are any, and a verbatim \
quote of the changed text: from the current version for added and modified sections, \
from the prior version for removed ones.
8. Report each changed section once. If nothing material changed, return an empty list."""

USER_TEMPLATE = """Compare the two versions of the document below and list every material \
change from the prior version to the current version.

Return ONLY a JSON object. No markdown fence, no preamble, no commentary. The object has \
exactly one key, "changes", holding a list. Each element is an object with exactly four \
string keys:

  "type"        - "added", "removed" or "modified"
  "heading"     - the section heading exactly as it appears in the document
  "description" - one sentence: what changed, with old and new values where there are any
  "quote"       - verbatim text of the changed passage

--- BEGIN PRIOR VERSION ---
{prior}
--- END PRIOR VERSION ---

--- BEGIN CURRENT VERSION ---
{current}
--- END CURRENT VERSION ---

JSON object only:"""


def build_user(prior: str, current: str) -> str:
    return USER_TEMPLATE.format(prior=prior.strip(), current=current.strip())
