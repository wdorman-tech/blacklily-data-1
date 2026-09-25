# Authoring rules for every synthetic document in Report No. 02

You are the **Author** in a three-role evaluation (Author, Subject, Grader). You write
documents and the answer keys that grade them. The systems under test will never see the
key, your notes, or this file. Write documents a practitioner would find credible on first
read: a general counsel, a CCO, a fund administrator or an operations analyst should not
be able to tell they are synthetic except for the banner.

## Hard rules

1. **Banner.** Every synthetic document opens (after its title block) with this blockquote,
   with the invented entity names filled in:

   > **SYNTHETIC DOCUMENT: FOR BENCHMARK USE ONLY.** This document is fictional. [Entity
   > names] and all persons, service providers and figures named herein are invented for
   > the purpose of evaluating document-processing systems. It is not an offer to sell
   > securities and does not describe any real entity.

   The banner is the only place the words "benchmark", "synthetic" or "fictional" may appear.
   Never write "test", "trap", "planted" or anything that signals the evaluation in the
   document body.
2. **No em dashes and no en dashes**, anywhere, including titles and keys. Use a colon,
   a comma, parentheses, or a plain hyphen. The character U+2014 and U+2013 must not appear
   in any file you write. This is checked by script.
3. **Invented names only.** Funds, advisers, service providers (auditors, administrators,
   prime brokers, law firms, custodians), people and clients are all invented. Do not use
   the name of any real firm, fund, bank, law firm, audit firm or famous person, and avoid
   names that are one word away from one (no "Goldmann", no "Deloite"). Prefer two
   uncommon surnames or a place-plus-noun construction ("Hallowmere Partners", "Tarrow
   Kessel LLP"). Names are checked against SEC EDGAR and the IAPD adviser database after
   you finish; a collision means a rewrite.
4. **Locations.** Invented firms may sit in real places.
5. **Figures must be internally consistent** across the whole document (and across a
   document set). If a fee appears twice, it matches, unless the inconsistency is a
   deliberate part of the design written into the key.
6. **Register.** Real documents of this type are dense, precise and repetitive in a legal
   way. Match that. No marketing gloss inside legal documents. No filler paragraphs that
   exist only to add length: length comes from the provisions a real document would carry
   (risk factors, definitions, tax, ERISA, transfer restrictions, conflicts, etc.).
7. **Markdown structure.** Use `#`, `##`, `###` headings. Section identifiers must appear in
   headings in one of these shapes so citations can be validated: `SECTION 4. FEES` with
   subsections `### 4.1 Management Fee`; `ARTICLE VI` with `### 6.2 ...`; `APPENDIX A`;
   supplement sections `### Section S-2. ...`. Every section a key cites must exist as a
   heading.
8. **Plain ASCII punctuation is safest.** Curly quotes are fine; dashes are not.

## Answer keys

Keys are JSON, UTF-8, written exactly in the schema the task spec gives. Every pattern is a
Python regular expression applied case-insensitively (re.IGNORECASE | re.DOTALL) to the
system's answer after lower-casing and whitespace collapsing. Rules for patterns:

- An **accept** pattern must match every correct phrasing a competent analyst would write,
  including numerals vs words ("12 months", "twelve months", "one year" where equivalent),
  "%" vs "percent", "$2,000,000" vs "$2 million" vs "$2mm" vs "USD 2,000,000".
- A **reject** pattern names a specific, predictable wrong answer (the superseded value,
  the side-letter value, a fabricated number) and must NOT match any correct answer.
  Use negative lookaheads, as in `^(?!.*1\.60).*2\.00`, so an answer that mentions the old
  value while clearly giving the new one is not rejected.
- Keys are self-tested by script: each `expected` string must match its own accept list and
  must not match any reject pattern. Write patterns that pass that.
- Every key item records where in the document the answer lives (section heading id) and a
  short verbatim quote. The independent Verifier checks every item against the document.

## Word counts

Stay inside the word range the task spec gives for each document. Word counts are checked
by script (whitespace split). Too short means the document is not realistic; too long can
break the context budget the study depends on.
