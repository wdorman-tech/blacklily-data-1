"""Assemble results.json: the only source of any number in the paper, charts or dashboard.

    python src/build_results.py [--split test]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KEYS, ROOT, RUNS, read, sha256, write_json  # noqa: E402
from stats import METRIC_LABELS, find_runs, metric, tier, trap_table  # noqa: E402

MODELS = {
    "claude-opus-5": {"label": "Claude Opus 5", "short": "Opus 5", "role": "frontier", "tag": "claude-opus-5",
                      "card_url": "https://www.anthropic.com/claude"},
    "qwen2.5-14b-instruct-q4-k-m": {"label": "Qwen2.5 14B", "short": "Qwen2.5 14B", "role": "local_continuity",
                                    "tag": "qwen2.5:14b-instruct-q4_K_M",
                                    "card_url": "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct"},
    "gemma4-12b": {"label": "Gemma 4 12B", "short": "Gemma 4 12B", "role": "local_current", "tag": "gemma4:12b",
                   "card_url": "https://ollama.com/library/gemma4"},
    "qwen3.5-9b": {"label": "Qwen3.5 9B", "short": "Qwen3.5 9B", "role": "local_current", "tag": "qwen3.5:9b",
                   "card_url": "https://ollama.com/library/qwen3.5"},
    "ministral-3-14b": {"label": "Ministral 3 14B", "short": "Ministral 3 14B", "role": "local_current",
                        "tag": "ministral-3:14b", "card_url": "https://ollama.com/library/ministral-3"},
    "qwen2.5-7b-instruct-q4-k-m": {"label": "Qwen2.5 7B", "short": "Qwen2.5 7B", "role": "ablation_size",
                                   "tag": "qwen2.5:7b-instruct-q4_K_M",
                                   "card_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct"},
}
TASKS = {
    "t1": {"name": "Fund term extraction", "mirrors": "Diligence on a private fund's offering documents",
           "source": "Synthetic offering memoranda, LPAs and side letters"},
    "t2": {"name": "Change detection", "mirrors": "Annual document review; amended fund terms",
           "source": "Real 10-K risk factors (FY2024 vs FY2025) and synthetic LPA and policy versions"},
    "t3": {"name": "Grounded Q&A with abstention", "mirrors": "DDQ and RFP responses; internal policy lookup",
           "source": "Synthetic firm document packs and 40-question DDQs"},
    "t4": {"name": "Filing brief", "mirrors": "Morning notes and coverage updates",
           "source": "Real 8-K earnings releases, July and August 2026"},
    "t5": {"name": "Meeting notes to CRM", "mirrors": "The CRM update after every client meeting",
           "source": "Synthetic adviser-client meeting transcripts"},
    "t6": {"name": "Client drafting", "mirrors": "Quarterly client letters",
           "source": "Synthetic adviser fact sheets"},
    "t7": {"name": "Marketing review flagging", "mirrors": "First-pass review of marketing drafts for a human reviewer",
           "source": "Synthetic marketing drafts with planted issues"},
}
FAIL_ORDER = ["HALLUCINATION", "FABRICATED", "INVENTED_CHANGE", "STALE", "MISSTATED", "LEAKED", "RECORDED_NON_ACTION",
              "FLAGGED_DECOY", "WRONG", "PARTIAL", "MISSED", "ABSENT", "NOT_VERBATIM", "FALSE_ABSTAIN", "MISSING"]


def pick_failure(runs: list, task: str) -> dict | None:
    """Deterministic verbatim failure: first run, most severe verdict, first item in id order."""
    if not runs:
        return None
    r = runs[0]
    best = None
    for iid in sorted(r.items):
        for u in r.items[iid]["units"]:
            v = u["verdict"]
            if v not in FAIL_ORDER or u["kind"] in {"number"}:
                continue
            if not (u.get("got") or u.get("expected")):
                continue
            rank = FAIL_ORDER.index(v)
            if best is None or rank < best[0]:
                best = (rank, iid, u)
    if best is None:
        return None
    _, iid, u = best
    return {"item": iid, "unit": u["uid"], "verdict": u["verdict"], "trap": u.get("trap"), "got": u.get("got", "")[:600],
            "expected": u.get("expected", "")[:600], "run": r.run_dir.name}


ERR_OF = {
    "MISSING": "missed", "MISSED": "missed", "ABSENT": "missed", "FALSE_ABSTAIN": "missed",
    "STALE": "stale",
    "HALLUCINATION": "fabricated", "FABRICATED": "fabricated", "INVENTED_CHANGE": "fabricated", "LEAKED": "fabricated",
    "RECORDED_NON_ACTION": "fabricated", "FLAGGED_DECOY": "fabricated", "UNPLANTED_FLAG": "fabricated",
    "WRONG": "other", "PARTIAL": "other", "MISSTATED": "other", "NOT_VERBATIM": "other",
}


def error_taxonomy(runs: list, task: str) -> dict:
    """Failed units by kind, averaged over runs. Bad citation counts correct answers whose citation fails."""
    tot: dict[str, float] = {"missed": 0, "stale": 0, "fabricated": 0, "other": 0, "bad_citation": 0}
    units = 0
    for r in runs:
        for it in r.items.values():
            for u in it["units"]:
                if u["kind"] == "number" or (u["kind"] == "extra_flag" and not u["hallucination"]):
                    continue
                if u["kind"] in {"field", "question", "material_change", "planted", "required_fact", "fact",
                                 "life_event", "account_action", "action_item", "non_action", "forbidden"}:
                    units += 1
                kind = ERR_OF.get(u["verdict"])
                if kind and (u["score"] < 1 or u["hallucination"]):
                    tot[kind] += 1
                elif u["score"] == 1 and (u.get("extra") or {}).get("citation_valid") is False:
                    tot["bad_citation"] += 1
    n = max(1, len(runs))
    return {k: round(v / n, 1) for k, v in tot.items()} | {"units": round(units / n)}


def speed(runs: list) -> dict:
    s = [it["stats"] for r in runs for it in r.items.values() if it["stats"].get("wall_seconds")]
    if not s:
        return {}
    med = lambda k: round(statistics.median(x[k] for x in s if k in x), 1) if any(k in x for x in s) else None  # noqa: E731
    return {"sec_per_item_median": med("wall_seconds"), "output_tps_median": med("output_tokens_per_sec"),
            "prompt_tokens_median": med("prompt_tokens"), "output_tokens_median": med("output_tokens"),
            "peak_vram_mib_max": max((x.get("peak_vram_mib", 0) for x in s), default=None),
            "thinking_chars_median": med("thinking_chars"), "items": len(s)}


def manifest_info(slug: str) -> dict:
    for task in TASKS:
        for d in sorted((RUNS / slug / task).glob("test-default*-r1")) if (RUNS / slug / task).exists() else []:
            m = json.loads(read(d / "_manifest.json"))
            return {"digest": m.get("subject", {}).get("digest"), "loaded": m.get("loaded"),
                    "server": m.get("server"), "gpu_before": m.get("gpu_before"),
                    "details": m.get("subject", {}).get("details")}
    return {}


def blinding() -> dict:
    total = blind = 0
    bad = []
    for meta in (RUNS / "claude-opus-5").rglob("*.meta.json"):
        m = json.loads(read(meta))
        total += 1
        if m.get("stats", {}).get("blind"):
            blind += 1
        else:
            bad.append(str(meta.relative_to(RUNS)))
    return {"frontier_calls": total, "blind": blind, "violations": bad[:20]}


ERR_MERGE = {"bad_citation": "other", "unsupported": "fabricated"}


def pool_local_errors(out: dict) -> None:
    """Pool every local model's graded errors per task, and the study-wide shares, so the paper
    never has to compute a number the checker cannot find in results.json."""
    grand: dict[str, float] = {}
    for t in out["tasks"].values():
        counts: dict[str, float] = {}
        units = 0.0
        for slug, mm in t["models"].items():
            if not out["models"][slug]["role"].startswith("local") or slug not in t.get("vs_frontier", {}):
                continue
            e = mm.get("errors") or {}
            units += e.get("units", 0)
            for k, n in e.items():
                if k == "units" or not n:
                    continue
                k2 = ERR_MERGE.get(k, k)
                counts[k2] = counts.get(k2, 0) + n
                grand[k2] = grand.get(k2, 0) + n
        if counts:
            t["local_errors"] = {"counts": {k: round(v) for k, v in counts.items()}, "units": round(units),
                                 "total": sum(round(v) for v in counts.values())}
    n = sum(grand.values())
    if n:
        out["derived"] = {"error_total": round(n),
                          "missed_share": round(100 * grand.get("missed", 0) / n, 1),
                          "fabricated_share": round(100 * grand.get("fabricated", 0) / n, 1),
                          "stale_share": round(100 * grand.get("stale", 0) / n, 1),
                          "other_share": round(100 * grand.get("other", 0) / n, 1)}


def pairwise_section() -> dict:
    """T6 letter preference. Each pair is judged twice with positions swapped; a pair that flips is a tie."""
    out: dict = {}
    base = RUNS / "_pairwise"
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name.split("__")[0]
        items: dict[str, dict] = {}
        for f in d.glob("*.json"):
            item, order = f.name.split(".")[0], f.name.split(".")[1]
            items.setdefault(item, {})[order] = json.loads(read(f))["result"]
        tally = {"local": 0, "frontier": 0, "tie": 0}
        by_axis = {"clarity": dict(tally), "tone": dict(tally)}
        for v in items.values():
            if "FL" not in v or "LF" not in v:
                continue
            for axis, store in (("overall", tally), ("clarity", by_axis["clarity"]), ("tone", by_axis["tone"])):
                fl = "frontier" if v["FL"][axis] == "A" else "local"
                lf = "local" if v["LF"][axis] == "A" else "frontier"
                store[fl if fl == lf else "tie"] += 1
        out[slug] = {"overall": tally, "clarity": by_axis["clarity"], "tone": by_axis["tone"],
                     "items": len(items), "runs": d.name}
    return out


SIZE_PAIR = ("qwen2.5-7b-instruct-q4-k-m", "qwen2.5-14b-instruct-q4-k-m")


def size_ablation(out: dict) -> dict:
    """Same family, same prompt, same settings, half the parameters."""
    small, base = SIZE_PAIR
    rows = {}
    for tid, t in out["tasks"].items():
        a = (t.get("vs_frontier") or {}).get(small)
        b = (t.get("vs_frontier") or {}).get(base)
        if a and b:
            rows[tid] = {"name": t["name"], "small": a["primary_local"], "base": b["primary_local"],
                         "delta": round(a["primary_local"] - b["primary_local"], 1),
                         "small_halluc": round(a["halluc_local"]["halluc"], 1),
                         "halluc_label": t["halluc_label"]}
    return rows


CFG_BASE = "qwen2.5-14b-instruct-q4-k-m"


def cfg_primary(slug: str, task: str, variant: str = "default", ctx: int | None = 16384) -> float | None:
    runs = find_runs(slug, task, "test", variant, ctx)
    return round(metric(runs, "primary")["mean"], 1) if runs else None


def t1_doc_tokens() -> list[int]:
    """Prompt length of each T1 test document, so the context exhibit can show where they sit."""
    runs = find_runs(CFG_BASE, "t1", "test")
    if not runs:
        return []
    return sorted(int(it["stats"]["prompt_tokens"]) for it in runs[0].items.values() if it["stats"].get("prompt_tokens"))


def t3_as_deployed() -> dict | None:
    """Pre-registration Section 10, the "as deployed" comparison: Claude Opus 5 given the whole firm pack
    against the same-input arms. The frontier whole-pack run covers one pack, so every figure here is on
    exactly those questions."""
    whole = find_runs("claude-opus-5", "t3", "test", "fullpack")
    if not whole:
        return None
    ids = sorted(whole[0].items)

    def on_ids(runs: list) -> dict | None:
        if not runs or not set(ids) <= set(runs[0].items):
            return None
        return {m: metric(runs, m, ids)["mean"] for m in ("primary", "halluc")}

    return {
        "pack": ids[0].split(".")[0], "questions": len(ids),
        "frontier_whole_pack": on_ids(whole),
        "frontier_retrieval": on_ids(find_runs("claude-opus-5", "t3")),
        "local_retrieval": on_ids(find_runs("gemma4-12b", "t3")),
        "local_whole_pack_32k": on_ids(find_runs("gemma4-12b", "t3", "test", "fullpack", 32768)),
    }


# Keys every T3 answer must carry (the answer format in prompts/t3); T1 requires every field in the item's key.
T3_KEYS = ("answer", "source_document", "section", "quote")
LOSS_RX = re.compile(r"truncat|cut off|cut-off|incomplete (?:document|text|input)|partial (?:document|text)|"
                     r"remainder of the (?:document|text)|not (?:fully )?(?:provided|included) in full", re.I)


def silent_failure() -> dict | None:
    """Pre-registration Section 10: among items whose prompt was truncated (fewer prompt tokens processed
    than the same model processed for the same item at a 32K window, which holds every prompt), the share
    whose output is valid JSON with every required key and nothing indicating that input was lost."""
    from common import extract_json  # noqa: PLC0415
    from tasks import t1_key  # noqa: PLC0415

    arms = [  # (label, model slug, task, run dirs that may truncate, the 32K run that does not)
        ("qwen2.5-14b t1", CFG_BASE, "t1",
         [f"test-default-ctx{c}-r1" for c in (2048, 4096, 8192)] + ["test-oob-r1"], "test-default-ctx32768-r1"),
        ("gemma4-12b t1", "gemma4-12b", "t1",
         [f"test-default-thinkoff-ctx{c}-r1" for c in (2048, 4096, 8192)], "test-default-thinkoff-ctx32768-r1"),
        ("gemma4-12b t3 whole pack", "gemma4-12b", "t3",
         [f"test-fullpack-thinkoff-ctx{c}-r1" for c in (4096, 8192, 16384)], "test-fullpack-thinkoff-ctx32768-r1"),
    ]

    def prompt_tokens(d: Path) -> dict[str, int]:
        return {m.name.removesuffix(".meta.json"): json.loads(read(m))["stats"].get("prompt_tokens", 0)
                for m in d.glob("*.meta.json")}

    rows, truncated, looks_complete = [], 0, 0
    for label, slug, task, dirs, full_dir in arms:
        full = prompt_tokens(RUNS / slug / task / full_dir)
        if not full:
            continue
        for name in dirs:
            d = RUNS / slug / task / name
            if not d.exists():
                continue
            n_trunc = n_ok = 0
            for item, got in prompt_tokens(d).items():
                if item not in full or got >= full[item]:
                    continue
                n_trunc += 1
                raw = read(d / f"{item}.raw.txt") if (d / f"{item}.raw.txt").exists() else ""
                parsed, _ = extract_json(raw)
                keys = list(t1_key(item)["fields"]) if task == "t1" else list(T3_KEYS)
                complete = isinstance(parsed, dict) and all(k in parsed for k in keys)
                if complete and not LOSS_RX.search(raw):
                    n_ok += 1
            if n_trunc:
                rows.append({"arm": label, "run": name, "truncated": n_trunc, "complete_looking": n_ok,
                             "share": round(100 * n_ok / n_trunc, 1)})
                truncated += n_trunc
                looks_complete += n_ok
    if not truncated:
        return None
    by_task: dict[str, dict] = {}
    for r in rows:
        t = by_task.setdefault(r["arm"].split()[1], {"truncated": 0, "complete_looking": 0})
        t["truncated"] += r["truncated"]
        t["complete_looking"] += r["complete_looking"]
    for t in by_task.values():
        t["share"] = round(100 * t["complete_looking"] / t["truncated"], 1)
    return {"truncated_items": truncated, "complete_looking": looks_complete,
            "share": round(100 * looks_complete / truncated, 1), "by_task": by_task, "runs": rows,
            "definition": "prompt tokens processed below the same model's count for the same item at a 32K window; "
                          "complete-looking = valid JSON with every required key and no mention of lost input"}


def config_section() -> dict:
    """The configuration arms, each read from its own run directory. Absent arms stay absent."""
    out: dict = {}
    sweep = {}
    for slug in (CFG_BASE, "gemma4-12b"):
        row = {str(c): v for c in (2048, 4096, 8192, 16384, 32768) if (v := cfg_primary(slug, "t1", ctx=c)) is not None}
        if row:
            sweep[slug] = row
    if sweep:
        out["ctx_sweep"] = sweep
    base = cfg_primary(CFG_BASE, "t1")
    for name, variant, ctx in (("t1_oob", "oob", None), ("t1_naive", "naive", 16384), ("t1_nojson", "nojson", 16384)):
        v = cfg_primary(CFG_BASE, "t1", variant, ctx)
        if v is not None:
            out[name] = {"primary": v, "base": base, "delta": round(v - base, 1) if base is not None else None}
    fp = {str(c): v for c in (4096, 8192, 16384, 32768) if (v := cfg_primary("gemma4-12b", "t3", "fullpack", c)) is not None}
    if fp:
        out["t3_fullpack"] = fp
    # The three ways to answer from a pack that does not fit the window, same model, same questions.
    strategies = {"retrieval": cfg_primary("gemma4-12b", "t3"),
                  "mapreduce": cfg_primary("gemma4-12b", "t3", "mapreduce", 16384),
                  "whole_pack_16k": fp.get("16384"), "whole_pack_32k": fp.get("32768")}
    if any(v is not None for v in strategies.values()):
        out["t3_strategies"] = {k: v for k, v in strategies.items() if v is not None}
    as_deployed = t3_as_deployed()
    if as_deployed:
        out["t3_as_deployed"] = as_deployed
    silent = silent_failure()
    if silent:
        out["silent_failure"] = silent
    for task in ("t1", "t3"):
        for key, slug, variant in (("q8", "qwen3.5-9b-q8-0", "default"), ("q4", "qwen3.5-9b", "default"),
                                   ("think_on", "qwen3.5-9b", "default-thinkon"),
                                   ("think_off", "qwen3.5-9b", "default-thinkoff")):
            v = cfg_primary(slug, task, variant)
            if v is not None:
                out.setdefault("arms", {}).setdefault(task, {})[key] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    args = ap.parse_args()
    out: dict = {
        "meta": {"report": "Benchmark Report No. 02", "month": "September 2026",
                 "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "split": args.split,
                 "prereg_sha256": sha256(read(ROOT / "preregistration.md")),
                 "prompt_hashes": json.loads(read(ROOT / "prompts" / "HASHES.json")) if (ROOT / "prompts" / "HASHES.json").exists() else {}},
        "hardware": {"gpu": "NVIDIA GeForce RTX 5070", "vram_gb": 12, "cpu": "AMD Ryzen 7 7700X", "ram_gb": 63,
                     "os": "Windows 11 Pro"},
        "runtime": {"ollama": "0.34.2", "flash_attention": True, "kv_cache": "q8_0", "num_ctx": 16384},
        "models": {}, "tasks": {}, "blinding": blinding(),
    }
    for slug, info in MODELS.items():
        out["models"][slug] = {**info, "slug": slug, **(manifest_info(slug) if info["role"] != "frontier" else {})}
    for tid, tinfo in TASKS.items():
        frontier = find_runs("claude-opus-5", tid, args.split)
        t = {**tinfo, "id": tid, "primary_label": METRIC_LABELS["primary"][tid], "halluc_label": METRIC_LABELS["halluc"][tid],
             "models": {}, "vs_frontier": {}, "failures": {}}
        if tid in METRIC_LABELS["halluc2"]:
            t["halluc2_label"] = METRIC_LABELS["halluc2"][tid]
        for slug in MODELS:
            runs = frontier if slug == "claude-opus-5" else find_runs(slug, tid, args.split)
            if not runs:
                continue
            names = sorted({n for r in runs for it in r.items.values() for n in it["counts"]})
            t["models"][slug] = {n: metric(runs, n) for n in names}
            t["models"][slug]["traps"] = trap_table(runs)
            t["models"][slug]["errors"] = error_taxonomy(runs, tid)
            t["models"][slug]["speed"] = speed(runs)
            t["models"][slug]["n_runs"] = len(runs)
            t["models"][slug]["judge_pending"] = any(it["extra"].get("judge_pending") for r in runs for it in r.items.values())
            t["failures"][slug] = pick_failure(runs, tid)
            if slug != "claude-opus-5" and frontier:
                t["vs_frontier"][slug] = tier(tid, runs, frontier)
            if slug == "claude-opus-5" or "units" not in t:
                r0 = runs[0]
                t["units"] = {"items": len(r0.items), "clusters": len({it["group"] for it in r0.items.values()}),
                              "primary_units": int(sum(it["counts"]["primary"][1] for it in r0.items.values()))}
        out["tasks"][tid] = t
    t2c = KEYS.parent / "review" / "t2_materiality_contested.json"
    if t2c.exists():
        out["keys"] = {"t2_materiality": json.loads(read(t2c))["stats"]}
    pool_local_errors(out)
    dt = t1_doc_tokens()
    if dt:
        out.setdefault("derived", {})["t1_doc_tokens"] = dt
    sz = size_ablation(out)
    if sz:
        out.setdefault("derived", {})["size_ablation"] = sz
    pw = pairwise_section()
    if pw:
        out["tasks"]["t6"]["pairwise"] = pw
    cfg = config_section()
    if cfg:
        out["config"] = cfg
    write_json(ROOT / "results.json", out)
    print(f"wrote results.json: {sum(1 for t in out['tasks'].values() if t['models'])} tasks with results")
    for tid, t in out["tasks"].items():
        for slug, v in t.get("vs_frontier", {}).items():
            print(f"  {tid} {slug:<30} {v['tier']:<7} local {v['primary_local']} vs {v['primary_frontier']} "
                  f"diff {v['diff']['diff']} CI {v['diff']['ci']} {'(not distinguishable)' if v['not_distinguishable'] else ''}")


if __name__ == "__main__":
    main()
