"""Assemble report03/results.json: the only source of any number in No. 03's paper, charts or dashboard.

    python report03/src/build_results_03.py

Every subject is scored on the same items: No. 03's field models, No. 02's resident local models
(the floor) and No. 02's Claude Opus 5 runs (the reference). On T3 all of them are cut to the
registered firm pack before any metric or tier is computed, so no row compares 40 items with 120.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
sys.path.insert(0, str(R2 / "src"))
from build_results import MODELS as NO2_MODELS  # noqa: E402
from build_results import TASKS, error_taxonomy, pick_failure  # noqa: E402
from common import model_slug, read, sha256, write_json  # noqa: E402
from stats import (  # noqa: E402
    METRIC_LABELS,
    RunData,
    find_runs,
    load_run,
    metric,
    tier,
    trap_table,
)

T3_PACK = "t3_f04"
GAP_TASKS = ["t2", "t4", "t5", "t7"]
# Labels only. Class, parameter counts and active parameters are read from ops/field_03.json and
# ops/fit_03.json in main(), never typed here.
FIELD = {
    "gemma4:26b-a4b-it-q4_K_M": "Gemma 4 26B-A4B",
    "qwen3.6:35b-a3b-q4_K_M": "Qwen3.6 35B-A3B",
    "qwen3.8:27b-q4_K_M": "Qwen3.8 27B",
    "gemma4:31b-it-q4_K_M": "Gemma 4 31B",
}
ANCHORS = [s for s, m in NO2_MODELS.items() if m["role"] in ("local_continuity", "local_current")]
# No. 02's local models are dense transformers (their model cards); fit_03.json shows no expert count for gemma4:12b.
NO2_CLASS = "dense"


def subset(runs: list[RunData], task: str) -> list[RunData]:
    if task != "t3":
        return runs
    return [RunData(r.run_dir, {k: v for k, v in r.items.items() if k.startswith(T3_PACK + ".")}) for r in runs]


def placement(runs: list[RunData]) -> dict:
    """Spill and speed on the reference machine, from the run manifest and per-item stats."""
    m = json.loads(read(runs[0].run_dir / "_manifest.json"))
    loaded = m.get("loaded", {})
    stats = [it["stats"] for it in runs[0].items.values() if it["stats"].get("wall_seconds")]
    wall = sum(s["wall_seconds"] for s in stats)
    out_tok = sum(s.get("output_tokens", 0) for s in stats)
    return {
        "spill_fraction": round(1 - loaded["size_vram_bytes"] / loaded["size_bytes"], 4) if loaded.get("size_bytes") else None,
        "loaded_bytes": loaded.get("size_bytes"), "vram_bytes": loaded.get("size_vram_bytes"),
        "items_timed": len(stats), "wall_seconds": round(wall, 1),
        "seconds_per_item": round(wall / len(stats), 1) if stats else None,
        "output_tokens_per_sec": round(sum(s.get("output_tokens_per_sec", 0) for s in stats) / len(stats), 1) if stats else None,
        "output_tokens": out_tok,
        "peak_vram_mib": max((s.get("peak_vram_mib", 0) for s in stats), default=None),
    }


def model_block(runs: list[RunData], task: str) -> dict:
    names = sorted({n for r in runs for it in r.items.values() for n in it["counts"]})
    return {**{n: metric(runs, n) for n in names}, "traps": trap_table(runs), "errors": error_taxonomy(runs, task),
            "n_runs": len(runs), "items": len(runs[0].items),
            "judge_pending": any(it["extra"].get("judge_pending") for r in runs for it in r.items.values())}


def _rel(p: Path) -> str:
    return p.resolve().relative_to(R3.parent.resolve()).as_posix()


def _param_size_b(details: dict | None) -> float | None:
    ps = ((details or {}).get("parameter_size") or "").upper()
    return float(ps[:-1]) if ps.endswith("B") else None


def reported_params(slug: str, tag: str, fit: dict) -> tuple[float | None, str | None]:
    """Total parameters as Ollama reports them (/api/show details.parameter_size, billions): from the fit
    probe when the model was probed, else from the model's No. 02 run manifests. One source for every model."""
    f = fit.get(tag) or {}
    v = _param_size_b(f.get("details"))
    if v is not None:
        exact = (f.get("arithmetic") or {}).get("parameter_count")
        if exact and abs(exact / 1e9 - v) > 0.05:
            raise SystemExit(f"{tag}: parameter_size {v}B disagrees with parameter_count {exact}")
        return v, "report03/ops/fit_03.json details.parameter_size"
    for man in sorted((R2 / "runs" / slug).glob("*/*/_manifest.json")):
        v = _param_size_b(json.loads(read(man)).get("subject", {}).get("details"))
        if v is not None:
            return v, f"{_rel(man)} subject.details.parameter_size"
    return None, None


def t1_speed(run: RunData) -> dict | None:
    """Median item output tokens per second and placement for one T1 run, from its manifest and item stats."""
    man = json.loads(read(run.run_dir / "_manifest.json"))
    loaded = man.get("loaded") or {}
    stats = [it["stats"] for it in run.items.values()]
    tps = [s["output_tokens_per_sec"] for s in stats if s.get("output_tokens_per_sec")]
    if not tps or not loaded.get("size_bytes"):
        return None
    ctx = (man.get("options") or {}).get("num_ctx")
    return {"method": "t1_test_median", "source": _rel(run.run_dir), "run": run.run_dir.name,
            "output_tps": round(statistics.median(tps), 1), "items": len(tps), "item_ids": sorted(run.items),
            "resident_share": round(loaded["size_vram_bytes"] / loaded["size_bytes"], 4),
            "fully_on_gpu": bool(loaded.get("fully_on_gpu")), "num_ctx": ctx, "context_k": ctx // 1024 if ctx else None,
            "think": man.get("think"), "thinking_chars": sum(s.get("thinking_chars") or 0 for s in stats)}


def probe_speed(f: dict) -> dict:
    """Fallback for a field model whose T1 test run has not landed: the fit probe, one T1 item."""
    ctx = f.get("num_ctx")
    return {"method": "fit_probe", "source": "report03/ops/fit_03.json", "run": None,
            "output_tps": f["output_tps"], "items": 1, "item_ids": [],
            "resident_share": round(1 - f["spill_fraction"], 4), "fully_on_gpu": bool(f.get("fully_on_gpu")),
            "num_ctx": ctx, "context_k": ctx // 1024 if ctx else None, "think": f.get("think"),
            "thinking_chars": f.get("thinking_chars"), "vram_before_mib": f.get("vram_before_mib")}


def spill_curve(models: dict, fit: dict, control: dict | None) -> dict:
    """Exhibit 3 data. Every point is the median item speed of one T1 test run, placement from its manifest.
    A hollow point (kind 'moved') is a resident model run at a second placement; its anchor is the resident
    run with the same items and settings, which is also that model's solid point."""
    points: list[dict] = []

    def add(slug: str, kind: str, sp: dict, **extra: object) -> dict:
        m = models[slug]
        p = {"slug": slug, "label": m["label"], "class": m.get("class", NO2_CLASS), "kind": kind, **sp, **extra}
        points.append(p)
        return p

    for slug, m in models.items():
        if m["role"] == "frontier":
            continue
        runs = find_runs(slug, "t1")
        sp = t1_speed(runs[0]) if runs else None
        f = fit.get(m["tag"]) or {}
        if sp is None and m["role"] == "field" and f.get("output_tps") is not None and f.get("spill_fraction") is not None:
            sp = probe_speed(f)
        if sp:
            add(slug, "field" if m["role"] == "field" else "resident", sp)

    for slug, m in models.items():
        if m["role"] == "frontier":
            continue
        base = R2 / "runs" / slug / "t1"
        moved = []
        if control and control.get("spilled") and (base / control["spilled"]).is_dir():
            moved.append((control["spilled"], control.get("resident"), "control"))
        moved += [(d.name, d.name.replace("ctx32768", "ctx16384"), "context") for d in sorted(base.glob("test-*ctx32768-r1"))]
        for run_name, anchor_name, why in moved:
            if not (base / run_name / "_grades.json").exists():
                continue
            run = load_run(base / run_name)
            sp = t1_speed(run)
            if not sp or sp["fully_on_gpu"]:
                continue
            anchor = next((p for p in points if p["slug"] == slug and p["run"] == anchor_name), None)
            if anchor is None and anchor_name and (base / anchor_name / "_grades.json").exists():
                a = t1_speed(load_run(base / anchor_name))
                anchor = add(slug, "resident", a) if a else None
            if anchor and (not anchor["fully_on_gpu"] or anchor["item_ids"] != sp["item_ids"]):
                raise SystemExit(f"{slug} {run_name}: anchor {anchor_name} is not a resident run on the same items")
            add(slug, "moved", sp, why=why, anchor=anchor["source"] if anchor else None)
    for p in points:
        del p["item_ids"]  # used only for the anchor check above; ids would add stray numbers to results.json
    return {
        "method": "median item output tokens per second over one T1 test run; placement from the run manifest",
        "machine": "reference machine",
        "points": points,
        "not_loaded": [t for t, f in fit.items() if f.get("loaded") is False],
    }


def size_ladder(out: dict, fit: dict, active_nominal: dict) -> dict:
    """Exhibit 6 data: mean of the four gap tasks' primary means, against total parameters."""

    def per_task(src: dict, slug: str) -> dict:
        return {t: ((src.get(t, {}).get("models", {}).get(slug) or {}).get("primary") or {}).get("mean") for t in GAP_TASKS}

    def mean4(q: dict) -> float | None:
        return round(sum(q.values()) / len(q), 1) if None not in q.values() else None

    points, frontier = [], None
    for slug, m in out["models"].items():
        q = per_task(out["tasks"], slug)
        if m["role"] == "frontier":
            frontier = {"slug": slug, "label": m["label"], "per_task": q, "mean": mean4(q)}
            continue
        params, src = reported_params(slug, m["tag"], fit)
        cls = m.get("class", NO2_CLASS)
        points.append({
            "slug": slug, "label": m["label"], "class": cls, "study": "03" if m["role"] == "field" else "02",
            "params_b": params, "params_source": src,
            "active_b_nominal": active_nominal.get(m["tag"]) if cls == "moe" else None,
            "per_task": q, "mean": mean4(q),
            # No. 02's published values are final as No. 02 published them; only No. 03's own runs can be provisional.
            "provisional": m["role"] == "field" and any(
                (out["tasks"][t]["models"].get(slug) or {}).get("judge_pending") for t in GAP_TASKS),
        })
    for slug, m in NO2_MODELS.items():
        if slug in out["models"] or m["role"] == "frontier":
            continue
        q = {}
        for t in GAP_TASKS:
            runs = find_runs(slug, t)
            q[t] = metric(runs, "primary")["mean"] if runs else None
        params, src = reported_params(slug, m["tag"], fit)
        points.append({"slug": slug, "label": m["label"], "class": NO2_CLASS, "study": "02", "params_b": params,
                       "params_source": src, "active_b_nominal": None, "per_task": q, "mean": mean4(q),
                       "provisional": False})
    return {
        "tasks": GAP_TASKS,
        "quality": "mean of the four gap tasks' primary-metric means, each as stored under tasks.<id>.models",
        "params": "total parameters as Ollama reports them (details.parameter_size), billions",
        "active": "nominal active parameters from the Ollama library listing (the model name), ops/field_03.json",
        "points": points, "frontier": frontier,
    }


# Section 13 of the pre-registration read this line when the file was hashed at registration.
REGISTERED_SECTION_13 = "None yet.\r\n"


def registration() -> dict:
    """The registered hash and time from ops/REGISTRATION.json, and whether everything above the first
    Section 13 entry still reproduces that hash (register.py hashed the file's bytes)."""
    reg = json.loads(read(R3 / "ops" / "REGISTRATION.json"))
    raw = (R3 / "preregistration.md").read_bytes()
    head = raw[: raw.index(b"## 13. Deviations")]
    rebuilt = head + b"## 13. Deviations\r\n\r\n" + REGISTERED_SECTION_13.encode()
    registered = reg["sha256"]["report03/preregistration.md"]
    return {"registered_at": reg["registered_at"], "sha256_registered": registered,
            "sha256_method": "register.py: SHA-256 of the file's bytes at registration (ops/REGISTRATION.json)",
            "above_section_13_reproduces_registered": hashlib.sha256(rebuilt).hexdigest() == registered}


def frontier_runs() -> int:
    """Runs per item behind the frontier column. One per task, or the build stops."""
    n = {len(find_runs("claude-opus-5", tid)) for tid in TASKS}
    if len(n) != 1:
        raise SystemExit(f"frontier run count differs across tasks: {sorted(n)}")
    return n.pop()


def spilled_repeat(control: dict | None) -> dict | None:
    """Byte identity of the second spilled control run (the -spill2 directory) against the first spilled run."""
    if not control:
        return None
    base = R2 / "runs" / "gemma4-12b" / "t1"
    rep = base / control["spilled"].replace("-r1", "-spill2")
    if not rep.is_dir():
        return None
    first = base / control["spilled"]
    pairs = [(p, first / p.name) for p in sorted(rep.glob("*.raw.txt"))]
    loaded = json.loads(read(rep / "_manifest.json")).get("loaded") or {}
    return {"run": rep.name, "compared_with": first.name, "items": len(pairs),
            "identical": sum(a.read_bytes() == b.read_bytes() for a, b in pairs),
            "fully_on_gpu": bool(loaded.get("fully_on_gpu"))}


def wall_clock(queue: dict, models: dict) -> dict:
    """Each field model's test-split time as the queue counted it against the ceiling (ops/queue_state.json)."""
    test = queue.get("test", {})
    by_tag = {m["tag"]: s for s, m in models.items() if m["role"] == "field"}
    return {
        "method": "the queue's own count for each field model: the elapsed time of every test-split job, model "
                  "loads included, the pause excluded; the part of the one job stopped by the pause is included "
                  "and its in-flight item was rerun on resume",
        "machine": "reference machine",
        "seconds": {by_tag[t]: round(s, 1) for t, s in test.get("spent_s", {}).items() if t in by_tag},
        "pauses": [{"stopped": p["stopped"], "resumed": p["resume_at"], "credited_seconds": p["credited_s"],
                    "model": by_tag.get(p["job"].split()[1].rstrip(",")), "task": p["job"].split()[0]}
                   for p in test.get("pauses", [])],
    }


def main() -> None:
    queue = json.loads(read(R3 / "ops" / "queue_state.json")) if (R3 / "ops" / "queue_state.json").exists() else {}
    field_snapshot = json.loads(read(R3 / "ops" / "field_03.json"))
    fit = json.loads(read(R3 / "ops" / "fit_03.json"))
    klass = {tag: c for c, tags in field_snapshot["field"].items() for tag in tags}
    active_nominal = {c["build"]["tag"]: c["active_b"] for c in field_snapshot["candidates"]}
    n_fr = frontier_runs()
    out: dict = {
        "meta": {"report": "Benchmark Report No. 03", "month": "September 2026",
                 "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "t3_pack": T3_PACK,
                 "prereg_sha256": sha256(read(R3 / "preregistration.md")),
                 "prereg_sha256_method": "SHA-256 of the file's current text, Section 13 included, with line "
                                         "endings normalized to LF",
                 "registration": registration(),
                 "frontier_runs_per_item": n_fr,
                 "frontier_source": f"Benchmark Report No. 02 test run{'s' if n_fr > 1 else ''} r1"
                                    + (f" to r{n_fr}" if n_fr > 1 else "")
                                    + f", {n_fr} run per item (No. 02 deviation of 2026-09-22), not re-run"},
        "hardware": {"gpu": "NVIDIA GeForce RTX 5070", "vram_gb": 12, "cpu": "AMD Ryzen 7 7700X", "ram_gb": 63,
                     "os": "Windows 11 Pro", "role": "reference machine: a deliberately modest floor"},
        "runtime": {"ollama": "0.34.2", "flash_attention": True, "kv_cache": "q8_0", "num_ctx": 16384},
        "field": field_snapshot["field"],
        "fit": fit,
        "control": json.loads(read(R3 / "ops" / "control_03.json")) if (R3 / "ops" / "control_03.json").exists() else None,
        "did_not_complete": queue.get("test", {}).get("did_not_complete", {}),
        "models": {}, "tasks": {},
    }
    for tag, label in FIELD.items():
        params, src = reported_params(model_slug(tag), tag, fit)
        out["models"][model_slug(tag)] = {
            "label": label, "class": klass[tag], "tag": tag, "role": "field", "params_b": params, "params_source": src,
            "active_b_nominal": active_nominal.get(tag) if klass[tag] == "moe" else None}
    for slug in ANCHORS:
        out["models"][slug] = {**NO2_MODELS[slug], "role": "resident_anchor"}
    out["models"]["claude-opus-5"] = {**NO2_MODELS["claude-opus-5"], "role": "frontier"}

    for tid, tinfo in TASKS.items():
        frontier = subset(find_runs("claude-opus-5", tid), tid)
        t = {**tinfo, "id": tid, "primary_label": METRIC_LABELS["primary"][tid],
             "halluc_label": METRIC_LABELS["halluc"][tid], "gap_task": tid in GAP_TASKS,
             "models": {}, "vs_frontier": {}, "placement": {}, "failures": {}}
        for slug, info in out["models"].items():
            runs = frontier if slug == "claude-opus-5" else subset(find_runs(slug, tid), tid)
            if not runs or not runs[0].items:
                continue
            t["models"][slug] = model_block(runs, tid)
            t["failures"][slug] = pick_failure(runs, tid)
            if info["role"] != "frontier" and frontier:
                t["vs_frontier"][slug] = tier(tid, runs, frontier)
            if info["role"] == "field":
                t["placement"][slug] = placement(runs)
        if frontier:
            f0 = frontier[0]
            t["units"] = {"items": len(f0.items), "clusters": len({it["group"] for it in f0.items.values()})}
        best = {}
        for role in ("resident_anchor", "field"):
            cands = [(v["primary_local"], s) for s, v in t["vs_frontier"].items() if out["models"][s]["role"] == role]
            if cands:
                p, s = max(cands)
                best[role] = {"slug": s, "primary": p, "tier": t["vs_frontier"][s]["tier"]}
        if frontier:
            best["frontier"] = {"primary": metric(frontier, "primary")["mean"]}
        t["gap_closure"] = best
        out["tasks"][tid] = t
    if out["control"]:
        out["control"]["spilled_repeat"] = spilled_repeat(out["control"])
    out["wall_clock"] = wall_clock(queue, out["models"])
    out["spill_curve"] = spill_curve(out["models"], fit, out["control"])
    out["size_ladder"] = size_ladder(out, fit, active_nominal)
    write_json(R3 / "results.json", out)
    print(f"wrote report03/results.json: {sum(1 for t in out['tasks'].values() if t['vs_frontier'])} tasks")
    for tid, t in out["tasks"].items():
        for slug, v in t["vs_frontier"].items():
            if out["models"][slug]["role"] != "field":
                continue
            pl = t["placement"].get(slug, {})
            print(f"  {tid} {slug:<28} {v['tier']:<7} {v['primary_local']} vs {v['primary_frontier']} "
                  f"CI {v['diff']['ci']} spill {pl.get('spill_fraction')} {pl.get('seconds_per_item')} s/item")


if __name__ == "__main__":
    main()
