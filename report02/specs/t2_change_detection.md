# T2. Change detection: authoring spec (synthetic pairs)

The system under test receives two versions of one document, labelled PRIOR VERSION and
CURRENT VERSION, and lists every **material** change: provisions added, provisions
removed, and provisions whose substance was modified. For each change it gives the type,
the location (the section heading), a one-sentence description and a verbatim quote.

Grading is at the level of a **section** (one `###` heading and its body). A reported
change is located by its quote and heading. A report that points at a section whose text
is identical in both versions is an invented change. So the key must be exact about which
sections changed and which did not.

## Your pair

Write `corpus/t2/<split>/<pair_id>/prior.md`, `corpus/t2/<split>/<pair_id>/current.md`
and `keys/t2/<pair_id>.json`.

- Each version: 2,700 to 3,400 words, 18 to 26 `###` sections, each with a numbered
  heading (`### 4.2 Management Fee`). Write the PRIOR version first, in full, then produce
  the CURRENT version by editing a copy of it.
- **Exactly one kind of edit per section.** Never put a material change and a minor edit in
  the same section; never put two material changes in one section. Sections you do not
  deliberately change must be byte-identical between versions (same heading, same text).
- Planted edits:
  - 9 to 12 **material** changes: 2 or 3 sections ADDED (new heading, new provision), 1 or 2
    sections REMOVED, 5 to 7 sections MODIFIED in substance (a changed rate, threshold,
    period, party, right, obligation, consent requirement, or a sentence that adds or
    removes an exposure). Make some modifications subtle: one number inside a long
    paragraph; "may" becoming "shall"; a consent right moving from the LPAC to the GP; a
    carve-out added to an exclusion.
  - 5 to 8 **minor** edits, each in its own section: a date rolled forward in a boilerplate
    line, a defined term renamed consistently, a cross-reference renumbered, a typo fixed,
    a sentence reworded with identical meaning. These are real text changes that are not
    material.
  - 1 **moved** section: identical text relocated to a different position, keeping its
    heading text but not its number (renumber it). The grader aligns by heading text, so a
    report of "added" or "removed" for it is an invented change.
- Heading text of a MODIFIED or MINOR section stays identical across versions except for
  its number. Heading text of an ADDED section must not resemble any prior heading.
- The document header of the CURRENT version carries the new version date and title (for
  an LPA: "Amended and Restated Limited Partnership Agreement").

### Key schema (exactly)

```json
{
  "pair_id": "t2_s02",
  "doc_title": "Plain title, no dashes",
  "doc_type": "LPA | Compliance Manual",
  "notes": "2 to 3 sentences on what makes the pair hard",
  "changes": [
    {
      "cid": "c01",
      "type": "added | removed | modified | minor | moved",
      "material": true,
      "prior_heading": "4.2 Management Fee",
      "current_heading": "4.2 Management Fee",
      "description": "One sentence: what changed, with old and new values",
      "prior_quote": "verbatim text from prior (empty for added)",
      "current_quote": "verbatim text from current (empty for removed)",
      "subtle": false
    }
  ]
}
```

`material` is true for added, removed and modified; false for minor and moved. List every
section you touched, and nothing else.

## Pair designs

**t2_s01 (dev). Buyout fund LPA, original vs Amended and Restated.**
**t2_s02 (test). Private credit fund LPA, original vs Amended and Restated.** Include a
changed recycling provision, a new excuse right for a class of LPs, and an added ESG
reporting obligation.
**t2_s03 (test). RIA compliance manual v1 vs v2** (a wealth manager). Include a changed
personal-trading pre-clearance threshold, a removed gift-reporting exception, a new
off-channel communications policy, and a changed code-of-ethics reporting deadline.
**t2_s04 (test). Hedge fund manager compliance manual v1 vs v2.** Include a changed
restricted-list procedure, a new expert-network policy section, a removed exemption for
de minimis trades, and a changed valuation-override approval chain.
