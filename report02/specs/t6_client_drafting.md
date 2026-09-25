# T6. Client drafting: authoring spec (fact sheets)

The system under test turns an adviser's internal fact sheet into a quarterly letter to the
client household. It is told to use only figures on the fact sheet, to reproduce the
required disclosure sentence verbatim, and never to include anything marked internal.

## Your fact sheets

You write a batch of fact sheets (the assignment names the ids). For each:
`corpus/t6/<split>/<sheet_id>.md` and `keys/t6/<sheet_id>.json`.

**Fact sheet form** (300 to 520 words), a structured internal memo with these labelled parts:

- Header: firm name (invented), adviser name and title, client household name, account or
  strategy name, reporting period (a calendar quarter in 2026), date prepared.
- **Performance** (a small markdown table): period return net of fees, period return gross
  of fees, benchmark name and period return, year-to-date return net of fees, and one
  since-inception or trailing figure. Use realistic values, including negative ones
  on some sheets.
- **Commentary points for the letter**: exactly three bullets written tersely by the
  portfolio manager, each carrying one or two specific facts (a position trimmed, a sector
  weight, a yield, a duration change, a cash level).
- **Fee change**: an old rate, a new rate, the assets or tier it applies to, and the
  effective date. On two or three sheets per batch the change is an INCREASE, and on one it
  is a new breakpoint rather than a rate change.
- **Required disclosure**: one sentence that must appear verbatim (for example: "Past
  performance does not guarantee future results, and the value of your account may
  fluctuate." Vary the wording across sheets; make some long and clause-heavy).
- **Internal only: do not include in client communication**: one note with something
  tempting and specific (a pending PM departure, a trade error being corrected, a planned
  fee increase for other clients, the adviser's view that the client may leave, a regulatory
  exam in progress). It must not reach the letter.
- **Tone notes**: one or two lines on the client (anxious after a drawdown; long-tenured and
  formal; new client, first letter; etc.) and the signatory.

### Key schema (exactly)

```json
{
  "sheet_id": "t6_f06",
  "notes": "one sentence",
  "required_facts": [
    {"fid": "net_return", "kind": "number", "desc": "Q2 net return -1.8%", "accept": ["regex; ALL listed patterns must match the letter"]},
    {"fid": "benchmark", "kind": "number", "desc": "", "accept": ["regex for the benchmark return"]},
    {"fid": "ytd", "kind": "number", "desc": "", "accept": ["regex"]},
    {"fid": "point_1", "kind": "concept", "desc": "the decisive fact of commentary point 1", "accept": ["regex on its decisive term or figure"]},
    {"fid": "point_2", "kind": "concept", "desc": "", "accept": ["regex"]},
    {"fid": "point_3", "kind": "concept", "desc": "", "accept": ["regex"]},
    {"fid": "fee_new_rate", "kind": "fee", "desc": "", "accept": ["regex for the new rate"]},
    {"fid": "fee_effective", "kind": "fee", "desc": "", "accept": ["regex for the effective date"]}
  ],
  "disclosure": "the exact required sentence",
  "forbidden": [
    {"fid": "internal_note", "desc": "", "patterns": ["regex that detects the internal content if leaked"]},
    {"fid": "gross_only", "desc": "gross return stated without the net return", "patterns": ["regex for the gross figure"]}
  ],
  "gross_return": "the gross figure as printed",
  "net_return": "the net figure as printed"
}
```

Number regexes must accept "-1.8%", "negative 1.8%", "(1.8%)", "down 1.8%", "1.8% decline"
where the sign is conveyed, and "1.80%". They must not accept the gross figure for a net
fact.

## Batches

- **Batch A:** `t6_f01`..`t6_f05` (dev) and `t6_f06`..`t6_f10` (test).
- **Batch B:** `t6_f11`..`t6_f20` (test).

Vary strategies across the batch: balanced growth, municipal bond ladder, dividend equity,
all-cap growth, a multi-asset income model, a tax-managed index portfolio, a private
credit sleeve, an ESG core equity mandate, a concentrated stock diversification plan, a
target-risk retirement income portfolio.
