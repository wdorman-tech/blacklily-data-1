# T1. Fund term extraction: authoring spec

The system under test reads one private fund offering document (PPM, offering memorandum
or LPA) and extracts the 20 fields below, each as `{value, citation, quote}`. The field
list, prompt and rules are fixed (from Report No. 01) and are reproduced here so you know
what the document must support. `NOT_FOUND` = the document does not state the term.
`NOT_APPLICABLE` = the document states the term does not exist or does not apply.

| field | meaning |
|---|---|
| fund_name | Full legal name of the fund entity being offered |
| fund_domicile | Jurisdiction of organization of the offered entity |
| fund_structure | Open-end (redeemable) or closed-end (drawdown), and whether master-feeder |
| management_fee | Annual rate AND basis; every class or tier |
| performance_fee | Incentive allocation / carried interest rate; every class |
| hurdle_rate | Preferred return / hurdle / benchmark; type (hard/soft, catch-up) if given |
| high_water_mark | Whether a HWM or loss carryforward applies; perpetual or resets |
| minimum_initial_investment | Minimum INITIAL subscription or commitment |
| lockup_period | Hard vs soft lock; every class |
| redemption_frequency | How often interests may be redeemed |
| redemption_notice_days | Advance written notice to redeem |
| gate_provision | Level (fund / investor) and threshold |
| key_man_provision | Who is named and what it triggers |
| gp_commitment | Required GP / sponsor commitment. A disclosed current holding is NOT a commitment |
| fund_term | Term incl. extensions, or perpetual |
| auditor | Independent auditor CURRENTLY appointed |
| administrator | Fund administrator |
| prime_broker | Prime broker(s) |
| legal_counsel | Law firm(s) acting as counsel to the fund |
| mfn_election | Whether an MFN election on side letters is offered, and its scope |

## Your document

Your assignment names one document design below. Write:

1. `corpus/t1/<split>/<doc_id>.md`: the document.
2. `keys/t1/<doc_id>.json`: the key.

### Key schema (exactly)

```json
{
  "doc_id": "t1_d05",
  "doc_title": "Plain title, no dashes of any kind",
  "doc_type": "PPM | Offering Memorandum | LPA | ...",
  "difficulty": "baseline | structural | adversarial",
  "notes": "2 to 4 sentences: what makes this document hard, for the paper's methods table",
  "traps": { "<field>": "one sentence describing the trap and the correct reading" },
  "fields": {
    "<field>": {
      "expected": "the correct value as an analyst would write it",
      "citation": "Section 4.1",
      "quote": "short verbatim quote from the document that proves it",
      "accept": ["regex", "..."],
      "partial": ["regex for an incomplete but not wrong answer (optional)"],
      "reject": { "STALE_<what>": ["regex"], "HALLUCINATED_<what>": ["regex"], "<other_error>": ["regex"] },
      "absence_test": true,
      "supersession_test": true,
      "trap_type": "absence | supersession | side_letter | table_only | late_position | precedence | layered_fee | holding_not_commitment | class_variants | none"
    }
  }
}
```

- All 20 fields must be present in `fields`.
- `absence_test: true` on any field whose correct answer is NOT_FOUND or NOT_APPLICABLE.
  For those, `accept` must accept the sentinel AND natural phrasings ("none", "no gate",
  "not applicable", "does not impose", "not stated"). The grader treats any substantive
  value on an absence field as a hallucination.
- `supersession_test: true` on any field whose body value is replaced by a later amendment,
  supplement or "recent changes" section. Put the superseded value in a `STALE_...` reject
  pattern guarded by a negative lookahead for the current value.
- Reject keys starting `HALLUCINATED` mark fabrications; `STALE` marks superseded values.
- Where the document is silent on a term that does not fit the fund type (prime broker in
  a buyout fund), prefer to make the document explicit ("The Fund does not engage a prime
  broker") so NOT_APPLICABLE is defensible, and accept NOT_FOUND as well in that case.
- Include at least 3 absence fields and at least 2 trap fields of the document's design
  type. At least 6 of 20 fields should be genuinely hard (trap_type != none).

## Document designs

Word counts are whitespace-split words of the whole file.

**t1_d04 (dev). Open-end long/short equity hedge fund PPM with an executed side letter
appended.** 4,000 to 5,000 words. Delaware LP, two classes. The final appendix reproduces
an executed side letter with one named pension plan investor that reduces THAT investor's
management fee, shortens THAT investor's notice period and waives its lock-up. The PPM
separately offers an MFN election to investors above a stated commitment size. Correct
fund-level answers come from the PPM body, never from the side letter. Put the side-letter
values in reject patterns (`SIDE_LETTER_...`). trap_type side_letter on the affected fields.

**t1_d05 (test). Multi-strategy hedge fund PPM whose economics appear only in tables.**
3,800 to 5,000 words. Three classes (A, B, Founders). Management fee, incentive
allocation, lock-up, notice and gate appear ONLY inside markdown tables (a "Summary of
Principal Terms" table and a "Class Terms" table); the prose says "as set forth in the table
in Section 2.3" and never restates the numbers. Founders Class has lower economics and a
longer lock. The correct management_fee and performance_fee list every class.
trap_type table_only / class_variants.

**t1_d06 (test). Buyout fund LPA with a First Amendment.** 4,500 to 6,000 words. Delaware
LP, closed-end, 10-year term with extensions, 5-year investment period, management fee on
commitments during the investment period then on invested capital, 20% carry over an 8%
preferred return with full catch-up, two named key persons, GP commitment as a percent of
commitments. The First Amendment at the end (dated about 14 months after the LPA) changes
the post-investment-period fee rate and basis, replaces one departed key person with a
newly named one, and changes the number of permitted one-year extensions (and who must
consent). Limited partners have no redemption right, stated expressly. No prime broker,
stated expressly. trap_type supersession on three fields, absence on the redemption group.

**t1_d07 (test). Semi-liquid private credit fund PPM with an executed side letter.** 4,500
to 5,500 words. Evergreen Delaware LP with quarterly tender-style redemptions, a 5% of NAV
fund-level quarterly gate, an incentive fee on pre-incentive-fee net investment income over
a quarterly hurdle with catch-up, plus a capital gains incentive fee. The appended side
letter with a named endowment reduces that investor's management fee, waives its early
redemption charge and grants it key-person notification rights. Fund-level answers come
from the PPM. The PPM also says a loss carryforward applies to the capital gains fee only
(high_water_mark must say so). trap_type side_letter on 2+ fields.

**t1_d08 (test). Closed-end value-add real estate fund PPM with a late auditor change.**
4,000 to 5,500 words. 9% IRR-based preferred return (hard hurdle), 50/50 catch-up, 20%
carry; fee on commitments during the investment period then on invested equity; sponsor
commitment "the greater of $X or Y% of commitments"; 8-year term plus two one-year
extensions. A "Recent Developments" section near the end states that the fund replaced its
auditor effective a date after the body was written; the service-provider section and a
directory page still name the former auditor. MFN offered to investors above a threshold.
No prime broker mentioned anywhere (NOT_FOUND). trap_type supersession (auditor),
absence (prime broker, redemption fields as NOT_APPLICABLE with an express statement).

**t1_d09 (test). Open-end fund of hedge funds offering memorandum.** 4,000 to 5,000
words. The fund's OWN fees (a management fee and an incentive fee over a stated hurdle)
sit next to a paragraph describing the fees UNDERLYING managers typically charge (higher
numbers). Monthly subscriptions, quarterly redemptions, a notice period in days, an
investor-level gate, a one-year soft lock with an early redemption fee. The document states
the fund does not engage a prime broker. No key person clause (NOT_FOUND). The adviser's
disclosed current investment in the fund is expressly not a commitment. trap_type
layered_fee (management_fee, performance_fee), holding_not_commitment, absence.

**t1_d10 (test). Early-stage venture capital fund LPA.** 4,000 to 5,500 words. Management
fee on commitments for years 1 to 5 then stepping down by a fixed amount each year to a
floor; carried interest that steps up from 20% to 25% once distributions exceed a stated
multiple of paid-in capital; the LPA states expressly that there is no preferred return;
GP commitment as a percent; 10-year term plus up to three one-year extensions; two named
key persons with an investment-period suspension; MFN for LPs above a threshold. No
redemptions (express). trap_type class_variants on performance_fee (tiered), absence on
hurdle and redemption group.

**t1_d11 (test). Global macro master-feeder PPM near the context limit.** 8,300 to 8,900
words (this is a hard ceiling: the study needs this document to fit a 16K-token window
together with the prompt and the answer). Delaware feeder into a Cayman master. Heavy
risk-factor, tax, ERISA and regulatory sections in the middle. The LAST section,
"Section 14. Summary of Changes Effective [date]", changes the redemption notice period,
introduces a fund-level gate that the body said did not exist, and names a new auditor.
Nothing earlier in the document points to Section 14. trap_type late_position (and
supersession) on those three fields.

**t1_d12 (test). Cayman commodities fund offering memorandum with two supplements.**
3,800 to 5,000 words. Cayman exempted company, two share classes. Supplement No. 1
(earlier date) changes the management fee and the redemption notice. Supplement No. 2
(later date) changes the management fee again for one class only and says nothing about
notice. The correct answers are body -> S1 -> S2 reconciled: the fee is the S2 value for
that class and the S1 value for the other; the notice is the S1 value. The fund expressly
imposes no gate. No key person clause and no manager commitment (NOT_FOUND). Use
`### Section S-1.`-style headings inside each supplement, with supplement sections
numbered distinctly (S-1..S-4 in Supplement No. 1, S-5..S-8 in Supplement No. 2).
trap_type supersession (double), absence.

**t1_d13 (test). Infrastructure secondaries fund: term sheet table plus LPA, with a
precedence clause.** 4,500 to 6,000 words. Opens with a "Summary of Principal Terms" table;
the LPA body follows. The document states that in any conflict the LPA controls. For two
terms (GP commitment and the number of term extensions) the table and the LPA body
disagree; the LPA body value is correct. Closed-end, 12-year term. trap_type precedence on
those two fields; absence on the redemption group and prime broker.
