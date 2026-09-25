# T5. Meeting transcript to CRM: authoring spec

The system under test reads an automatic transcript of an adviser-client review meeting and
fills a fixed CRM record plus a list of action items. The output schema is fixed:

```json
{
  "meeting_date": "",
  "client_names": [""],
  "primary_goal": "",
  "retirement_target": "",
  "risk_tolerance": "",
  "risk_tolerance_change": "",
  "life_events": [""],
  "account_actions": [{"action": "", "account": "", "amount": ""}],
  "action_items": [{"task": "", "owner": "", "due": ""}],
  "next_meeting": ""
}
```

`NOT_FOUND` for anything not established in the meeting. `risk_tolerance_change` is
`from X to Y` or `no change`.

## Your transcript

Write `corpus/t5/<split>/<meeting_id>.md` and `keys/t5/<meeting_id>.json`.

**Transcript form.** 4,200 to 5,800 words. The raw output of a meeting transcription
tool: a short header (meeting title, date, duration 22 to 32 minutes, participants), then
turns as `[00:04:12] Dana Whitcombe (Advisor): ...`. Realistic speech: fillers (um, uh,
like, you know), false starts, self-interruptions written with an ellipsis, `[crosstalk]`,
`[inaudible]`, one or two transcription errors on a proper noun or number that a later turn
clarifies, small talk (weather, kids, a game, a trip) that carries no CRM content, the
adviser recapping at the end but incompletely. Two to four speakers: the adviser, one or
two clients, sometimes an associate or paraplanner who joins partway.

**Every transcript contains all of these:**

1. **A corrected figure.** A client states a number (a balance, salary, pension, sale
   price, gift amount) and corrects it later in the meeting, possibly several minutes later
   ("actually I pulled up the statement, it's 340 not 400"). The CRM must carry the
   corrected value. Key it with a `STALE_` reject on the first figure.
2. **A reassigned action item.** An item is assigned to one person and then, later,
   reassigned to someone else. Owner must be the final assignee.
3. **A changed due date** on a different item ("by Friday... actually make it the 14th").
4. **A tentative non-action.** Someone floats an idea that is explicitly deferred or
   declined ("maybe someday we'll look at a trust, not now"). It must not appear as an
   action item or account action.
5. **An adviser proposal the client declines.** Not an account action.
6. **Explicit risk tolerance discussion** ending in either a stated change or an explicit
   "no change".

Vary the scenario across transcripts (the assignment names yours). Put 4 to 7 genuine
action items and 1 to 4 account actions in each meeting. Due dates can be absolute ("the
14th", "October 3") or relative ("end of next week"); the key records the date as said,
plus the absolute date if the meeting date makes it computable.

### Key schema (exactly)

```json
{
  "meeting_id": "t5_m04",
  "title": "no dashes",
  "notes": "2 to 3 sentences on what is hard here",
  "scalar_fields": {
    "meeting_date": {"expected": "", "accept": ["regex"], "reject": {}},
    "client_names": {"expected": "", "accept": ["regex that must ALL match: list each name as its own pattern"], "match": "all", "reject": {}},
    "primary_goal": {"expected": "", "accept": ["regex"], "reject": {}},
    "retirement_target": {"expected": "", "accept": ["regex"], "reject": {"STALE_x": ["regex"]}},
    "risk_tolerance": {"expected": "", "accept": ["regex"], "reject": {}},
    "risk_tolerance_change": {"expected": "", "accept": ["regex"], "reject": {}},
    "next_meeting": {"expected": "", "accept": ["regex"], "reject": {}}
  },
  "life_events": [
    {"eid": "e1", "expected": "", "match": ["regex identifying this event"], "reject": {"STALE_x": ["regex"]}}
  ],
  "account_actions": [
    {"aid": "a1", "expected": "", "match": ["regex on action+account+amount text joined"], "amount_accept": ["regex"], "amount_reject": {"STALE_x": ["regex"]}}
  ],
  "action_items": [
    {"iid": "i1", "expected_task": "", "match": ["regex on the task text"], "owner_accept": ["regex"], "owner_reject": {"STALE_OWNER": ["regex"]}, "due_accept": ["regex"], "due_reject": {"STALE_DUE": ["regex"]}, "trap": "reassigned | due_changed | none"}
  ],
  "non_actions": [
    {"nid": "n1", "what": "", "match": ["regex that would identify it if wrongly listed"], "kind": "tentative | declined_proposal"}
  ],
  "corrected_figures": [
    {"what": "", "said_first": "", "corrected_to": "", "field": "life_events | account_actions | scalar:<name>"}
  ]
}
```

The `match` regexes are applied to each item the system returns, to pair it with the key
item. They must be specific enough not to match other items and loose enough to match any
reasonable paraphrase (key on the distinctive noun: "529", "Roth", "beneficiary", "RMD").
Unmatched system items are later reviewed by an adjudicator against the transcript, so
the key must list every genuine action item, life event and account action in the meeting.

## Meetings

- **t5_m01 (dev):** couple, early 60s, planning retirement timing; one spouse's pension election.
- **t5_m02 (dev):** recently widowed client; beneficiary updates, survivor benefits, liquidity.
- **t5_m03 (dev):** business owner mid-sale of a company; proceeds, escrow, tax.
- **t5_m04 (test):** young tech employee with RSUs and ISOs; concentration, AMT, house down payment.
- **t5_m05 (test):** divorcing client; QDRO, account retitling, cash-flow.
- **t5_m06 (test):** parents of a child with a disability; special needs trust, ABLE account, guardianship.
- **t5_m07 (test):** retired couple, RMDs, Roth conversions, charitable giving (QCDs, a donor-advised fund).
- **t5_m08 (test):** physician couple with high income; backdoor Roth, disability insurance, 529s for three kids.
- **t5_m09 (test):** client inheriting a rental property portfolio from a parent; step-up, sell vs hold.
- **t5_m10 (test):** small business owner; SEP vs solo 401(k), cash management, key-person insurance.
- **t5_m11 (test):** client caring for an aging parent; long-term care, power of attorney, gifting.
- **t5_m12 (test):** couple relocating to another state for a job; state tax residency, home sale, 401(k) rollover.
