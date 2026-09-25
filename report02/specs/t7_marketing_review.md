# T7. Marketing review flagging: authoring spec

The system under test reads a draft marketing piece from an SEC-registered investment
adviser and surfaces candidate issues for a human reviewer, against a fixed checklist
derived from the text of Rule 206(4)-1 under the Investment Advisers Act (the marketing
rule). It returns `{"flags": [{"category": "C1".."C9", "quote": "verbatim span", "reason": ""}]}`.
The framing is surfacing candidates for a person to review; it never decides anything.

## Checklist (fixed)

| code | candidate issue | rule text it derives from |
|---|---|---|
| C1 | Testimonial or endorsement without clear and prominent disclosure of client status, compensation, and material conflicts | 206(4)-1(b)(1) |
| C2 | Gross performance without net performance shown with at least equal prominence | (d)(1) |
| C3 | Performance of a portfolio (not a private fund) without 1-, 5- and 10-year periods | (d)(2) |
| C4 | Performance time periods or results chosen in a way that is not fair and balanced (cherry-picked window) | (a)(6) |
| C5 | Hypothetical, model or backtested performance without the required criteria, assumptions and risk disclosures | (d)(6) |
| C6 | Untrue or unsubstantiated material statement of fact ("never lost money", "top-ranked", "guaranteed") | (a)(1), (a)(2) |
| C7 | Third-party rating or ranking without the date, period, rater identity and compensation disclosure | (c) |
| C8 | Extracted performance (selected winning positions) without the total portfolio's performance | (d)(5), (a)(5) |
| C9 | Benefits described without fair and balanced treatment of material risks or limitations | (a)(4) |

## Your pieces

The assignment gives piece ids. For each write `corpus/t7/<split>/<piece_id>.md` and
`keys/t7/<piece_id>.json`.

- 350 to 900 words. Forms: quarterly newsletter article, website "Our Performance" page
  copy, pitch deck slide text (slide-by-slide), LinkedIn post series, prospect email, seminar
  invitation, strategy one-pager, podcast show notes. Invented firm per piece.
- Plant 0 to 4 issues (across a batch of 5: exactly one clean piece with 0, the rest 2 to
  4). Each planted issue is a contiguous span of 8 to 45 words that clearly instantiates one
  checklist code. Spread codes: every code appears at least once per batch of 5.
- Add 1 or 2 **decoys** per piece: an element that looks like a checklist item but is
  handled properly (a testimonial WITH the three disclosures; gross shown next to net of
  equal prominence; a rating with date, period, rater and compensation; a hypothetical
  with criteria and risk disclosure). A decoy must not be flagged.
- Do not plant anything outside the checklist, and do not leave accidental issues: the rest
  of the text must be clean against all nine codes. Include normal footnote-style
  disclosures where a real piece would have them.

### Key schema (exactly)

```json
{
  "piece_id": "t7_p06",
  "form": "prospect email",
  "notes": "one sentence",
  "planted": [
    {"iid": "p1", "category": "C2", "span": "verbatim text from the piece", "explanation": "one sentence"}
  ],
  "decoys": [
    {"did": "d1", "looks_like": "C1", "span": "verbatim text", "why_ok": "one sentence"}
  ]
}
```

`span` must be copied character for character from the piece.

## Batches

- **Batch A:** `t7_p01`..`t7_p05` (dev)
- **Batch B:** `t7_p06`..`t7_p10` (test)
- **Batch C:** `t7_p11`..`t7_p15` (test)
- **Batch D:** `t7_p16`..`t7_p20` (test)
- **Batch E:** `t7_p21`..`t7_p25` (test)
