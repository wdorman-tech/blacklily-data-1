"""Run one subject over one task split and write raw outputs plus a manifest.

Local models run serially (one GPU). The frontier runs through headless Claude Code with
a small thread pool. Re-running the same command resumes: finished items are skipped.

    python src/run.py --task t1 --model qwen2.5:14b-instruct-q4_K_M --split test --run r1
    python src/run.py --task t1 --model claude-opus-5 --split test --run r1 --workers 6
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    RUNS, call_frontier, call_ollama, gpu_snapshot, is_frontier, model_slug,
    ollama_loaded, ollama_model_info, ollama_server_config, sha256, write_json,
)
from tasks import Item, items_for  # noqa: E402


def run_dir(model: str, task: str, split: str, variant: str, num_ctx: int | None, run: str) -> Path:
    ctx = f"-ctx{num_ctx}" if num_ctx and not is_frontier(model) else ""
    return RUNS / model_slug(model) / task / f"{split}-{variant}{ctx}-{run}"


def item_done(out: Path, item: Item) -> bool:
    meta = out / f"{item.item_id}.meta.json"
    if not meta.exists():
        return False
    return json.loads(meta.read_text(encoding="utf-8")).get("prompt_hash") == item.prompt_hash


def save_item(out: Path, item: Item, text: str, stats: dict, extra: dict) -> None:
    (out / f"{item.item_id}.raw.txt").write_text(text, encoding="utf-8")
    write_json(out / f"{item.item_id}.meta.json", {
        "item_id": item.item_id, "task": item.task, "split": item.split, "group": item.group,
        "prompt_hash": item.prompt_hash, "system_hash": sha256(item.system),
        "user_hash": sha256(item.user), "json_mode": item.json_mode,
        "num_predict": item.num_predict, "meta": item.meta, "stats": stats, **extra,
    })


def run_local(args: argparse.Namespace, items: list[Item], out: Path, manifest: dict) -> None:
    cfg = manifest["server"]
    if cfg.get("flash_attention") != "true" or cfg.get("kv_cache_type") != "q8_0":
        raise SystemExit(f"server config is {cfg}; flash attention and q8_0 KV cache are required")
    num_ctx = args.num_ctx
    json_off = args.variant in {"nojson", "oob"}
    # gpt-oss cannot turn reasoning off; it takes an effort level instead of a boolean.
    think = {"auto": None, "on": True, "off": False}.get(args.think, args.think)
    # Warm the model so load time is not charged to the first item.
    call_ollama(args.model, "Reply with OK.", "OK?", num_ctx=num_ctx, num_predict=4,
                json_mode=False, think=think, num_gpu=args.num_gpu)
    manifest["loaded"] = ollama_loaded(args.model)
    manifest["gpu_after_load"] = gpu_snapshot()
    write_json(out / "_manifest.json", manifest)
    for n, item in enumerate(items, 1):
        if item_done(out, item):
            continue
        try:
            reply = call_ollama(args.model, item.system, item.user, num_ctx=num_ctx,
                                num_predict=item.num_predict,
                                json_mode=item.json_mode and not json_off, think=think,
                                num_gpu=args.num_gpu)
        except Exception as exc:  # noqa: BLE001 - record and move on; the grader scores it as a miss
            save_item(out, item, "", {"error": f"{type(exc).__name__}: {exc}"}, {"subject": "local"})
            print(f"[{n}/{len(items)}] {item.item_id} ERROR {exc}", flush=True)
            continue
        if reply.thinking:
            (out / f"{item.item_id}.thinking.txt").write_text(reply.thinking, encoding="utf-8")
        save_item(out, item, reply.text, reply.stats, {"subject": "local"})
        s = reply.stats
        print(f"[{n}/{len(items)}] {item.item_id} {s['wall_seconds']}s {s['prompt_tokens']} in / "
              f"{s['output_tokens']} out {s['output_tokens_per_sec']} tok/s "
              f"vram {s['peak_vram_mib']} {s['done_reason']}", flush=True)
    manifest["loaded_end"] = ollama_loaded(args.model)


def run_frontier(args: argparse.Namespace, items: list[Item], out: Path) -> None:
    todo = [it for it in items if not item_done(out, it)]

    def one(item: Item) -> tuple[Item, dict]:
        reply = call_frontier(item.system, item.user, out / f"{item.item_id}.transcript.jsonl")
        save_item(out, item, reply.text, reply.stats, {"subject": "frontier"})
        return item, reply.stats

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(one, it) for it in todo]
        for n, f in enumerate(as_completed(futs), 1):
            try:
                item, s = f.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[{n}/{len(todo)}] ERROR {exc}", flush=True)
                continue
            flag = "" if s["blind"] else "  NOT BLIND"
            print(f"[{n}/{len(todo)}] {item.item_id} {s['wall_seconds']}s {s['input_tokens']} in / "
                  f"{s['output_tokens']} out ({s['thinking_tokens']} thinking){flag}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--run", default="r1")
    ap.add_argument("--variant", default="default")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--think", default="auto", choices=["auto", "on", "off", "low", "medium", "high"])
    ap.add_argument("--num-gpu", type=int, default=None, help="force this many layers onto the GPU")
    ap.add_argument("--items", default=None, help="comma-separated item ids (pilot)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if args.split == "test":
        frozen = RUNS.parent / "prompts" / "HASHES.json"
        if not frozen.exists():
            raise SystemExit("prompts are not frozen: run ops/freeze_prompts.py before any test-split run")
        sys.path.insert(0, str(RUNS.parent / "ops"))
        from freeze_prompts import current  # noqa: PLC0415

        want = json.loads(frozen.read_text(encoding="utf-8"))
        if current()["files"] != want["files"]:
            raise SystemExit("prompt files changed since they were frozen; log a deviation and re-freeze deliberately")
    items = items_for(args.task, args.split, args.variant)
    if args.items:
        wanted = set(args.items.split(","))
        items = [i for i in items if i.item_id in wanted]
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit("no items selected")

    frontier = is_frontier(args.model)
    variant = args.variant + ("" if args.think == "auto" else f"-think{args.think}")
    if args.num_gpu is not None:
        variant += f"-gpu{args.num_gpu}"
    out = run_dir(args.model, args.task, args.split, variant, None if frontier else args.num_ctx, args.run)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task": args.task, "model": args.model, "split": args.split, "run": args.run,
        "variant": args.variant, "think": args.think, "num_gpu": args.num_gpu, "items": len(items),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "prompt_hashes": sorted({i.prompt_hash for i in items})[:3] + ["..."],
        "system_hashes": sorted({sha256(i.system) for i in items}),
    }
    if frontier:
        manifest["subject"] = {"via": "claude -p --safe-mode --tools \"\" --system-prompt-file",
                               "model": args.model, "workers": args.workers}
        write_json(out / "_manifest.json", manifest)
        run_frontier(args, items, out)
    else:
        manifest.update({
            "subject": {"via": "ollama /api/chat", "model": args.model, **ollama_model_info(args.model)},
            "server": ollama_server_config(),
            "options": {"num_ctx": args.num_ctx, "temperature": 0.0, "top_p": 0.9, "repeat_penalty": 1.0},
            "gpu_before": gpu_snapshot(),
        })
        write_json(out / "_manifest.json", manifest)
        run_local(args, items, out, manifest)
    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    write_json(out / "_manifest.json", manifest)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
