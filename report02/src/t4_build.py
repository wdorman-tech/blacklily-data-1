"""Convert fetched 8-K Exhibit 99.1 earnings releases into T4 corpus documents."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources" / "edgar" / "8k"

# 4 dev, 12 test. Chosen for sector spread and to fit the 16K-token budget with the prompt
# and a one-page brief.
SELECTION = {
    "AAPL": ("Apple Inc.", "dev"),
    "MCD": ("McDonald's Corporation", "dev"),
    "GS": ("The Goldman Sachs Group, Inc.", "dev"),
    "XOM": ("Exxon Mobil Corporation", "dev"),
    "JPM": ("JPMorgan Chase & Co.", "test"),
    "JNJ": ("Johnson & Johnson", "test"),
    "MSFT": ("Microsoft Corporation", "test"),
    "GOOGL": ("Alphabet Inc.", "test"),
    "META": ("Meta Platforms, Inc.", "test"),
    "HD": ("The Home Depot, Inc.", "test"),
    "NVDA": ("NVIDIA Corporation", "test"),
    "T": ("AT&T Inc.", "test"),
    "MS": ("Morgan Stanley", "test"),
    "IBM": ("International Business Machines Corporation", "test"),
    "V": ("Visa Inc.", "test"),
    "CVX": ("Chevron Corporation", "test"),
}


NOISE = re.compile(
    r"^(ex-?99\.?1|exhibit 99\.1|\d{1,3}|[\w.-]+\.html?|.*activedisclosure.*|creation date.*|"
    r"copyright \(c\).*donnelley.*|document and entity information.*)$",
    re.I,
)
BULLETS = {"•", "●", "▪", "·", "-", "–", "o"}


def clean_blocks(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    pending_bullet = False
    for b in blocks:
        text = b["text"].strip()
        if b["kind"] != "row" and NOISE.match(text) and len(out) < 12:
            continue
        if text in BULLETS:
            pending_bullet = True
            continue
        if pending_bullet and b["kind"] != "row":
            b = {**b, "text": "- " + text}
        pending_bullet = False
        out.append(b)
    return out


def render(rec: dict, name: str) -> str:
    lines = [
        f"# {name}: Form 8-K, Exhibit 99.1 (earnings release)",
        "",
        f"Furnished to the SEC on {rec['filing_date']}.",
        "",
    ]
    prev_row = False
    for b in clean_blocks(rec["blocks"]):
        if b["kind"] == "row":
            lines.append(b["text"])
            prev_row = True
            continue
        if prev_row:
            lines.append("")
            prev_row = False
        if b["bold"] and len(b["text"].split()) <= 14:
            lines += [f"**{b['text']}**", ""]
        else:
            lines += [b["text"], ""]
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    for t, (name, split) in SELECTION.items():
        rec = json.loads((SRC / f"{t}.json").read_text(encoding="utf-8"))
        text = render(rec, name)
        out = ROOT / "corpus" / "t4" / split / f"t4_{t.lower()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"t4_{t.lower():<6} {split:<4} {len(text.split()):>5} words {len(text):>6} chars  ~{len(text)//3.2:.0f} tok")


if __name__ == "__main__":
    main()
