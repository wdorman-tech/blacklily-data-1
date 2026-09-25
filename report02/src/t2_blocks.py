"""Split two versions of a document into sections and align them.

Used for both T2 sources:
  - real 10-K Item 1A text, where a section is one risk factor (bold headline + body);
  - synthetic markdown pairs, where a section is one `###` heading and its body.

The alignment is the backbone of the T2 key: every section is classified as unchanged,
modified, added, removed or moved, deterministically, before any person or model judges
materiality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

WS = re.compile(r"\s+")


def norm(text: str) -> str:
    text = text.lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("\xa0", " ")):
        text = text.replace(a, b)
    text = re.sub(r"[*`#>_]", "", text)
    return WS.sub(" ", text).strip()


def heading_key(heading: str) -> str:
    """Heading text without its section number, for alignment across renumbering."""
    h = norm(heading)
    h = re.sub(r"^(section\s+)?[a-z]?-?\d+(\.\d+)*\.?\s*", "", h)
    return h.strip(" .:")


@dataclass
class Section:
    sid: str
    heading: str
    body: str
    category: str = ""
    order: int = 0

    @property
    def text(self) -> str:
        return f"{self.heading}\n{self.body}"

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass
class Alignment:
    status: str  # unchanged | modified | added | removed | moved
    prior: Section | None
    current: Section | None
    similarity: float = 1.0
    notes: list[str] = field(default_factory=list)

    @property
    def aid(self) -> str:
        return (self.current or self.prior).sid  # type: ignore[union-attr]


def split_markdown(md: str) -> list[Section]:
    sections: list[Section] = []
    heading, body, category = None, [], ""
    for line in md.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if heading is not None:
                sections.append(Section("", heading, "\n".join(body).strip(), category))
                heading, body = None, []
            category = line[3:].strip()
            continue
        if line.startswith("### "):
            if heading is not None:
                sections.append(Section("", heading, "\n".join(body).strip(), category))
            heading, body = line[4:].strip(), []
            continue
        if heading is not None:
            body.append(line)
    if heading is not None:
        sections.append(Section("", heading, "\n".join(body).strip(), category))
    for i, s in enumerate(sections):
        s.order = i
        s.sid = f"s{i + 1:02d}"
    return sections


def align(prior: list[Section], current: list[Section]) -> list[Alignment]:
    """Pair sections across versions by heading text, then by body similarity."""
    out: list[Alignment] = []
    used_p: set[int] = set()
    used_c: set[int] = set()
    by_key_p: dict[str, list[int]] = {}
    for i, s in enumerate(prior):
        by_key_p.setdefault(heading_key(s.heading), []).append(i)

    pairs: list[tuple[int, int]] = []
    for j, c in enumerate(current):
        for i in by_key_p.get(heading_key(c.heading), []):
            if i not in used_p:
                pairs.append((i, j))
                used_p.add(i)
                used_c.add(j)
                break

    # Unmatched: fuzzy on heading, then on body.
    for j, c in enumerate(current):
        if j in used_c:
            continue
        best, best_score = None, 0.0
        for i, p in enumerate(prior):
            if i in used_p:
                continue
            h = SequenceMatcher(None, heading_key(p.heading), heading_key(c.heading)).ratio()
            b = SequenceMatcher(None, norm(p.body)[:3000], norm(c.body)[:3000]).ratio()
            score = max(h, b)
            if score > best_score:
                best, best_score = i, score
        if best is not None and best_score >= 0.72:
            pairs.append((best, j))
            used_p.add(best)
            used_c.add(j)

    for i, j in pairs:
        p, c = prior[i], current[j]
        same_text = norm(p.body) == norm(c.body) and heading_key(p.heading) == heading_key(c.heading)
        sim = SequenceMatcher(None, norm(p.text), norm(c.text)).ratio()
        if same_text:
            # Relative order among matched sections decides "moved".
            status = "unchanged"
        else:
            status = "modified"
        out.append(Alignment(status, p, c, round(sim, 3)))

    for i, p in enumerate(prior):
        if i not in used_p:
            out.append(Alignment("removed", p, None, 0.0))
    for j, c in enumerate(current):
        if j not in used_c:
            out.append(Alignment("added", None, c, 0.0))

    # Moved: matched and unchanged, but out of order relative to its neighbours.
    matched = sorted((a for a in out if a.prior and a.current), key=lambda a: a.prior.order)  # type: ignore[union-attr]
    cur_orders = [a.current.order for a in matched]  # type: ignore[union-attr]
    lis = _longest_increasing(cur_orders)
    for k, a in enumerate(matched):
        if k not in lis and a.status == "unchanged":
            a.status = "moved"

    out.sort(key=lambda a: (a.current.order if a.current else a.prior.order + 0.5))  # type: ignore[union-attr]
    return out


def _longest_increasing(seq: list[int]) -> set[int]:
    """Indices of one longest strictly increasing subsequence."""
    import bisect

    tails: list[int] = []
    tails_idx: list[int] = []
    prev = [-1] * len(seq)
    for i, x in enumerate(seq):
        k = bisect.bisect_left(tails, x)
        if k == len(tails):
            tails.append(x)
            tails_idx.append(i)
        else:
            tails[k] = x
            tails_idx[k] = i
        prev[i] = tails_idx[k - 1] if k > 0 else -1
    keep: set[int] = set()
    i = tails_idx[-1] if tails_idx else -1
    while i != -1:
        keep.add(i)
        i = prev[i]
    return keep


def word_diff(a: str, b: str, limit: int = 12) -> list[str]:
    """Human-readable list of changed word runs, for the materiality review."""
    wa, wb = a.split(), b.split()
    sm = SequenceMatcher(None, wa, wb, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        old = " ".join(wa[i1:i2])
        new = " ".join(wb[j1:j2])
        out.append(f"{op}: [{old[:300]}] -> [{new[:300]}]")
        if len(out) >= limit:
            out.append("...")
            break
    return out
