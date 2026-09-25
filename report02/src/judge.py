"""Judged grading: T4 coverage and claims, T6 commentary points and pairwise preference,
T5 unmatched CRM items, T7 unplanted flags. Every call is a fresh headless Claude session.

Outputs are anonymized: the judge sees only the document, the key where needed and the
output text. Results are written next to the run under _judge/ and are resumable.

    python src/judge.py absolute runs/<model>/t4/<run_dir> [more run dirs]
    python src/judge.py pairwise runs/<local>/t6/<run_dir> runs/claude-opus-5/t6/<run_dir>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KEYS, PROMPTS, RUNS, call_judge, extract_json, read, sha256, write_json  # noqa: E402

_spec = importlib.util.spec_from_file_location("judge_prompts", PROMPTS / "judge.py")
J = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(J)  # type: ignore[union-attr]
_t7 = importlib.util.spec_from_file_location("p_t7", PROMPTS / "t7.py")
P7 = importlib.util.module_from_spec(_t7)  # type: ignore[arg-type]
_t7.loader.exec_module(P7)  # type: ignore[union-attr]

WORKERS = 8


def _cached(path: Path, prompt_hash: str) -> dict | None:
    if path.exists():
        d = json.loads(read(path))
        if d.get("prompt_hash") == prompt_hash:
            return d
    return None


def _judge(path: Path, system: str, user: str, schema: dict) -> dict:
    h = sha256(system + "\x00" + user)
    if (hit := _cached(path, h)) is not None:
        return hit
    shared = RUNS / "_judge_cache" / f"{h}.json"  # identical prompt judged before (a repeat run at temperature 0)
    if shared.exists():
        rec = json.loads(read(shared))
        write_json(path, rec | {"reused": True})
        return rec
    out = call_judge(system, user, schema, path.with_suffix(".transcript.jsonl"))
    rec = {"prompt_hash": h, "result": out}
    write_json(path, rec)
    write_json(shared, rec)
    return rec


def _equiv_job(task: str, iid: str, g: dict, jdir: Path) -> tuple | None:
    cand = [u for u in g["units"] if u["verdict"] in ("WRONG", "PARTIAL") and u["got"]
            and (task != "t5" or u["kind"] == "field")]  # T5 list items are paired by the t5list judge
    if not cand:
        return None
    ctx = {"t1": "Fund term field", "t3": "DDQ question", "t5": "CRM entry"}[task]
    pairs = "\n\n".join(f"{n}. {ctx}: {u['uid']}\n   Key: {u['expected']}\n   Answer: {u['got']}"
                        for n, u in enumerate(cand, 1))
    return (jdir / f"{iid}.equiv.json", J.EQUIV_SYSTEM, J.EQUIV_USER.format(pairs=pairs), J.EQUIV_SCHEMA)


def t5_record_items(raw: str) -> list[tuple[str, object]]:
    """The record's list items in a fixed order, numbered from 1 by the judge prompt and by stats."""
    parsed, _ = extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}
    out: list[tuple[str, object]] = []
    for field, kind in (("life_events", "life event"), ("account_actions", "account action"), ("action_items", "action item")):
        for x in parsed.get(field) or []:
            if x:
                out.append((kind, x))
    return out


def _task_job(task: str, iid: str, meta: dict, raw: str, g: dict | None, jdir: Path) -> tuple | None:
    doc = read(Path(meta["meta"]["doc_path"])) if meta["meta"].get("doc_path") else ""
    if task == "t4":
        key = json.loads(read(KEYS / "t4" / f"{iid}.json"))
        facts = "\n".join(f"{f['fid']}: {f['fact']} (basis: {f.get('basis', 'n/a')})" for f in key["facts"])
        return (jdir / f"{iid}.t4.json", J.T4_SYSTEM,
                J.T4_USER.format(facts=facts, release=doc, brief=raw.strip() or "(empty)"), J.T4_SCHEMA)
    if not g:
        return None
    if task == "t6":
        missed = [u["uid"] for u in g["units"] if u["kind"] == "required_fact" and u["uid"] != "disclosure" and u["score"] == 0]
        if not missed:
            return None
        key = json.loads(read(KEYS / "t6" / f"{iid}.json"))
        pts = "\n".join(f"{f['fid']}: {f['desc']}" for f in key["required_facts"] if f["fid"] in missed)
        return (jdir / f"{iid}.t6points.json", J.T6_POINTS_SYSTEM,
                J.T6_POINTS_USER.format(points=pts, sheet=doc, letter=raw.strip() or "(empty)"), J.T6_POINTS_SCHEMA)
    if task == "t5":
        key = json.loads(read(KEYS / "t5" / f"{iid}.json"))
        key_items = "\n".join(
            [f"{e['eid']} [life event]: {e['expected']}" for e in key.get("life_events", [])]
            + [f"{a['aid']} [account action]: {a['expected']}" for a in key.get("account_actions", [])]
            + [f"{i['iid']} [action item]: {i['expected_task']}" for i in key.get("action_items", [])])
        non = "\n".join(f"{n['nid']}: {n['what']}" for n in key.get("non_actions", [])) or "(none)"
        record = t5_record_items(raw)
        rec_txt = "\n".join(f"{n}. [{kind}] {json.dumps(x, ensure_ascii=False)}" for n, (kind, x) in enumerate(record, 1)) or "(none)"
        return (jdir / f"{iid}.t5list.json", J.T5LIST_SYSTEM,
                J.T5LIST_USER.format(key_items=key_items, non_actions=non, record_items=rec_txt, transcript=doc), J.T5LIST_SCHEMA)
    if task == "t7":
        extra = [u for u in g["units"] if u["kind"] == "extra_flag" and u["extra"].get("needs_adjudication")]
        if not extra:
            return None
        flags = "\n".join(f"{n}. [{u['extra'].get('category')}] \"{u['got']}\" : {u['extra'].get('reason', '')}"
                          for n, u in enumerate(extra, 1))
        missed = [u for u in g["units"] if u["kind"] == "planted" and u["verdict"] == "MISSED"]
        missed_txt = "\n".join(f"{u['uid']} [{u['trap']}]: \"{u['expected']}\"" for u in missed) or "(none)"
        return (jdir / f"{iid}.t7.json", J.T7_SYSTEM,
                J.T7_USER.format(checklist=P7.CHECKLIST, flags=flags, missed=missed_txt, draft=doc), J.T7_SCHEMA)
    return None


def jobs_for_run(run_dir: Path) -> list[tuple[Path, str, str, dict]]:
    manifest = json.loads(read(run_dir / "_manifest.json"))
    task = manifest["task"]
    grades = json.loads(read(run_dir / "_grades.json"))["items"] if (run_dir / "_grades.json").exists() else {}
    jobs = []
    for meta_path in sorted(run_dir.glob("*.meta.json")):
        meta = json.loads(read(meta_path))
        iid = meta["item_id"]
        raw_p = run_dir / f"{iid}.raw.txt"
        raw = read(raw_p) if raw_p.exists() else ""
        jdir = run_dir / "_judge"
        g = grades.get(iid)
        if task in ("t1", "t3", "t5") and g and (j := _equiv_job(task, iid, g, jdir)):
            jobs.append(j)
        if (j := _task_job(task, iid, meta, raw, g, jdir)):
            jobs.append(j)
    return jobs


def run_jobs(jobs: list) -> None:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(_judge, *j): j[0] for j in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
                print(f"[{n}/{len(jobs)}] {futs[f].parent.parent.name}/{futs[f].name}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{n}/{len(jobs)}] ERROR {futs[f]}: {exc}", flush=True)


def pairwise_jobs(local_dir: Path, frontier_dir: Path) -> list:
    out_dir = RUNS / "_pairwise" / f"{local_dir.parent.parent.name}__{local_dir.name}__vs__{frontier_dir.name}"
    jobs = []
    for meta_path in sorted(local_dir.glob("*.meta.json")):
        iid = json.loads(read(meta_path))["item_id"]
        a_p, b_p = local_dir / f"{iid}.raw.txt", frontier_dir / f"{iid}.raw.txt"
        if not (a_p.exists() and b_p.exists()):
            continue
        sheet = read(Path(json.loads(read(meta_path))["meta"]["doc_path"]))
        local, frontier = read(a_p).strip(), read(b_p).strip()
        # Both orders are always judged; which goes first is fixed by the item hash.
        first_local = int(sha256(iid), 16) % 2 == 0
        for order, (a, b) in (("LF", (local, frontier)), ("FL", (frontier, local))):
            jobs.append((out_dir / f"{iid}.{order}.json", J.T6_PAIR_SYSTEM,
                         J.T6_PAIR_USER.format(sheet=sheet, a=a, b=b), J.T6_PAIR_SCHEMA))
        if not first_local:
            jobs[-2], jobs[-1] = jobs[-1], jobs[-2]
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["absolute", "pairwise"])
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args()
    if args.mode == "absolute":
        jobs = [j for d in args.dirs for j in jobs_for_run(d)]
    else:
        jobs = pairwise_jobs(args.dirs[0], args.dirs[1])
    print(f"{len(jobs)} judge calls")
    run_jobs(jobs)


if __name__ == "__main__":
    main()
