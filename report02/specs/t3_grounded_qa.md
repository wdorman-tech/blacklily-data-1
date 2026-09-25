# T3. Grounded Q&A with abstention: authoring spec (firm packs and DDQs)

The system under test answers due diligence questionnaire (DDQ) questions from an
allocator, using only a pack of the adviser's own documents. Each answer is
`{answer, source_document, section, quote}`, or `answer = NOT_IN_DOCUMENTS` when the pack
does not answer the question. About a quarter of the questions are unanswerable from the
pack. Several answers were changed by a later policy memo that overrides an earlier
document.

## Your firm

You write one complete firm pack and its DDQ key. Start by writing a private "firm
bible" for yourself (facts, people, numbers, service providers, dates) in
`keys/t3/<firm_id>.bible.md` so the six documents agree with each other. Then write:

| file (in `corpus/t3/<split>/<firm_id>/`) | words | content |
|---|---|---|
| `01_brochure.md` | 4,300 to 5,300 | Written in the style of Form ADV Part 2A, organized by the Part 2A item headings (Item 1 Cover Page through Item 18 Financial Information): advisory business, fees and compensation, performance-based fees, types of clients, methods of analysis and risk of loss, disciplinary information, other financial industry activities, code of ethics and personal trading, brokerage practices, review of accounts, client referrals, custody, investment discretion, voting client securities, financial information. |
| `02_compliance_manual.md` | 4,300 to 5,300 | Policies and procedures: CCO role, code of ethics, personal trading and pre-clearance, gifts and entertainment, political contributions, insider trading and MNPI, marketing review, trade allocation and aggregation, best execution review, cybersecurity and information security, privacy, recordkeeping, electronic communications, annual review, training. |
| `03_valuation_policy.md` | 1,700 to 2,400 | Valuation committee (composition, quorum, frequency), pricing hierarchy and sources, level 3 methodology, price challenges and overrides (who approves), stale price monitoring, back-testing, independent review. |
| `04_business_continuity_plan.md` | 1,700 to 2,400 | Plan owner, alternate site, recovery objectives, critical vendors, data backup (frequency, location), testing (frequency, last test date), communication tree, pandemic and cyber incident response. |
| `05_fee_schedule.md` | 600 to 1,000 | Fee tables, breakpoints, billing frequency and basis, minimums, termination and refunds. |
| `06_policy_update_memo.md` | 700 to 1,200 | A dated internal memorandum from the CCO, later than every other document, that amends 5 or 6 specific provisions of the other documents (a changed threshold, frequency, approver, vendor, deadline, or fee breakpoint). It must say which document and section each change amends and that the change supersedes it. The original documents are NOT edited: they still carry the old values. |

Headings: `## Item 12. Brokerage Practices` then `### 12.1 ...`, or `## SECTION 6. PERSONAL
TRADING` then `### 6.3 ...`, consistently within each document. Every document starts with a
`#` title, the firm name, a version date, and the banner.

## The DDQ key: `keys/t3/<firm_id>.json`

Exactly 40 questions, phrased the way an institutional allocator's DDQ phrases them
("Describe...", "Who approves...", "How frequently..."). Mix:

- 25 **answerable** questions spread across all six documents; at least 4 require combining
  facts from two sections; at least 6 hinge on a specific number, date or named party.
- 5 **supersession** questions whose correct answer comes from the policy update memo; the
  original document still states the old value. Put the old value in a `STALE_...` reject.
- 5 **clean unanswerable** questions: standard DDQ topics the pack never addresses (for
  example D&O insurance limits, key-person life insurance, succession plan, AUM by
  client type if not given, staff turnover). Make sure the pack truly never addresses them.
- 5 **near-miss unanswerable** questions: the pack addresses the topic but not the asked
  detail (the pack says the firm carries cyber insurance but never states the limit; it
  names the fund administrator but never says when it was appointed). These tempt
  fabrication. Put the most likely fabricated answer shape in a `HALLUCINATED_...` reject
  if there is one.

Shuffle the order so types are interleaved.

```json
{
  "firm_id": "t3_f02",
  "firm_name": "...",
  "firm_type": "...",
  "documents": ["01_brochure.md", "02_compliance_manual.md", "..."],
  "questions": [
    {
      "qid": "q01",
      "question": "...",
      "answerable": true,
      "trap": "none | multi_part | supersession | unanswerable_clean | near_miss",
      "expected": "concise correct answer, or NOT_IN_DOCUMENTS",
      "accept": ["regex"],
      "partial": ["regex (optional)"],
      "reject": {"STALE_x": ["regex"], "HALLUCINATED_x": ["regex"]},
      "source_document": "06_policy_update_memo.md",
      "section": "Section 3",
      "quote": "verbatim supporting text (empty for unanswerable)",
      "also_needs": [{"source_document": "...", "section": "...", "quote": "..."}]
    }
  ]
}
```

For unanswerable questions `accept` must be `["NOT_IN_DOCUMENTS|not\\s+(stated|specified|addressed|provided|disclosed|included)|does\\s+not\\s+(state|specify|address)|no\\s+information"]`
or tighter. For answerable questions accept patterns must key on the decisive fact (the
number, the named party, the frequency), not on wording.

## Firms

**t3_f01 (dev).** Independent wealth manager RIA, about $2 billion in separately managed
accounts for high-net-worth households, 3 locations.
**t3_f02 (test).** Hedge fund manager RIA advising three private funds (a flagship
long/short equity fund, an offshore feeder, and a co-investment vehicle).
**t3_f03 (test).** Multi-family office RIA serving about 60 families, with an in-house
trust company affiliate and outsourced custody.
**t3_f04 (test).** Institutional fixed income manager: separately managed accounts for
public pension and insurance clients plus one commingled fund.
