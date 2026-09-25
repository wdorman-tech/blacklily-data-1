"""Write the real 10-K T2 pairs to corpus/ and their deterministic draft keys to keys/.

Materiality of modified sections is left null here; it is labeled by the Author agent and
independently re-labeled by a Verifier agent (disagreements go to review/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t2_blocks import word_diff  # noqa: E402
from t2_real import build_pairs, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ISSUERS = {
    "CAT": ("Caterpillar Inc.", "dev"),
    "MMM": ("3M Company", "dev"),
    "JNJ": ("Johnson & Johnson", "test"),
    "KO": ("The Coca-Cola Company", "test"),
    "MA": ("Mastercard Incorporated", "test"),
    "T": ("AT&T Inc.", "test"),
    "SCHW": ("The Charles Schwab Corporation", "test"),
    "HD": ("The Home Depot, Inc.", "test"),
}


def main() -> None:
    for ticker, (name, split) in ISSUERS.items():
        for p in build_pairs(ticker):
            d = ROOT / "corpus" / "t2" / split / p["pair_id"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "prior.md").write_text(
                render(p["prior"]["sections"], "prior year", name, p["prior"]["report_date"]),
                encoding="utf-8",
            )
            (d / "current.md").write_text(
                render(p["current"]["sections"], "current year", name, p["current"]["report_date"]),
                encoding="utf-8",
            )
            sections = []
            for i, a in enumerate(p["alignment"], start=1):
                sections.append({
                    "aid": f"a{i:02d}",
                    "status": a.status,
                    "prior_heading": a.prior.heading if a.prior else "",
                    "current_heading": a.current.heading if a.current else "",
                    "similarity": a.similarity,
                    "diff": word_diff(a.prior.text, a.current.text) if a.status == "modified" else [],
                    "material": {"added": True, "removed": True, "unchanged": False, "moved": False}.get(a.status),
                    "rationale": "",
                })
            key = {
                "pair_id": p["pair_id"],
                "source": "sec_edgar_10k_item_1a",
                "issuer": name,
                "ticker": ticker,
                "split": split,
                "prior": {"fiscal_year_end": p["prior"]["report_date"], "url": p["prior"]["url"]},
                "current": {"fiscal_year_end": p["current"]["report_date"], "url": p["current"]["url"]},
                "words": p["words"],
                "sections": sections,
            }
            kd = ROOT / "keys" / "t2"
            kd.mkdir(parents=True, exist_ok=True)
            (kd / f"{p['pair_id']}.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
            n_mod = sum(1 for s in sections if s["status"] == "modified")
            print(f"{p['pair_id']:<14} {split:<4} {p['words']:>5} words, {len(sections)} sections, {n_mod} modified")


if __name__ == "__main__":
    main()
