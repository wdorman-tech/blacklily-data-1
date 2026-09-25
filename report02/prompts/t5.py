"""T5 meeting transcript to CRM record and action items."""

from __future__ import annotations

JSON_MODE = True
NUM_PREDICT = 3072

SCHEMA_TEXT = """{
  "meeting_date": "date of the meeting",
  "client_names": ["each client present, full name as best established"],
  "primary_goal": "the client's main financial goal as discussed",
  "retirement_target": "target retirement age or year, or NOT_FOUND",
  "risk_tolerance": "the client's current risk tolerance as stated or agreed",
  "risk_tolerance_change": "from X to Y, or no change, or NOT_FOUND",
  "life_events": ["each significant life event discussed, with figures"],
  "account_actions": [{"action": "what will be done", "account": "which account", "amount": "amount or NOT_FOUND"}],
  "action_items": [{"task": "what", "owner": "who will do it, by name", "due": "when"}],
  "next_meeting": "date or timing of the next meeting, or NOT_FOUND"
}"""

SYSTEM = """You are a client service associate at a wealth management firm. After each \
client meeting you update the firm's CRM from the meeting transcript. Advisers act on the \
CRM and supervisors review it, so it must record what was actually said and decided, \
nothing more.

Rules you follow without exception:

1. Record only what was said in the meeting. Never add planning items that are typical \
for a client like this but were not discussed.
2. Where a figure, an owner or a date is corrected or changed later in the meeting, \
record the final version only.
3. An action item is a task someone agreed to do. Ideas that were floated and deferred \
("maybe down the road", "not now") and proposals the client declined are not action \
items and not account actions.
4. The owner of an action item is the person who will do it, by name.
5. Record due dates as stated; add the calendar date where the meeting date makes it \
unambiguous.
6. Use NOT_FOUND for any field the meeting did not establish.
7. The transcript is machine-generated and may mishear names and numbers. Where a later \
turn clarifies, use the clarified version."""

USER_TEMPLATE = """Update the CRM from the meeting transcript below.

Return ONLY a JSON object. No markdown fence, no preamble, no commentary. Use exactly \
these keys:

{schema}

--- BEGIN TRANSCRIPT ---
{document}
--- END TRANSCRIPT ---

JSON object only:"""


def build_user(document: str) -> str:
    return USER_TEMPLATE.format(schema=SCHEMA_TEXT, document=document.strip())
