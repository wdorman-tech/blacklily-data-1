"""Grade an extraction run against the ground-truth answer keys.

Scores any run directory the same way, so the Claude baseline and the local
model are measured by one yardstick. Reports five things the one-pager cares
about:

  field accuracy      - did it get the term right
  hallucination rate  - did it invent a term that is not in the document
  supersession        - did it use the amended value, not the superseded one
  citation validity   - does the cited section actually exist
  quote grounding     - is the supporting quote verbatim from the document
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
TRUTH = ROOT / "ground_truth"


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    # Note: underscores are preserved: NOT_FOUND / NOT_APPLICABLE are sentinels.
    text = re.sub(r"[*`>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def matches_any(patterns: list[str], value: str) -> str | None:
    for pat in patterns:
        if re.search(pat, value, re.IGNORECASE | re.DOTALL):
            return pat
    return None


@dataclass
class FieldResult:
    name: str
    score: float
    verdict: str
    got: str
    expected: str
    error_kind: str | None = None
    citation_valid: bool | None = None
    quote_grounded: bool | None = None


@dataclass
class DocResult:
    doc_id: str
    difficulty: str
    fields: list[FieldResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return sum(f.score for f in self.fields) / len(self.fields) if self.fields else 0.0


def section_ids(text: str) -> set[str]:
    """Pull section identifiers out of a heading line or a citation string.

    Handles the four shapes these documents use: supplement sections (S-2),
    appendices (Appendix A), articles (Article VI) and numbered sections
    (Section 4 / 4.1). "Supplement No. 1" is stripped first; it names a
    document part, not a section.
    """
    t = re.sub(r"supplement\s+no\.?\s*\d+", " ", text.lower())
    out: set[str] = set()
    out.update(re.findall(r"\bs-\d+\b", t))
    out.update(f"appendix {m}" for m in re.findall(r"\bappendix\s+([a-d])\b", t))
    out.update(f"article {m}" for m in re.findall(r"\barticle\s+([ivxlc]+)\b", t))
    out.update(re.findall(r"\b\d+\.\d+(?:\.\d+)*\b", t))
    out.update(re.findall(r"\bsection\s+(\d+)\b", t))
    return out


def build_heading_index(doc_raw: str) -> set[str]:
    index: set[str] = set()
    for line in doc_raw.splitlines():
        if not line.lstrip().startswith("#"):
            continue
        heading = line.lstrip("#").strip()
        index |= section_ids(heading)
        # "### 1.1 The Partnership" and "### Section S-2." both need the bare
        # leading identifier picked up.
        if m := re.match(r"^(?:section\s+)?(s-\d+|\d+(?:\.\d+)*)\b", heading, re.I):
            tok = m.group(1).lower()
            index.add(tok)
            index.add(tok.split(".")[0])
    return index


def citation_is_valid(citation: str, index: set[str]) -> bool | None:
    """True if every section identifier in the citation exists in the document."""
    if not citation.strip():
        return None
    tokens = section_ids(citation)
    if not tokens:
        return False
    return all(tok in index for tok in tokens)


def quote_is_grounded(quote: str, doc_norm: str) -> bool | None:
    q = normalize(quote)
    if len(q) < 15:
        return None
    if q in doc_norm:
        return True
    # tolerate elision and truncation: require a long contiguous run to match
    words = q.split()
    for size in (14, 10, 8):
        if len(words) < size:
            continue
        for i in range(0, len(words) - size + 1):
            if " ".join(words[i : i + size]) in doc_norm:
                return True
    return False


def grade_doc(truth_path: Path, run_dir: Path) -> DocResult | None:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    doc_id = truth["doc_id"]
    pred_path = run_dir / f"{doc_id}.json"
    if not pred_path.exists():
        return None

    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    doc_raw = (CORPUS / f"{doc_id}.md").read_text(encoding="utf-8")
    doc_norm = normalize(doc_raw)
    heading_index = build_heading_index(doc_raw)
    result = DocResult(doc_id=doc_id, difficulty=truth.get("difficulty", "?"))

    for name, spec in truth["fields"].items():
        entry = pred.get(name) or {}
        got = str(entry.get("value", "") or "").strip()
        got_norm = normalize(got)

        if not got_norm:
            result.fields.append(
                FieldResult(name, 0.0, "MISSING", got, spec["expected"], "no_value")
            )
            continue

        score, verdict, error_kind = 0.0, "WRONG", None

        if matches_any(spec.get("accept", []), got_norm):
            score, verdict = 1.0, "CORRECT"
        elif matches_any(spec.get("partial", []), got_norm):
            score, verdict, error_kind = 0.5, "PARTIAL", "incomplete"

        if verdict != "CORRECT":
            for kind, pats in (spec.get("reject") or {}).items():
                if matches_any(pats, got_norm):
                    error_kind = kind
                    if verdict == "WRONG":
                        verdict = (
                            "HALLUCINATION"
                            if kind.startswith("HALLUCINATED")
                            else "STALE"
                            if kind.startswith("STALE")
                            else "WRONG"
                        )
                    break

        # A hallucination on an absence field is the worst failure mode: the
        # model produced a term that is not in the document at all.
        if spec.get("absence_test") and verdict in {"WRONG", "PARTIAL"}:
            verdict, score = "HALLUCINATION", 0.0

        result.fields.append(
            FieldResult(
                name,
                score,
                verdict,
                got,
                spec["expected"],
                error_kind,
                citation_is_valid(str(entry.get("citation", "")), heading_index),
                quote_is_grounded(str(entry.get("quote", "")), doc_norm),
            )
        )

    return result


def summarize(results: list[DocResult], truths: dict[str, dict]) -> dict:
    all_fields = [f for r in results for f in r.fields]
    n = len(all_fields) or 1

    absence, supersession = [], []
    for r in results:
        spec_fields = truths[r.doc_id]["fields"]
        for f in r.fields:
            if spec_fields[f.name].get("absence_test"):
                absence.append(f)
            if spec_fields[f.name].get("supersession_test"):
                supersession.append(f)

    cites = [f.citation_valid for f in all_fields if f.citation_valid is not None]
    quotes = [f.quote_grounded for f in all_fields if f.quote_grounded is not None]

    def pct(part: list, whole: list) -> float:
        return round(100 * len(part) / len(whole), 1) if whole else 0.0

    return {
        "fields_graded": len(all_fields),
        "field_accuracy_pct": round(100 * sum(f.score for f in all_fields) / n, 1),
        "exact_correct": sum(1 for f in all_fields if f.verdict == "CORRECT"),
        "partial": sum(1 for f in all_fields if f.verdict == "PARTIAL"),
        "wrong": sum(1 for f in all_fields if f.verdict == "WRONG"),
        "missing": sum(1 for f in all_fields if f.verdict == "MISSING"),
        "hallucinations": sum(1 for f in all_fields if f.verdict == "HALLUCINATION"),
        "hallucination_rate_pct": round(
            100 * sum(1 for f in all_fields if f.verdict == "HALLUCINATION") / n, 1
        ),
        "absence_fields": len(absence),
        "absence_correct_pct": pct([f for f in absence if f.verdict == "CORRECT"], absence),
        "supersession_fields": len(supersession),
        "supersession_correct_pct": pct(
            [f for f in supersession if f.verdict == "CORRECT"], supersession
        ),
        "stale_answers": sum(1 for f in all_fields if f.verdict == "STALE"),
        "citation_validity_pct": pct([c for c in cites if c], cites),
        "quote_grounding_pct": pct([q for q in quotes if q], quotes),
        "per_doc": {
            r.doc_id: {
                "difficulty": r.difficulty,
                "accuracy_pct": round(100 * r.accuracy, 1),
            }
            for r in results
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--label", default=None)
    ap.add_argument("--verbose", action="store_true", help="print every failed field")
    args = ap.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    label = args.label or run_dir.name

    truths, results = {}, []
    for tp in sorted(TRUTH.glob("*.json")):
        truth = json.loads(tp.read_text(encoding="utf-8"))
        truths[truth["doc_id"]] = truth
        if (r := grade_doc(tp, run_dir)) is not None:
            results.append(r)

    if not results:
        raise SystemExit(f"no predictions found in {run_dir}")

    summary = summarize(results, truths)
    summary["label"] = label
    (run_dir / "_score.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n=== {label} ===")
    print(f"  field accuracy        {summary['field_accuracy_pct']:>6}%  "
          f"({summary['exact_correct']} exact, {summary['partial']} partial "
          f"of {summary['fields_graded']})")
    print(f"  hallucination rate    {summary['hallucination_rate_pct']:>6}%  "
          f"({summary['hallucinations']} fields)")
    print(f"  absence handled       {summary['absence_correct_pct']:>6}%  "
          f"({summary['absence_fields']} fields that are not in the doc)")
    print(f"  supersession handled  {summary['supersession_correct_pct']:>6}%  "
          f"({summary['supersession_fields']} amended fields, "
          f"{summary['stale_answers']} stale)")
    print(f"  citation validity     {summary['citation_validity_pct']:>6}%")
    print(f"  quote grounding       {summary['quote_grounding_pct']:>6}%")
    print("  per document:")
    for doc_id, d in summary["per_doc"].items():
        print(f"    {doc_id:<26} {d['accuracy_pct']:>6}%  ({d['difficulty']})")

    if args.verbose:
        print("\n  failures:")
        for r in results:
            for f in r.fields:
                if f.verdict not in {"CORRECT"}:
                    print(f"    [{f.verdict}] {r.doc_id}.{f.name}"
                          f"{' <' + f.error_kind + '>' if f.error_kind else ''}")
                    print(f"        got:      {f.got[:150]}")
                    print(f"        expected: {f.expected[:150]}")


if __name__ == "__main__":
    main()
