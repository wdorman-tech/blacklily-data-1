"""Turn fetched 10-K Item 1A text into category-level prior/current pairs for T2."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t2_blocks import Section, align, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources" / "edgar" / "10k"
SKIP_CATEGORY = re.compile(r"forward.looking|cautionary", re.I)


def is_category(b: dict) -> bool:
    t = b["text"]
    words = len(t.split())
    if not (b["bold"] or b["italic"]):
        return False
    return words <= 12 and not t.rstrip().endswith(".") or (t.isupper() and words <= 14)


def is_headline(b: dict) -> bool:
    return (b["bold"] or b["italic"]) and len(b["text"].split()) >= 6 and not is_category(b)


def to_sections(blocks: list[dict]) -> list[Section]:
    sections: list[Section] = []
    category = "General"
    cur: Section | None = None
    for b in blocks:
        if b["kind"] == "row":
            continue
        if is_category(b):
            category = b["text"].rstrip(":").strip()
            cur = None
            continue
        if is_headline(b):
            cur = Section("", b["text"], "", category)
            sections.append(cur)
            continue
        if cur is not None:
            cur.body = (cur.body + "\n\n" + b["text"]).strip()
    sections = [s for s in sections if not SKIP_CATEGORY.search(s.category)]
    for i, s in enumerate(sections):
        s.order, s.sid = i, f"r{i + 1:02d}"
    return sections


def by_category(sections: list[Section]) -> dict[str, list[Section]]:
    out: dict[str, list[Section]] = {}
    for s in sections:
        out.setdefault(s.category, []).append(s)
    return out


def main() -> None:
    for path in sorted(SRC.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        cur_f, prior_f = rec["filings"][0], rec["filings"][1]
        cur, prior = to_sections(cur_f["blocks"]), to_sections(prior_f["blocks"])
        cats_c, cats_p = by_category(cur), by_category(prior)
        print(f"== {rec['ticker']} {prior_f['report_date']} -> {cur_f['report_date']}: "
              f"{len(prior)} -> {len(cur)} risk factors, categories {len(cats_p)} -> {len(cats_c)}")
        for cat in cats_c:
            pkey = next((k for k in cats_p if norm(k) == norm(cat)), None)
            p = cats_p.get(pkey, []) if pkey else []
            c = cats_c[cat]
            al = align(p, c)
            counts: dict[str, int] = {}
            for a in al:
                counts[a.status] = counts.get(a.status, 0) + 1
            words = sum(s.words for s in p) + sum(s.words for s in c)
            print(f"   {cat[:60]:<60} words={words:>6}  {counts}")


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


MAX_PAIR_WORDS = 6800


def chunk_alignment(al: list, max_words: int = MAX_PAIR_WORDS) -> list[list]:
    """Cut an ordered alignment into consecutive chunks whose prior+current words fit."""
    chunks: list[list] = [[]]
    size = 0
    for a in al:
        w = (a.prior.words if a.prior else 0) + (a.current.words if a.current else 0)
        if chunks[-1] and size + w > max_words:
            chunks.append([])
            size = 0
        chunks[-1].append(a)
        size += w
    return [c for c in chunks if c]


def render(sections: list[Section], label: str, issuer: str, fy: str) -> str:
    lines = [f"# {issuer}: Form 10-K for fiscal year ended {fy}", "",
             f"## Item 1A. Risk Factors (excerpt, {label})", ""]
    last_cat = None
    for s in sections:
        if s.category != last_cat:
            lines += [f"**{s.category}**", ""]
            last_cat = s.category
        lines += [f"### {s.heading}", "", s.body, ""]
    return "\n".join(lines).strip() + "\n"


def build_pairs(ticker: str) -> list[dict]:
    rec = json.loads((SRC / f"{ticker}.json").read_text(encoding="utf-8"))
    cur_f, prior_f = rec["filings"][0], rec["filings"][1]
    cur, prior = to_sections(cur_f["blocks"]), to_sections(prior_f["blocks"])
    al = align(prior, cur)
    out = []
    for k, chunk in enumerate(chunk_alignment(al), start=1):
        p_secs = sorted([a.prior for a in chunk if a.prior], key=lambda s: s.order)
        c_secs = sorted([a.current for a in chunk if a.current], key=lambda s: s.order)
        out.append({
            "pair_id": f"t2_{ticker.lower()}_{k}",
            "ticker": ticker,
            "prior": {"report_date": prior_f["report_date"], "url": prior_f["url"], "sections": p_secs},
            "current": {"report_date": cur_f["report_date"], "url": cur_f["url"], "sections": c_secs},
            "alignment": chunk,
            "words": sum(s.words for s in p_secs) + sum(s.words for s in c_secs),
        })
    return out


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "chunks":
    for t in sys.argv[2:]:
        for p in build_pairs(t):
            counts: dict[str, int] = {}
            for a in p["alignment"]:
                counts[a.status] = counts.get(a.status, 0) + 1
            print(p["pair_id"], p["words"], counts)
