"""Fit probe for Report No. 03: does each field model load, how much of it spills out of graphics
memory, how fast it runs on the reference machine, and what the Section 6 arithmetic predicts.

    python report03/ops/fit_probe_03.py --think off gemma4:31b-it-q4_K_M qwen3.8:27b-q4_K_M
    python report03/ops/fit_probe_03.py --think low gpt-oss:120b

Same item as No. 02's fit probe (T1 dev, doc1_meridian_ridge) at 16K context and a q8_0 KV cache.
Writes report03/ops/fit_03.json, one entry per model, merged across invocations.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

import httpx
import psutil

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
sys.path.insert(0, str(R2 / "src"))
from common import (  # noqa: E402
    OLLAMA, RUNS, call_ollama, gpu_snapshot, ollama_loaded, ollama_model_info, ollama_server_config, write_json,
)
from tasks import items_for  # noqa: E402

NUM_CTX = 16384
Q8_0_BYTES_PER_ELEMENT = 34 / 32  # 32 int8 values plus one fp16 scale per block
THINK = {"auto": None, "on": True, "off": False, "low": "low", "medium": "medium", "high": "high"}
# Scored items per task in No. 03 (plan Section 4). T3 runs one 40-item firm pack.
N03 = {"t1": 9, "t2": 22, "t3": 40, "t4": 12, "t5": 9, "t6": 15, "t7": 20}


class MemSampler:
    """System memory in use and the Ollama runner's resident set, sampled every half second."""

    def __init__(self) -> None:
        self.sys_used_peak = 0
        self.runner_rss_peak = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            vm = psutil.virtual_memory()
            self.sys_used_peak = max(self.sys_used_peak, vm.total - vm.available)
            for p in psutil.process_iter(["name", "memory_info"]):
                if p.info["name"] and p.info["name"].startswith(("llama-server", "ollama_llama_server")):
                    self.runner_rss_peak = max(self.runner_rss_peak, p.info["memory_info"].rss)
            self._stop.wait(0.5)

    def __enter__(self) -> MemSampler:
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._t.join(timeout=3)


def arithmetic(model: str, file_bytes: int) -> dict:
    show = httpx.post(f"{OLLAMA}/api/show", json={"model": model}, timeout=60).json()
    mi = show.get("model_info", {})
    arch = mi.get("general.architecture", "")

    def g(key: str) -> object:
        return mi.get(f"{arch}.{key}")

    n = g("block_count")
    heads = g("attention.head_count_kv")
    heads = heads if isinstance(heads, list) else [heads] * n
    k_len = g("attention.key_length") or ((g("embedding_length") or 0) // (g("attention.head_count") or 1))
    v_len = g("attention.value_length") or k_len
    k_swa, v_swa = g("attention.key_length_swa") or k_len, g("attention.value_length_swa") or v_len
    window = g("attention.sliding_window")
    pattern = g("attention.sliding_window_pattern")
    if window and not isinstance(pattern, list) and arch == "gptoss":
        pattern = [i % 2 == 0 for i in range(n)]  # gpt-oss alternates banded and dense attention, banded first
    interval = g("full_attention_interval")  # hybrid recurrent models: only every Nth layer keeps a KV cache
    # Per layer: an attention layer caches K and V for every token in its window; a sliding-window layer
    # never holds more than the window; a recurrent layer holds a fixed-size state, counted as overhead.
    full_per_tok, swa_layers, attn_layers = 0.0, 0, 0
    swa_per_tok = 0.0
    for i in range(n):
        if interval and (i + 1) % interval:
            continue
        attn_layers += 1
        if isinstance(pattern, list) and pattern[i]:
            swa_layers += 1
            swa_per_tok += heads[i] * (k_swa + v_swa) * Q8_0_BYTES_PER_ELEMENT
        else:
            full_per_tok += heads[i] * (k_len + v_len) * Q8_0_BYTES_PER_ELEMENT
    kv_at_ctx = int(full_per_tok * NUM_CTX + swa_per_tok * min(NUM_CTX, window or NUM_CTX))
    params = mi.get("general.parameter_count")
    return {
        "architecture": arch, "parameter_count": params, "block_count": n, "attention_layers": attn_layers,
        "sliding_window_layers": swa_layers, "sliding_window": window, "head_count_kv": sorted(set(heads)),
        "key_length": k_len, "value_length": v_len, "key_length_swa": k_swa, "value_length_swa": v_swa,
        "full_attention_interval": interval,
        "expert_count": g("expert_count"), "expert_used_count": g("expert_used_count"),
        "bits_per_weight": round(file_bytes * 8 / params, 2) if params else None,
        "kv_bytes_per_token_full_layers_q8_0": int(full_per_tok),
        "kv_bytes_at_ctx": kv_at_ctx,
        "predicted_total_bytes_no_overhead": file_bytes + kv_at_ctx,
    }


def no02_token_profile() -> dict[str, list[tuple[int, int]]]:
    """(prompt, output) tokens per test item from No. 02's gemma4:12b run 1: the load a model must carry."""
    prof: dict[str, list[tuple[int, int]]] = {}
    for task in N03:
        d = RUNS / "gemma4-12b" / task / "test-default-thinkoff-ctx16384-r1"
        rows = []
        for meta in sorted(d.glob("*.meta.json")):
            s = json.loads(meta.read_text(encoding="utf-8"))["stats"]
            rows.append((s.get("prompt_tokens", 0), s.get("output_tokens", 0)))
        prof[task] = rows
    return prof


def project_hours(prompt_tps: float, output_tps: float, prof: dict) -> float:
    secs = 0.0
    for task, rows in prof.items():
        if not rows:
            continue
        per_item = sum(p / prompt_tps + o / output_tps for p, o in rows) / len(rows)
        secs += per_item * N03[task]
    return round(secs / 3600, 2)


def unload(model: str) -> None:
    httpx.post(f"{OLLAMA}/api/generate", json={"model": model, "keep_alive": 0}, timeout=120)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--think", required=True, choices=list(THINK))
    args = ap.parse_args()
    out_path = R3 / "ops" / "fit_03.json"
    out = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    cfg = ollama_server_config()
    if cfg.get("flash_attention") != "true" or cfg.get("kv_cache_type") != "q8_0":
        raise SystemExit(f"server config {cfg}: restart with report02/ops/ollama-serve.cmd first")
    if httpx.get(f"{OLLAMA}/api/ps", timeout=30).json().get("models"):
        raise SystemExit("another model is loaded: the probe needs an empty GPU")
    item = next(i for i in items_for("t1", "dev") if i.item_id == "doc1_meridian_ridge")
    prof = no02_token_profile()
    think = THINK[args.think]
    for model in args.models:
        info = ollama_model_info(model)
        entry: dict = {"digest": info["digest"], "size_bytes": info["size_bytes"], "details": info["details"],
                       "think": args.think, "server": cfg, "num_ctx": NUM_CTX}
        entry["arithmetic"] = arithmetic(model, info["size_bytes"])
        entry["vram_before_mib"] = gpu_snapshot()["vram_used_mib"]
        entry["sys_available_before_gb"] = round(psutil.virtual_memory().available / 1e9, 1)
        try:
            with MemSampler() as mem:
                warm = call_ollama(model, "Reply with OK.", "OK?", num_ctx=NUM_CTX, num_predict=4,
                                   json_mode=False, think=think)
                loaded = ollama_loaded(model)
                r = call_ollama(model, item.system, item.user, num_ctx=NUM_CTX, num_predict=item.num_predict,
                                json_mode=True, think=think)
        except Exception as exc:  # noqa: BLE001 - a model that will not load is a result, not a crash
            entry["error"] = f"{type(exc).__name__}: {exc}"[:500]
            out[model] = entry
            write_json(out_path, out)
            print(f"{model:<30} FAILED {entry['error']}", flush=True)
            unload(model)
            continue
        s = r.stats
        size, vram = loaded.get("size_bytes") or 0, loaded.get("size_vram_bytes") or 0
        prompt_secs = s["prompt_tokens"] / s["prompt_tokens_per_sec"] if s["prompt_tokens_per_sec"] else None
        entry.update({
            "load_seconds": warm.stats["load_seconds"],
            "loaded_size_bytes": size, "size_vram_bytes": vram, "fully_on_gpu": loaded.get("fully_on_gpu"),
            "spill_fraction": round(1 - vram / size, 4) if size else None,
            "measured_overhead_bytes": (size - info["size_bytes"] - (entry["arithmetic"]["kv_bytes_at_ctx"] or 0))
            if size else None,
            "peak_vram_mib": s["peak_vram_mib"], "sys_used_peak_gb": round(mem.sys_used_peak / 1e9, 1),
            "runner_rss_peak_gb": round(mem.runner_rss_peak / 1e9, 1),
            "wall_seconds": s["wall_seconds"], "prompt_tokens": s["prompt_tokens"],
            "prompt_tps": s["prompt_tokens_per_sec"], "time_to_first_token_s": round(prompt_secs, 2) if prompt_secs else None,
            "output_tokens": s["output_tokens"], "output_tps": s["output_tokens_per_sec"],
            "thinking_chars": s["thinking_chars"], "done_reason": s["done_reason"],
            "answered": bool(r.text.strip()), "reply_head": r.text[:200],
            "projected_hours_127_items": project_hours(s["prompt_tokens_per_sec"], s["output_tokens_per_sec"], prof)
            if s["prompt_tokens_per_sec"] and s["output_tokens_per_sec"] else None,
        })
        out[model] = entry
        write_json(out_path, out)
        print(f"{model:<30} spill={entry['spill_fraction']} vram {vram / 1e9:.1f}/{size / 1e9:.1f} GB "
              f"pp {s['prompt_tokens_per_sec']} tg {s['output_tokens_per_sec']} tok/s ttft {entry['time_to_first_token_s']}s "
              f"think={s['thinking_chars']} answered={entry['answered']} {s['done_reason']} "
              f"proj {entry['projected_hours_127_items']} h", flush=True)
        unload(model)


if __name__ == "__main__":
    main()
