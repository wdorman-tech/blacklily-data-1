"""Aggregate every graded run into one results file for the one-pager."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
BASELINE = ROOT / "baseline"
OUT = ROOT / "onepager" / "results.json"

LOCAL_RUNS = ["local_r1", "local_r2", "local_r3"]
ABLATIONS = [
    (
        "oob_baseline",
        "Out of the box",
        "Default context window and an unengineered prompt: what you get on install",
    ),
    ("abl_naive_prompt", "Naive prompt", "First-attempt prompt with no grounding rules"),
    ("abl_no_json", "No JSON mode", "Constrained JSON decoding turned off"),
    ("abl_ctx4096", "4K context window", "Ollama default context instead of 16K"),
    ("abl_7b", "7B instead of 14B", "Same prompt and settings, smaller model"),
]

METRICS = [
    "field_accuracy_pct",
    "hallucination_rate_pct",
    "absence_correct_pct",
    "supersession_correct_pct",
    "citation_validity_pct",
    "quote_grounding_pct",
]


def score(tag: str) -> dict | None:
    p = (RUNS / tag / "_score.json") if tag != "baseline" else (BASELINE / "_score.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def manifest(tag: str) -> dict | None:
    p = RUNS / tag / "_manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> None:
    local = [s for t in LOCAL_RUNS if (s := score(t))]
    if not local:
        raise SystemExit("no graded local runs found - run grade.py first")

    base = score("baseline")
    if base is None:
        raise SystemExit("no graded baseline found - run grade.py on baseline/ first")

    local_mean = {
        m: round(statistics.mean(s[m] for s in local), 1) for m in METRICS
    }
    local_spread = {
        m: [min(s[m] for s in local), max(s[m] for s in local)] for m in METRICS
    }

    timings = []
    for t in LOCAL_RUNS:
        if (mf := manifest(t)) is None:
            continue
        for doc in mf["docs"].values():
            timings.append(doc)

    docs_meta = {}
    for tp in sorted((ROOT / "ground_truth").glob("*.json")):
        g = json.loads(tp.read_text(encoding="utf-8"))
        md = (ROOT / "corpus" / f"{g['doc_id']}.md").read_text(encoding="utf-8")
        docs_meta[g["doc_id"]] = {
            "title": g["doc_title"],
            "difficulty": g["difficulty"],
            "words": len(md.split()),
            "traps": len(g.get("traps", {})),
        }

    per_doc_local = {}
    for doc_id in docs_meta:
        vals = [s["per_doc"][doc_id]["accuracy_pct"] for s in local if doc_id in s["per_doc"]]
        per_doc_local[doc_id] = round(statistics.mean(vals), 1) if vals else None

    results = {
        "workflow": "Private fund offering document -> 20 key investment terms with section citations",
        "audience": "RIA and family office investment diligence",
        "model": manifest(LOCAL_RUNS[0])["model"],
        "runtime": "Ollama 0.34.2, flash attention on, q8_0 KV cache",
        "hardware": "Single consumer GPU workstation, 12 GB VRAM",
        "num_ctx": manifest(LOCAL_RUNS[0])["num_ctx"],
        "corpus": {
            "documents": len(docs_meta),
            "total_words": sum(d["words"] for d in docs_meta.values()),
            "fields_per_doc": 20,
            "graded_fields": local[0]["fields_graded"],
            "docs": docs_meta,
        },
        "headline": {
            "local_accuracy_pct": local_mean["field_accuracy_pct"],
            "claude_accuracy_pct": base["field_accuracy_pct"],
            "gap_pct": round(
                base["field_accuracy_pct"] - local_mean["field_accuracy_pct"], 1
            ),
            "local_hallucination_pct": local_mean["hallucination_rate_pct"],
            "claude_hallucination_pct": base["hallucination_rate_pct"],
            "runs": len(local),
            "stable": local_spread["field_accuracy_pct"][0]
            == local_spread["field_accuracy_pct"][1],
        },
        "metrics": [
            {
                "key": m,
                "label": {
                    "field_accuracy_pct": "Field accuracy",
                    "hallucination_rate_pct": "Hallucination rate",
                    "absence_correct_pct": "Absent terms flagged correctly",
                    "supersession_correct_pct": "Amended terms read correctly",
                    "citation_validity_pct": "Citations that resolve",
                    "quote_grounding_pct": "Quotes verbatim from source",
                }[m],
                "local": local_mean[m],
                "claude": base[m],
                "lower_is_better": m == "hallucination_rate_pct",
            }
            for m in METRICS
        ],
        "per_doc": [
            {
                "doc_id": d,
                "title": docs_meta[d]["title"],
                "difficulty": docs_meta[d]["difficulty"],
                "words": docs_meta[d]["words"],
                "local": per_doc_local[d],
                "claude": base["per_doc"][d]["accuracy_pct"],
            }
            for d in docs_meta
        ],
        "ablations": [
            {
                "tag": tag,
                "label": label,
                "detail": detail,
                "accuracy": s["field_accuracy_pct"],
                "hallucination": s["hallucination_rate_pct"],
                "supersession": s["supersession_correct_pct"],
                "delta": round(s["field_accuracy_pct"] - local_mean["field_accuracy_pct"], 1),
            }
            for tag, label, detail in ABLATIONS
            if (s := score(tag))
        ],
        "performance": {
            "median_seconds_per_doc": round(
                statistics.median(t["wall_seconds"] for t in timings), 1
            ),
            "median_tokens_per_sec": round(
                statistics.median(t["output_tokens_per_sec"] for t in timings), 1
            ),
            "median_prompt_tokens": int(
                statistics.median(t["prompt_tokens"] for t in timings)
            ),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    h = results["headline"]
    print(f"local   {h['local_accuracy_pct']}%   claude {h['claude_accuracy_pct']}%   "
          f"gap {h['gap_pct']} pts   stable across {h['runs']} runs: {h['stable']}")
    print(f"{results['performance']['median_seconds_per_doc']}s/doc median, "
          f"{results['performance']['median_tokens_per_sec']} tok/s")
    print("\nablations:")
    for a in results["ablations"]:
        print(f"  {a['label']:<22} {a['accuracy']:>6}%  ({a['delta']:+.1f} pts)  "
              f"supersession {a['supersession']}%")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
