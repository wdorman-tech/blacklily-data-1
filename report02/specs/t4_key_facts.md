# T4. Filing brief: key-fact list for a real earnings release

The system under test turns one earnings release (Form 8-K, Exhibit 99.1) into a one-page
investment committee brief of 350 to 450 words, using only figures stated in the
release. Your key lists the facts the brief must carry. It is graded by an adjudicator who
checks, fact by fact, whether the brief states each one correctly.

## The list

Exactly 10 facts, the ones a portfolio manager would be annoyed to find missing from a
one-page brief on this release. Pick them the way a buy-side analyst would:

- 6 **core** facts: headline revenue and its change; the headline earnings measure (GAAP
  EPS or net income; plus the adjusted measure if the company leads with it, labeled as
  such); the most important segment or business-line result; margin or profitability
  change; guidance or outlook (only if the release gives it; if it does not, choose
  another core fact and never invent guidance); one more fact the release itself treats as
  the headline story.
- 4 **supporting** facts: capital return (buybacks, dividends), balance sheet or cash flow,
  a notable one-time item or charge, a segment or geography that moved against the trend,
  a key operating metric (users, deposits, backlog, units).

Each fact is a single claim with at most two figures. Figures must be copied exactly as
printed (including units and "billion" vs "million"). Mark GAAP vs non-GAAP explicitly
wherever the release distinguishes them: a brief that reports an adjusted figure as if it
were GAAP gets that fact wrong.

## Schema: `keys/t4/<doc_id>.json`

```json
{
  "doc_id": "t4_msft",
  "issuer": "Microsoft Corporation",
  "period": "quarter ended June 30, 2026",
  "facts": [
    {
      "fid": "f01",
      "importance": "core",
      "fact": "Revenue was $90.0 billion, up 18% year over year.",
      "figures": ["$90.0 billion", "18%"],
      "basis": "GAAP | non-GAAP | operating metric | n/a",
      "quote": "verbatim sentence or table row from the release",
      "location": "first bullet under the headline | segment table row | outlook paragraph",
      "equivalent_phrasings": ["$90 billion", "up 18%"],
      "common_errors": ["confusing with constant-currency growth of 17%"]
    }
  ],
  "no_guidance": false,
  "traps": ["one line each: the easiest ways to misstate this release (GAAP vs adjusted, constant currency, quarter vs year to date, segment vs total)"]
}
```

No U+2014 or U+2013 characters in anything you write (copy figures, not dashes; if a quote
contains a dash, keep the quote as printed and nothing else).
