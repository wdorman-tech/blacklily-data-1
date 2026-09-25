"""Shared plumbing for Report No. 02: paths, model clients, hashing, text utilities.

Two subjects are called through this module and nothing else:

  - local models through the Ollama HTTP API on this workstation, one call at a time;
  - the frontier model through headless Claude Code (`claude -p`) with no tools, no
    instruction files, no hooks, and the task's own system prompt in place of Claude Code's.

Both receive byte-identical system and user text for the same item.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
NO1 = ROOT.parent
CORPUS = ROOT / "corpus"
KEYS = ROOT / "keys"
RUNS = ROOT / "runs"
PROMPTS = ROOT / "prompts"
OLLAMA = "http://127.0.0.1:11434"
FRONTIER = "claude-opus-5"
FRONTIER_CWD = ROOT / "ops" / "frontier_cwd"  # empty directory: nothing to discover


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_json(p: Path, obj: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def model_slug(model: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", model.lower()).strip("-")


def is_frontier(model: str) -> bool:
    return model.startswith("claude-")


# --- text -----------------------------------------------------------------------------------

_DASHES = {"—": "-", "–": "-", "‒": "-", "−": "-"}
_QUOTES = {"’": "'", "‘": "'", "“": '"', "”": '"', "\xa0": " "}


def normalize(text: str) -> str:
    """Same normalization as No. 01's grader, applied everywhere in No. 02."""
    text = text.lower()
    for a, b in {**_DASHES, **_QUOTES}.items():
        text = text.replace(a, b)
    text = re.sub(r"[*`>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_grounded(quote: str, source_norm: str) -> bool | None:
    """No. 01's rule: verbatim after normalization, or a long contiguous run of it."""
    q = normalize(quote)
    if len(q) < 15:
        return None
    if q in source_norm:
        return True
    words = q.split()
    for size in (14, 10, 8):
        if len(words) < size:
            continue
        for i in range(0, len(words) - size + 1):
            if " ".join(words[i : i + size]) in source_norm:
                return True
    return False


def extract_json(raw: str) -> tuple[object | None, list[str]]:
    """Find and parse the JSON object in a model's raw output, recording every repair."""
    problems: list[str] = []
    text = raw.strip()
    if text.startswith("```"):
        problems.append("wrapped_in_markdown_fence")
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start > 0 or (end != -1 and end < len(text.strip()) - 1):
        problems.append("prose_around_json")
    if start == -1 or end == -1:
        return None, problems + ["no_json_object_found"]
    try:
        return json.loads(text[start : end + 1]), problems
    except json.JSONDecodeError as exc:
        return None, problems + [f"invalid_json:{exc.msg}"]


# --- GPU telemetry ----------------------------------------------------------------------------


def gpu_snapshot() -> dict:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    used, total, util = (int(x.strip()) for x in out.split(","))
    return {"vram_used_mib": used, "vram_total_mib": total, "gpu_util_pct": util}


class VramSampler:
    """Samples nvidia-smi once a second in the background and keeps the peak."""

    def __init__(self) -> None:
        self.peak = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, gpu_snapshot()["vram_used_mib"])
            except Exception:  # noqa: BLE001 - telemetry must never kill a run
                pass
            self._stop.wait(1.0)

    def __enter__(self) -> VramSampler:
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._t.join(timeout=3)


def ollama_server_config() -> dict:
    """Read the flags the running server actually started with, from its own log line."""
    log = ROOT / "logs" / "ollama-server.log"
    cfg: dict = {"flash_attention": None, "kv_cache_type": None, "version": None}
    try:
        cfg["version"] = httpx.get(f"{OLLAMA}/api/version", timeout=10).json()["version"]
    except Exception:  # noqa: BLE001
        pass
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")  # the server log carries GPU driver bytes
        lines = [ln for ln in text.splitlines() if 'msg="server config"' in ln]
        if lines:
            last = lines[-1]
            if m := re.search(r"OLLAMA_FLASH_ATTENTION:(\w+)", last):
                cfg["flash_attention"] = m.group(1)
            if m := re.search(r"OLLAMA_KV_CACHE_TYPE:(\S*)", last):
                cfg["kv_cache_type"] = m.group(1) or "f16"
            if m := re.search(r"OLLAMA_NUM_PARALLEL:(\d+)", last):
                cfg["num_parallel"] = int(m.group(1))
    return cfg


def ollama_model_info(model: str) -> dict:
    tags = httpx.get(f"{OLLAMA}/api/tags", timeout=30).json()["models"]
    for t in tags:
        if t["name"] == model:
            return {"digest": t["digest"], "size_bytes": t["size"], "details": t.get("details", {})}
    raise SystemExit(f"model {model!r} is not pulled")


def ollama_loaded(model: str) -> dict:
    for m in httpx.get(f"{OLLAMA}/api/ps", timeout=30).json().get("models", []):
        if m["name"] == model:
            return {
                "size_bytes": m.get("size"),
                "size_vram_bytes": m.get("size_vram"),
                "fully_on_gpu": m.get("size") == m.get("size_vram"),
                "context_length": m.get("context_length"),
            }
    return {}


# --- subject calls ------------------------------------------------------------------------------


@dataclass
class Reply:
    text: str
    stats: dict = field(default_factory=dict)
    thinking: str = ""


def call_ollama(
    model: str,
    system: str,
    user: str,
    *,
    num_ctx: int,
    num_predict: int,
    json_mode: bool,
    temperature: float = 0.0,
    think: bool | str | None = None,
    num_gpu: int | None = None,
) -> Reply:
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.0,
            "num_predict": num_predict,
        },
    }
    if num_ctx <= 0:  # "out of the box": let the server choose its default context window
        del payload["options"]["num_ctx"]
    if num_gpu is not None:  # layers held in graphics memory; the rest run from system memory
        payload["options"]["num_gpu"] = num_gpu
    if json_mode:
        payload["format"] = "json"
    if think is not None:
        payload["think"] = think
    started = time.perf_counter()
    with VramSampler() as vram, httpx.Client(timeout=3600.0) as client:
        resp = client.post(f"{OLLAMA}/api/chat", json=payload)
        resp.raise_for_status()
        body = resp.json()
    wall = time.perf_counter() - started
    msg = body.get("message", {})
    eval_ns = body.get("eval_duration", 0) or 1
    prompt_ns = body.get("prompt_eval_duration", 0) or 1
    stats = {
        "wall_seconds": round(wall, 2),
        "prompt_tokens": body.get("prompt_eval_count", 0),
        "output_tokens": body.get("eval_count", 0),
        "output_tokens_per_sec": round(body.get("eval_count", 0) / (eval_ns / 1e9), 1),
        "prompt_tokens_per_sec": round(body.get("prompt_eval_count", 0) / (prompt_ns / 1e9), 1),
        "load_seconds": round(body.get("load_duration", 0) / 1e9, 2),
        "done_reason": body.get("done_reason"),
        "thinking_chars": len(msg.get("thinking") or ""),
        "peak_vram_mib": vram.peak,
    }
    return Reply(msg.get("content", ""), stats, msg.get("thinking") or "")


def call_judge(system: str, user: str, schema: dict, transcript_path: Path, *, retries: int = 3) -> dict:
    """A judge call: headless Claude Opus 5, no tools but StructuredOutput, fresh session."""
    FRONTIER_CWD.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_path.resolve()  # the subprocess runs in FRONTIER_CWD
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    sys_file = transcript_path.with_suffix(".system.txt")
    sys_file.write_text(system, encoding="utf-8")
    cmd = [
        "claude", "-p", "--safe-mode", "--tools", "", "--model", FRONTIER,
        "--system-prompt-file", str(sys_file), "--json-schema", json.dumps(schema),
        "--output-format", "stream-json", "--verbose", "--no-session-persistence",
    ]
    last_err = ""
    for attempt in range(1, retries + 1):
        proc = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                              cwd=FRONTIER_CWD, timeout=1800)
        transcript_path.write_text(proc.stdout, encoding="utf-8")
        events = [json.loads(ln) for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        result = next((e for e in events if e.get("type") == "result"), None)
        if proc.returncode == 0 and result and isinstance(result.get("structured_output"), dict):
            return result["structured_output"]
        last_err = f"exit={proc.returncode} result={result and result.get('subtype')} stderr={proc.stderr[-300:]}"
        time.sleep(10 * attempt)
    raise RuntimeError(f"judge call failed: {last_err}")


def call_frontier(system: str, user: str, transcript_path: Path, *, retries: int = 3) -> Reply:
    """One blind frontier call through headless Claude Code.

    --safe-mode   no CLAUDE.md, skills, plugins, hooks, MCP servers, custom agents
    --tools ""    no tools at all, so the subject cannot read keys or anything else
    --system-prompt-file  the task's system prompt replaces Claude Code's
    The full event stream is kept so blinding can be verified afterwards.
    """
    FRONTIER_CWD.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_path.resolve()  # the subprocess runs in FRONTIER_CWD
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    sys_file = transcript_path.with_suffix(".system.txt")
    sys_file.write_text(system, encoding="utf-8")
    cmd = [
        "claude", "-p", "--safe-mode", "--tools", "", "--model", FRONTIER,
        "--system-prompt-file", str(sys_file),
        "--output-format", "stream-json", "--verbose", "--no-session-persistence",
    ]
    last_err = ""
    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        proc = subprocess.run(
            cmd, input=user, capture_output=True, text=True, encoding="utf-8",
            cwd=FRONTIER_CWD, timeout=1800,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )
        wall = time.perf_counter() - started
        transcript_path.write_text(proc.stdout, encoding="utf-8")
        events = [json.loads(ln) for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        result = next((e for e in events if e.get("type") == "result"), None)
        if proc.returncode == 0 and result and result.get("subtype") == "success":
            init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
            tool_uses = [
                c for e in events if e.get("type") == "assistant"
                for c in e["message"].get("content", []) if c.get("type") == "tool_use"
            ]
            models = sorted({e["message"].get("model", "") for e in events if e.get("type") == "assistant"})
            usage = result.get("usage", {})
            return Reply(
                result.get("result", ""),
                {
                    "wall_seconds": round(wall, 2),
                    "attempts": attempt,
                    "init_model": init.get("model"),
                    "init_tools": init.get("tools"),
                    "tool_use_blocks": len(tool_uses),
                    "assistant_models": models,
                    "input_tokens": usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "thinking_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0),
                    "stop_reason": result.get("stop_reason"),
                    "blind": init.get("tools") == [] and not tool_uses,
                },
            )
        last_err = f"exit={proc.returncode} result={result and result.get('subtype')} stderr={proc.stderr[-400:]}"
        time.sleep(15 * attempt)
    raise RuntimeError(f"frontier call failed after {retries} attempts: {last_err}")
