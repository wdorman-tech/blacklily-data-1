"""Number grounding: every figure in a free-text output must appear in the source.

A number in the output is grounded if the source states the same quantity, allowing for
the ways a careful writer legitimately restates it:

  - units and scale: "$90.0 billion" matches a table cell "90,012" under "(in millions)";
  - rounding to the precision the output shows: "18%" matches "17.6%", "$4.8" matches "4.81";
  - percent forms: "1.6%", "1.60 percent" and "160 bps" are the same quantity;
  - sign conveyed in words: "down 3%" matches "(3)%" and "-3%".

It is deliberately lenient in the model's favour (a small integer will usually find a match
somewhere). What it catches is the figure that exists nowhere in the source: a computed
growth rate, a remembered number, an invented one. Years, calendar days, quarter labels,
list markers and form or rule numbers are not treated as claims.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
SCALES = {"trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6,
          "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
NUM_RX = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![\w])")
REF_BEFORE = re.compile(r"\b(section|item|rule|part|form|article|appendix|exhibit|schedule|note|page|footnote|no\.|q|fy|h|class|tier|level|phase|version|v)\s*$", re.I)
REF_AFTER = re.compile(r"^(-k|-q|\(k\)|\(b\)|\(4\)|\(a\)|\(c\)|\(d\)|-year|-month|-day|-week|-quarter|st\b|nd\b|rd\b|th\b|:\d|q\d|/\d)", re.I)
PLAN_NAMES = re.compile(r"^(401|403|457|529|1031|1099|8-k|10-k|10-q)$")


@dataclass
class Num:
    text: str
    value: float  # in base units (dollars, percentage points, plain count)
    cls: str  # currency | pct | plain
    decimals: int
    scale: float
    context: str
    in_table: bool = False


def _parse(text: str) -> list[Num]:
    out: list[Num] = []
    lower = text.lower()
    for m in NUM_RX.finditer(lower):
        s, e = m.span()
        intpart, frac = m.group(1), m.group(2) or ""
        before, after = lower[max(0, s - 14) : s], lower[e : e + 22]
        raw_num = intpart.replace(",", "") + frac
        try:
            v = float(raw_num)
        except ValueError:
            continue
        # Not claims: form and plan numbers, section refs, dates, years, list markers, times.
        if PLAN_NAMES.match(intpart) and not re.match(r"^\s*(%|percent|million|billion|bps)", after):
            continue
        if REF_BEFORE.search(before) or REF_AFTER.match(after):
            continue
        if re.search(MONTHS + r"\.?\s*$", before) and v <= 31 and not frac:
            continue
        if not frac and "," not in intpart and 1900 <= v <= 2100 and not before.rstrip().endswith("$") \
                and not re.match(r"^\s*(%|percent|million|billion|bps|basis)", after):
            continue
        line_start = lower.rfind("\n", 0, s) + 1
        if re.fullmatch(r"\s*[-*]?\s*", lower[line_start:s]) and re.match(r"^[.)]\s", after):
            continue
        cls, scale = "plain", 1.0
        if re.match(r"^\)?\s*(%|percent|per cent|pct\b|percentage points?|points?\b|pts?\b|ppts?\b)", after):
            cls = "pct"
        elif re.match(r"^\)?\s*(bps|basis points?|bp\b)", after):
            cls, v = "pct", v / 100.0
            frac = "." + "0" * (len(frac.lstrip(".")) + 2) if frac else ".00"
        if cls != "pct":
            if re.search(r"(\$|us\$|usd\s?)\(?\s*-?\s*$", before):
                cls = "currency"
            if sm := re.match(r"^\s*(trillion|tn|billion|bn|million|mm|mn|thousand|m|b|k)\b", after):
                scale = SCALES[sm.group(1)]
                cls = "currency" if cls == "currency" or re.search(r"\$", before) else cls
        line_end = lower.find("\n", e)
        in_table = " | " in lower[line_start : line_end if line_end != -1 else len(lower)]
        out.append(Num(m.group(0), v * scale, cls, len(frac.lstrip(".")), scale,
                       text[max(0, s - 40) : min(len(text), e + 40)].replace("\n", " "), in_table))
    return out


def _tolerance(n: Num) -> float:
    return 0.5 * (10 ** -n.decimals) * n.scale + 1e-9


def _matches(out_n: Num, src: list[Num]) -> bool:
    tol = _tolerance(out_n)
    target = abs(out_n.value)
    for s in src:
        # A percent in the output may come from a table cell whose "%" sat in its own cell.
        if out_n.cls == "pct" and s.cls != "pct" and not (s.in_table and s.cls == "plain"):
            continue
        if out_n.cls != "pct" and s.cls == "pct":
            continue
        scales = [1.0] if s.scale != 1.0 or out_n.cls == "pct" else [1.0, 1e3, 1e6, 1e9]
        for k in scales:
            if abs(abs(s.value) * k - target) <= tol:
                return True
    return False


def ground_numbers(output: str, source: str) -> dict:
    src = _parse(source)
    nums = []
    for n in _parse(output):
        nums.append({"text": n.text, "cls": n.cls, "value": n.value, "grounded": _matches(n, src),
                     "context": n.context})
    total = len(nums)
    ungrounded = sum(1 for n in nums if not n["grounded"])
    return {"numbers": nums, "total": total, "ungrounded": ungrounded,
            "ungrounded_rate": (ungrounded / total) if total else 0.0}


if __name__ == "__main__":
    src = ("Revenue was $90.0 billion and increased 18%. Net income | 35,812 | 27,233 (In millions). "
           "Margin expanded 160 basis points. Diluted EPS $4.81. Loss of (3)% in Europe. July 29, 2026.")
    for out in ["Revenue of $90 billion, up 18%.", "Net income $35.8 billion.", "Margin up 1.6 percentage points.",
                "EPS $4.8.", "Europe down 3%.", "Revenue grew 21.3% on a two-year basis.", "In Q2 2026 on July 29.",
                "Net income rose 31.5%."]:
        g = ground_numbers(out, src)
        print(f"{out:<48} -> {[(n['text'], n['grounded']) for n in g['numbers']]}")
