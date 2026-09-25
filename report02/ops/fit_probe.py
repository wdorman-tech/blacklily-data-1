"""Measure whether each candidate model fits entirely on the GPU at 16K context (q8_0 KV cache),
how fast it runs, and whether Ollama serves it thinking by default. Writes ops/fit.json.

    python ops/fit_probe.py gemma4:12b qwen3.5:9b qwen2.5:14b-instruct-q4_K_M ministral-3:14b
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from common import (  # noqa: E402
    call_ollama, gpu_snapshot, ollama_loaded, ollama_model_info, ollama_server_config, write_json,
)
from tasks import items_for  # noqa: E402


def main() -> None:
    out_path = ROOT / "ops" / "fit.json"
    out = json.loads(out_path.read_text()) if out_path.exists() else {}
    cfg = ollama_server_config()
    if cfg.get("flash_attention") != "true" or cfg.get("kv_cache_type") != "q8_0":
        raise SystemExit(f"server config {cfg}: restart with ops/ollama-serve.cmd first")
    item = next(i for i in items_for("t1", "dev") if i.item_id == "doc1_meridian_ridge")
    for model in sys.argv[1:]:
        info = ollama_model_info(model)
        before = gpu_snapshot()
        r = call_ollama(model, item.system, item.user, num_ctx=16384, num_predict=item.num_predict, json_mode=True)
        loaded = ollama_loaded(model)
        out[model] = {
            "digest": info["digest"], "size_bytes": info["size_bytes"], "details": info["details"],
            "fully_on_gpu": loaded.get("fully_on_gpu"), "size_vram_bytes": loaded.get("size_vram_bytes"),
            "loaded_size_bytes": loaded.get("size_bytes"), "context_length": loaded.get("context_length"),
            "vram_before_mib": before["vram_used_mib"], "peak_vram_mib": r.stats["peak_vram_mib"],
            "wall_seconds": r.stats["wall_seconds"], "output_tps": r.stats["output_tokens_per_sec"],
            "prompt_tps": r.stats["prompt_tokens_per_sec"], "output_tokens": r.stats["output_tokens"],
            "thinks_by_default": r.stats["thinking_chars"] > 0, "thinking_chars": r.stats["thinking_chars"],
            "done_reason": r.stats["done_reason"], "server": cfg,
        }
        o = out[model]
        print(f"{model:<32} on_gpu={o['fully_on_gpu']} vram {o['size_vram_bytes']}/{o['loaded_size_bytes']} "
              f"{o['output_tps']} tok/s {o['wall_seconds']}s thinks={o['thinks_by_default']}", flush=True)
        write_json(out_path, out)


if __name__ == "__main__":
    main()
