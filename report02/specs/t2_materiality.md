# T2 real pairs: materiality labeling

Each pair is an excerpt of Item 1A (Risk Factors) from two consecutive Form 10-K filings of
one issuer, already aligned section by section by code: every risk factor (headline plus
body) is classified unchanged, modified, added, removed or moved. Added and removed risk
factors are material by definition. Your job is to label every **modified** section
material or not.

## Definition (pre-registered, apply it literally)

A modification is **material** if an analyst reviewing year-over-year risk disclosure would
need to know about it. Any one of these makes it material:

1. A new risk, exposure, dependency or mitigating fact is disclosed, or a previously
   disclosed one is removed.
2. A new specific event, development, proceeding, regulation, jurisdiction, product,
   business, counterparty or named program is referenced, or one is dropped.
3. The characterization of likelihood or severity changes: hypothetical to realized ("could"
   to "has"), a risk escalated or softened, "material" added or removed, scope widened or
   narrowed.
4. A quantitative change other than a routine date roll-forward: a dollar amount, a
   percentage, a share of revenue, a count, a rating.

A modification is **minor** only if every change in it is of these kinds: fiscal-year
roll-forward ("fiscal 2024" to "fiscal 2025") with nothing else, a renamed defined term or
segment name with no change in substance, a cross-reference update, punctuation, or
stylistic rewording with identical meaning.

When a section contains both kinds, it is material.

## Output

For every modified section write one label with `aid`, `material` (true/false), a
one-sentence `description` of the most important change (with old and new values when
there are numbers), and a one-sentence `rationale` naming which numbered criterion applies
(or why it is minor). For added and removed sections write only the one-sentence
`description` of what the risk factor covers.
