"""T3 long-document arm: map-reduce over a firm pack that does not fit the context window.

Map: the pack is split at document boundaries into three parts that each fit 16K tokens;
one call per part answers all 40 questions from that part alone. Reduce: one call per firm
reconciles the three candidate sets, later-dated documents controlling. Output is written
per question in the same shape as every other T3 run, so the same grader scores it.

    python src/t3_mapreduce.py --model qwen2.5:14b-instruct-q4_K_M --split test --run r1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CORPUS, KEYS, RUNS, call_ollama, model_slug, ollama_model_info, ollama_server_config,
    extract_json, read, sha256, write_json,
)
from tasks import _doc_label, load_prompt  # noqa: E402

REDUCE_BATCH = 10
THINK: bool | None = False
PARTS = [["01_brochure.md"], ["02_compliance_manual.md"],
         ["03_valuation_policy.md", "04_business_continuity_plan.md", "05_fee_schedule.md", "06_policy_update_memo.md"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--run", default="r1")
    ap.add_argument("--num-ctx", type=int, default=16384)
    # The main T1 to T7 arm runs the thinking-capable models with thinking off, because at this
    # window the thinking tokens consume the whole generation budget and the model returns nothing.
    # This arm has to match it or it is measuring thinking mode, not map-reduce.
    ap.add_argument("--think", choices=["auto", "on", "off"], default="off")
    args = ap.parse_args()
    p = load_prompt("t3")
    global THINK
    THINK = {"on": True, "off": False}.get(args.think)
    out = RUNS / model_slug(args.model) / "t3" / f"{args.split}-mapreduce-ctx{args.num_ctx}-{args.run}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"task": "t3", "model": args.model, "split": args.split, "run": args.run, "variant": "mapreduce", "think": args.think,
                "server": ollama_server_config(), "subject": ollama_model_info(args.model),
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "calls": []}
    for firm in sorted(x for x in (CORPUS / "t3" / args.split).iterdir() if x.is_dir()):
        key = json.loads(read(KEYS / "t3" / f"{firm.name}.json"))
        qs = key["questions"]
        qtext = "\n".join(f"{q['qid']}. {q['question']}" for q in qs)
        docs = {f.name: read(f) for f in sorted(firm.glob("*.md"))}
        partials: list[dict[str, dict]] = []
        stats_all = []
        for part in PARTS:
            ctx = "\n\n".join(p.format_document(n, docs[n]) for n in part if n in docs)
            user = p.MAP_TEMPLATE.format(context=ctx, questions=qtext, abstain=p.ABSTAIN)
            r = call_ollama(args.model, p.SYSTEM, user, num_ctx=args.num_ctx, num_predict=p.MAP_NUM_PREDICT,
                            json_mode=True, think=THINK)
            parsed, probs = extract_json(r.text)
            ans = {a.get("qid"): a for a in (parsed or {}).get("answers", []) if isinstance(a, dict)}
            partials.append(ans)
            stats_all.append(r.stats)
            manifest["calls"].append({"firm": firm.name, "step": "map", "part": part, "stats": r.stats, "problems": probs})
            print(f"{firm.name} map {part[0]}: {r.stats['wall_seconds']}s {r.stats['prompt_tokens']} in", flush=True)
        doc_list = "\n".join(f"- {n}: {_doc_label(t)}" for n, t in docs.items())

        def candidate_block(q: dict, parts: list = partials) -> str:
            lines = [f"{q['qid']}. {q['question']}"]
            for k, part in enumerate(parts, 1):
                a = part.get(q["qid"], {})
                lines.append(f"   part {k}: answer={a.get('answer', p.ABSTAIN)!r} source={a.get('source_document', '')!r} "
                             f"section={a.get('section', '')!r} quote={str(a.get('quote', ''))[:300]!r}")
            return "\n".join(lines)

        # The reduce emits one JSON object per question. Asking for all forty in a single
        # response overran the generation budget and returned an unparseable fragment, so
        # the questions go in batches; the batch size is recorded in the manifest.
        final: dict[str, dict] = {}
        reduce_wall = 0.0
        for start in range(0, len(qs), REDUCE_BATCH):
            batch = qs[start:start + REDUCE_BATCH]
            user = p.REDUCE_TEMPLATE.format(doc_list=doc_list,
                                            candidates="\n\n".join(candidate_block(q) for q in batch),
                                            abstain=p.ABSTAIN)
            r = call_ollama(args.model, p.SYSTEM, user, num_ctx=args.num_ctx,
                            num_predict=p.REDUCE_NUM_PREDICT, json_mode=True, think=THINK)
            parsed, probs = extract_json(r.text)
            final.update({a.get("qid"): a for a in (parsed or {}).get("answers", []) if isinstance(a, dict)})
            reduce_wall += r.stats["wall_seconds"]
            manifest["calls"].append({"firm": firm.name, "step": "reduce", "batch": [q["qid"] for q in batch],
                                      "stats": r.stats, "problems": probs})
            print(f"{firm.name} reduce {batch[0]['qid']}-{batch[-1]['qid']}: {r.stats['wall_seconds']}s "
                  f"{len(final)}/{len(qs)} answered", flush=True)
        total_wall = sum(s["wall_seconds"] for s in stats_all) + reduce_wall
        for q in qs:
            iid = f"{firm.name}.{q['qid']}"
            ans = final.get(q["qid"], {})
            (out / f"{iid}.raw.txt").write_text(json.dumps(ans), encoding="utf-8")
            write_json(out / f"{iid}.meta.json", {
                "item_id": iid, "task": "t3", "split": args.split,
                "group": f"{firm.name}:{q.get('source_document') or 'unanswerable'}",
                "prompt_hash": sha256(user), "subject": "local", "meta": {"firm": firm.name, "qid": q["qid"]},
                "stats": {"wall_seconds": round(total_wall / len(qs), 2), "shared_calls": len(PARTS) + (len(qs) + REDUCE_BATCH - 1) // REDUCE_BATCH},
            })
    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    write_json(out / "_manifest.json", manifest)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
