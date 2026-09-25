"""Metrics, confidence intervals and tiers, exactly as pre-registered (preregistration.md).

Every metric is a ratio of sums over items, so it can be recomputed on any resample of
items. For each (subject, task) the three runs are kept separate: a metric is computed per
run and then averaged, in the point estimate and inside every bootstrap resample.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common import RUNS, read

SEED = 20260921
RESAMPLES = 10_000
PRIMARY_KINDS = {
    "t1": {"field"}, "t2": {"material_change"}, "t3": {"question"}, "t4": {"fact"},
    "t5": {"field", "life_event", "account_action", "action_item"}, "t6": {"required_fact"}, "t7": {"planted"},
}
METRIC_LABELS = {
    "primary": {"t1": "Field accuracy", "t2": "Material-change recall", "t3": "Answer accuracy",
                "t4": "Key-fact coverage", "t5": "CRM accuracy", "t6": "Required-content rate",
                "t7": "Planted-issue recall"},
    "halluc": {"t1": "Hallucinated fields", "t2": "Invented changes", "t3": "Fabricated answers",
               "t4": "Ungrounded numbers", "t5": "Invented CRM items", "t6": "Ungrounded numbers",
               "t7": "False flags"},
    "halluc2": {"t4": "Unsupported claims"},
}


# --- merge judge verdicts into graded units ---------------------------------------------------


def load_item_units(run_dir: Path, task: str, item_id: str, graded: dict) -> tuple[list[dict], dict]:
    """Return the item's units after applying judge verdicts, plus judge-derived counts."""
    units = [dict(u) for u in graded["units"]]
    extra: dict = {}
    jdir = run_dir / "_judge"
    if task in ("t1", "t3", "t5"):
        jp = jdir / f"{item_id}.equiv.json"
        cand = [u for u in units if u["verdict"] in ("WRONG", "PARTIAL") and u["got"]
                and (task != "t5" or u["kind"] == "field")]
        if jp.exists():
            verdicts = {x["n"]: x["verdict"] for x in json.loads(read(jp))["result"]["pairs"]}
            for n, u in enumerate(cand, 1):
                if verdicts.get(n) == "equivalent":
                    u["score"], u["verdict"] = 1.0, "CORRECT_ADJUDICATED"
            extra["adjudicated"] = sum(1 for v in verdicts.values() if v == "equivalent")
        elif cand:
            extra["judge_pending"] = True
    if task == "t4":
        jp = jdir / f"{item_id}.t4.json"
        if jp.exists():
            j = json.loads(read(jp))["result"]
            key = json.loads(read(Path(__file__).resolve().parent.parent / "keys" / "t4" / f"{item_id}.json"))
            basis = {f["fid"]: f for f in key["facts"]}
            for v in j["facts"]:
                f = basis.get(v["fid"], {})
                text = (f.get("fact") or "").lower()
                trap = "non_gaap" if "non-gaap" in (f.get("basis") or "").lower() else (
                    "guidance" if any(w in text for w in ("guidance", "outlook", "expect", "forecast")) else "none")
                units.append({"uid": v["fid"], "kind": "fact", "score": 1.0 if v["verdict"] == "stated_correctly" else 0.0,
                              "verdict": v["verdict"].upper(), "trap": trap, "hallucination": v["verdict"] == "misstated",
                              "got": v.get("evidence", ""), "expected": f.get("fact", ""), "error_kind": None, "extra": {}})
            extra["claims"] = len(j["claims"])
            extra["unsupported_claims"] = sum(1 for c in j["claims"] if c["verdict"] == "unsupported")
            extra["unsupported_examples"] = [c for c in j["claims"] if c["verdict"] == "unsupported"][:5]
        else:
            extra["judge_pending"] = True
    elif task == "t6":
        jp = jdir / f"{item_id}.t6points.json"
        if jp.exists():
            j = {p["fid"]: p for p in json.loads(read(jp))["result"]["points"]}
            for u in units:
                if u["kind"] == "required_fact" and u["uid"] in j and j[u["uid"]]["verdict"] == "conveyed":
                    u["score"], u["verdict"] = 1.0, "PRESENT_JUDGED"
    elif task == "t5":
        units, extra = t5_judged_lists(run_dir, item_id, units, extra)
    elif task == "t7":
        jp = jdir / f"{item_id}.t7.json"
        needs = [u for u in units if u["kind"] == "extra_flag" and u["extra"].get("needs_adjudication")]
        if jp.exists():
            res = {x["n"]: x for x in json.loads(read(jp))["result"]["flags"]}
            planted = {u["uid"]: u for u in units if u["kind"] == "planted" and u["verdict"] == "MISSED"}
            for n, u in enumerate(needs, 1):
                x = res.get(n, {})
                if x.get("verdict") == "legitimate":
                    u["hallucination"], u["verdict"] = False, "LEGITIMATE_UNPLANTED"
                elif x.get("verdict") == "matches_known" and x.get("known_id") in planted:
                    p = planted.pop(x["known_id"])
                    p["score"], p["verdict"] = 1.0, "FLAGGED_ADJUDICATED"
                    u["hallucination"], u["verdict"] = False, "MATCHED_ADJUDICATED"
                    extra["adjudicated"] = extra.get("adjudicated", 0) + 1
        elif needs:
            extra["judge_pending"] = True
    return units, extra


LIST_KINDS = ("life_event", "account_action", "action_item", "non_action")


def t5_judged_lists(run_dir: Path, item_id: str, units: list[dict], extra: dict) -> tuple[list[dict], dict]:
    """Replace regex-paired T5 list units with the judge's semantic pairing; keep the regex units
    under *_rx kinds so the two methods can be compared."""
    extra["invented_items"] = 0
    jp = run_dir / "_judge" / f"{item_id}.t5list.json"
    if not jp.exists():
        extra["judge_pending"] = True
        return units, extra
    res = json.loads(read(jp))["result"]
    key = json.loads(read(Path(__file__).resolve().parent.parent / "keys" / "t5" / f"{item_id}.json"))
    kinds = {e["eid"]: ("life_event", "correction" if e.get("reject") else "none", e["expected"]) for e in key.get("life_events", [])}
    kinds |= {a["aid"]: ("account_action", "correction" if a.get("amount_reject") else "none", a["expected"]) for a in key.get("account_actions", [])}
    kinds |= {i["iid"]: ("action_item", i.get("trap", "none"), i["expected_task"]) for i in key.get("action_items", [])}
    out = [dict(u, kind=u["kind"] + "_rx") if u["kind"] in LIST_KINDS else u for u in units]
    seen = set()
    for x in res["key_items"]:
        if x["id"] not in kinds or x["id"] in seen:
            continue
        seen.add(x["id"])
        kind, trap, expected = kinds[x["id"]]
        found = x["record_n"] > 0
        full = found and x["figures_correct"] and (kind != "action_item" or (x["owner_correct"] and x["due_correct"]))
        score = 1.0 if full else 0.5 if found else 0.0
        verdict = "CORRECT" if full else ("STALE" if found and not x["figures_correct"] else "PARTIAL") if found else "MISSED"
        out.append({"uid": x["id"], "kind": kind, "score": score, "verdict": verdict, "trap": trap, "hallucination": False,
                    "got": f"record item {x['record_n']}" if found else "", "expected": expected, "error_kind": None,
                    "extra": {"owner_ok": x["owner_correct"], "due_ok": x["due_correct"], "figures_ok": x["figures_correct"],
                              "note": x.get("note", "")}})
    for kid, (kind, trap, expected) in kinds.items():
        if kid not in seen:  # the judge skipped it: count as missed rather than drop it
            out.append({"uid": kid, "kind": kind, "score": 0.0, "verdict": "MISSED", "trap": trap, "hallucination": False,
                        "got": "", "expected": expected, "error_kind": "judge_omitted", "extra": {}})
    nmap = {n["nid"]: n for n in key.get("non_actions", [])}
    for x in res["non_actions"]:
        if x["id"] in nmap:
            out.append({"uid": x["id"], "kind": "non_action", "score": 0.0 if x["recorded"] else 1.0,
                        "verdict": "RECORDED_NON_ACTION" if x["recorded"] else "CORRECTLY_OMITTED",
                        "trap": nmap[x["id"]].get("kind", "tentative"), "hallucination": bool(x["recorded"]),
                        "got": "", "expected": nmap[x["id"]]["what"], "error_kind": None, "extra": {}})
    extra["invented_items"] = sum(1 for x in res["extra_items"] if x["verdict"] == "unsupported")
    extra["extra_supported"] = sum(1 for x in res["extra_items"] if x["verdict"] == "supported")
    rx = {u["uid"]: u["score"] for u in units if u["kind"] in LIST_KINDS[:3]}
    jd = {u["uid"]: u["score"] for u in out if u["kind"] in LIST_KINDS[:3]}
    extra["rx_judge_agree"] = (sum(1 for k in jd if rx.get(k) == jd[k]), len(jd))
    return out, extra


# --- per-item numerators and denominators ----------------------------------------------------


def item_counts(task: str, units: list[dict], graded: dict, extra: dict) -> dict[str, tuple[float, float]]:
    prim = [u for u in units if u["kind"] in PRIMARY_KINDS[task]]
    out = {"primary": (sum(u["score"] for u in prim), float(len(prim)))}
    if task in {"t1", "t3"}:
        out["halluc"] = (float(sum(1 for u in prim if u["hallucination"])), float(len(prim)))
    elif task == "t2":
        rep = [u for u in units if u["kind"] == "reported"]
        out["halluc"] = (float(sum(1 for u in rep if u["hallucination"])), float(len(rep)))
        out["precision"] = (float(sum(1 for u in rep if not u["hallucination"])), float(len(rep)))
        out["minor_reported"] = (float(sum(1 for u in rep if not u["hallucination"] and u["extra"].get("material") is False)), float(len(rep)))
        loc = [u for u in rep if not u["hallucination"]]
        out["location"] = (float(sum(1 for u in loc if u["extra"].get("location_correct"))), float(len(loc)))
    elif task in {"t4", "t6"}:
        nums = [u for u in units if u["kind"] == "number"]
        out["halluc"] = (float(sum(1 for u in nums if u["hallucination"])), float(len(nums)))
        if task == "t4":
            out["halluc2"] = (float(extra.get("unsupported_claims", 0)), float(extra.get("claims", 0)))
            out["misstated"] = (float(sum(1 for u in prim if u["hallucination"])), float(len(prim)))
        else:
            leaks = [u for u in units if u["kind"] == "forbidden"]
            out["leak"] = (float(sum(1 for u in leaks if u["hallucination"])), float(len(leaks)))
        out["words"] = (float(graded.get("words", 0)), 1.0)
    elif task == "t5":
        non = [u for u in units if u["kind"] == "non_action" and u["hallucination"]]
        n_rep = float(graded.get("n_reported_items", 0))
        out["halluc"] = (float(len(non) + extra.get("invented_items", 0)), n_rep)
    elif task == "t7":
        flags = [u for u in units if u["kind"] == "extra_flag"]
        n_flags = float(graded.get("n_flags", 0))
        out["halluc"] = (float(sum(1 for u in flags if u["hallucination"])), n_flags)
        out["category_match"] = (float(sum(1 for u in prim if u["score"] and u["extra"].get("category_match"))),
                                 float(sum(1 for u in prim if u["score"])))
    if task == "t3":
        ans = [u for u in prim if u["extra"].get("answerable")]
        un = [u for u in prim if not u["extra"].get("answerable")]
        out["abstention"] = (float(sum(u["score"] for u in un)), float(len(un)))
        out["false_abstain"] = (float(sum(1 for u in ans if u["verdict"] == "FALSE_ABSTAIN")), float(len(ans)))
        out["answerable_acc"] = (float(sum(u["score"] for u in ans)), float(len(ans)))
    if task in {"t1", "t3"}:
        cites = [u["extra"].get("citation_valid") for u in prim if u["extra"].get("citation_valid") is not None]
        if task == "t3":
            cites = [u["extra"].get("cited_doc_ok") for u in prim if u["extra"].get("answerable")]
        out["citation"] = (float(sum(1 for c in cites if c)), float(len(cites)))
    return out


def trap_failures(task: str, units: list[dict]) -> dict[str, tuple[float, float]]:
    """Per trap category: (failures, opportunities) for one item."""
    out: dict[str, list[float]] = {}

    def add(cat: str, failed: bool) -> None:
        f, n = out.get(cat, [0.0, 0.0])
        out[cat] = [f + (1.0 if failed else 0.0), n + 1.0]

    for u in units:
        k, trap = u["kind"], u.get("trap") or "none"
        if task == "t2":
            if k == "material_change":
                add(trap, u["score"] < 1)
            elif k == "reported" and trap == "moved":
                add("moved", True)
        elif task == "t7":
            if k == "planted":
                add(trap, u["score"] < 1)
            elif k == "extra_flag" and trap == "decoy":
                add("decoy", True)
        elif task == "t6":
            if trap in {"disclosure", "internal_note", "gross_only", "concept"}:
                add(trap, u["score"] < 1)
        elif task == "t5":
            if trap != "none" and k in {"field", "life_event", "account_action", "action_item", "non_action"}:
                add(trap, u["score"] < 1)
        elif k in PRIMARY_KINDS[task] and trap != "none":
            add(trap, u["score"] < 1)
    return {c: (v[0], v[1]) for c, v in out.items()}


# --- run loading -----------------------------------------------------------------------------


@dataclass
class RunData:
    run_dir: Path
    items: dict[str, dict]  # item_id -> {"group", "counts", "traps", "units", "stats", "extra"}


def load_run(run_dir: Path) -> RunData:
    g = json.loads(read(run_dir / "_grades.json"))
    task = g["task"]
    items = {}
    for iid, graded in g["items"].items():
        units, extra = load_item_units(run_dir, task, iid, graded)
        items[iid] = {"group": graded["group"], "counts": item_counts(task, units, graded, extra),
                      "traps": trap_failures(task, units), "units": units, "stats": graded.get("stats", {}),
                      "extra": extra, "parse_problems": graded.get("parse_problems", [])}
    return RunData(run_dir, items)


def find_runs(model_slug: str, task: str, split: str = "test", variant: str = "default",
              ctx: int | None = 16384) -> list[RunData]:
    base = RUNS / model_slug / task
    if not base.exists():
        return []
    ctx_part = f"-ctx{ctx}" if ctx and not model_slug.startswith("claude") else ""
    dirs: list[Path] = []
    for v in (variant, f"{variant}-thinkoff"):  # thinking-capable models run the main arm with thinking off
        prefix = f"{split}-{v}{ctx_part}-"
        dirs = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith(prefix)
                      and d.name[len(prefix):].startswith("r") and (d / "_grades.json").exists())
        if dirs:
            break
    return [load_run(d) for d in dirs]


# --- estimation ------------------------------------------------------------------------------


def metric(runs: list[RunData], name: str, item_ids: list[str] | None = None) -> dict:
    vals = []
    for r in runs:
        ids = item_ids or list(r.items)
        num = sum(r.items[i]["counts"].get(name, (0, 0))[0] for i in ids if i in r.items)
        den = sum(r.items[i]["counts"].get(name, (0, 0))[1] for i in ids if i in r.items)
        vals.append(100.0 * num / den if den else float("nan"))
    arr = np.array(vals, dtype=float)
    ok = arr[~np.isnan(arr)]
    return {"mean": round(float(ok.mean()), 1) if ok.size else None,
            "min": round(float(ok.min()), 1) if ok.size else None,
            "max": round(float(ok.max()), 1) if ok.size else None,
            "runs": [round(v, 1) for v in vals]}


def _matrix(runs: list[RunData], name: str, ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    num = np.array([[r.items[i]["counts"].get(name, (0, 0))[0] if i in r.items else 0 for i in ids] for r in runs])
    den = np.array([[r.items[i]["counts"].get(name, (0, 0))[1] if i in r.items else 0 for i in ids] for r in runs])
    return num, den


def bootstrap_diff(local: list[RunData], frontier: list[RunData], name: str, seed: int = SEED) -> dict:
    """Paired cluster bootstrap of (local - frontier) on metric `name`, in points."""
    ids = sorted(set(local[0].items) & set(frontier[0].items))
    groups = sorted({local[0].items[i]["group"] for i in ids})
    gidx = {g: [k for k, i in enumerate(ids) if local[0].items[i]["group"] == g] for g in groups}
    ln, ld = _matrix(local, name, ids)
    fn, fd = _matrix(frontier, name, ids)
    # Sum numerators and denominators per cluster once, then resample clusters.
    def per_group(m: np.ndarray) -> np.ndarray:
        return np.stack([m[:, gidx[g]].sum(axis=1) for g in groups], axis=1)  # runs x groups
    lng, ldg, fng, fdg = per_group(ln), per_group(ld), per_group(fn), per_group(fd)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(groups), size=(RESAMPLES, len(groups)))
    counts = np.stack([np.bincount(d, minlength=len(groups)) for d in draws])  # R x G
    with np.errstate(invalid="ignore", divide="ignore"):
        l_rate = (counts @ lng.T) / (counts @ ldg.T)  # R x runs
        f_rate = (counts @ fng.T) / (counts @ fdg.T)
        diff = 100.0 * (np.nanmean(l_rate, axis=1) - np.nanmean(f_rate, axis=1))
    diff = diff[~np.isnan(diff)]
    lo, hi = np.percentile(diff, [2.5, 97.5]) if diff.size else (float("nan"), float("nan"))
    with np.errstate(invalid="ignore", divide="ignore"):
        point = 100.0 * (np.nanmean(lng.sum(1) / ldg.sum(1)) - np.nanmean(fng.sum(1) / fdg.sum(1)))
    return {"diff": round(float(point), 1), "ci": [round(float(lo), 1), round(float(hi), 1)],
            "clusters": len(groups), "items": len(ids)}


def trap_table(runs: list[RunData]) -> dict[str, dict]:
    cats: dict[str, list[tuple[float, float]]] = {}
    for r in runs:
        tot: dict[str, list[float]] = {}
        for it in r.items.values():
            for c, (f, n) in it["traps"].items():
                t = tot.setdefault(c, [0.0, 0.0])
                t[0] += f
                t[1] += n
        for c, (f, n) in tot.items():
            cats.setdefault(c, []).append((f, n))
    return {c: {"failures_mean": round(float(np.mean([f for f, _ in v])), 2),
                "opportunities": v[0][1], "runs": len(v)} for c, v in sorted(cats.items())}


def tier(task: str, local: list[RunData], frontier: list[RunData]) -> dict:
    lp, fp = metric(local, "primary")["mean"], metric(frontier, "primary")["mean"]
    names = ["halluc"] + (["halluc2"] if task == "t4" else [])
    lh = {n: metric(local, n)["mean"] for n in names}
    fh = {n: metric(frontier, n)["mean"] for n in names}
    lt, ft = trap_table(local), trap_table(frontier)
    worse_traps = [c for c in lt if lt[c]["failures_mean"] > ft.get(c, {"failures_mean": 0})["failures_mean"] + 1e-9]
    gap = fp - lp
    parity = gap <= 3.0 and all(lh[n] <= fh[n] + 1.0 for n in names) and not worse_traps
    usable = gap <= 10.0 and all(lh[n] <= 3.0 for n in names)
    t = "parity" if parity else "usable" if usable else "gap"
    reasons = []
    if gap > 3.0:
        reasons.append(f"primary {gap:.1f} points below frontier")
    for n in names:
        if lh[n] > fh[n] + 1.0:
            reasons.append(f"{METRIC_LABELS[n if n != 'halluc2' else 'halluc2'][task]} {lh[n]:.1f}% vs {fh[n]:.1f}%")
    if worse_traps:
        reasons.append("trap categories failed more often: " + ", ".join(worse_traps))
    bd = bootstrap_diff(local, frontier, "primary")
    lo, hi = bd["ci"]
    straddles = [b for b in (-3.0, -10.0) if lo < b < hi]
    return {"tier": t, "primary_local": lp, "primary_frontier": fp, "diff": bd, "halluc_local": lh,
            "halluc_frontier": fh, "worse_traps": worse_traps, "reasons": reasons,
            "not_distinguishable": bool(straddles), "straddles": straddles}
