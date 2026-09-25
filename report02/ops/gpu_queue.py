"""Serial GPU job queue for every local run in Report No. 02.

One GPU, so local jobs run one at a time, in a fixed order, each a src/run.py (or
src/t3_mapreduce.py) invocation. Finished items inside a job are skipped by run.py itself,
so the queue is safe to kill and restart. Touch ops/STOP to stop after the current job.

    python ops/gpu_queue.py dev        # dev pilot, one run per model per task
    python ops/gpu_queue.py test       # test split: r1 for everything, then r2, then r3
    python ops/gpu_queue.py config     # configuration experiments
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT.parent / ".venv" / "Scripts" / "python.exe")
LOG = ROOT / "logs" / "gpu_queue.log"
STOP = ROOT / "ops" / "STOP"

MAIN = ["gemma4:12b", "qwen3.5:9b", "qwen2.5:14b-instruct-q4_K_M"]
# Both current models ship with thinking on. At num_ctx 16384 with these documents the thinking
# tokens consume the whole generation budget and the model returns nothing (measured on dev), so
# the main comparison runs them with thinking off; thinking on is a configuration arm.
THINK = {"gemma4:12b": "off", "qwen3.5:9b": "off", "qwen3.5:9b-q8_0": "off"}
OPTIONAL = ["ministral-3:14b"]
SIZE = "qwen2.5:7b-instruct-q4_K_M"
TASKS = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]


def plan(phase: str) -> list[list[str]]:
    jobs: list[list[str]] = []
    if phase == "dev":
        for m in MAIN:
            for t in TASKS:
                jobs.append(["src/run.py", "--task", t, "--model", m, "--split", "dev", "--run", "r1"])
    elif phase == "test":
        fit = json.loads((ROOT / "ops" / "fit.json").read_text()) if (ROOT / "ops" / "fit.json").exists() else {}
        models = MAIN + [m for m in OPTIONAL if fit.get(m, {}).get("fully_on_gpu")]
        for run in ("r1", "r2", "r3"):
            for t in TASKS:
                for m in models:
                    jobs.append(["src/run.py", "--task", t, "--model", m, "--split", "test", "--run", run,
                                 "--think", THINK.get(m, "auto")])
        for t in TASKS:
            jobs.append(["src/run.py", "--task", t, "--model", SIZE, "--split", "test", "--run", "r1"])
    elif phase == "config":
        # Every config job carries the same thinking setting as the main arm. Without it a
        # thinking-capable model spends its generation budget on reasoning tokens and the arm
        # measures thinking mode rather than the setting under test.
        def cfg(model: str, *args: str) -> list[str]:
            return ["src/run.py", "--model", model, "--split", "test", "--run", "r1",
                    "--think", THINK.get(model, "auto"), *args]

        for m in ("qwen2.5:14b-instruct-q4_K_M", "gemma4:12b"):
            for ctx in ("2048", "4096", "8192", "32768"):
                jobs.append(cfg(m, "--task", "t1", "--num-ctx", ctx))
        for ctx in ("4096", "8192", "16384", "32768"):
            jobs.append(cfg("gemma4:12b", "--task", "t3", "--variant", "fullpack", "--num-ctx", ctx))
        jobs.append(["src/t3_mapreduce.py", "--model", "gemma4:12b", "--split", "test", "--run", "r1", "--think", "off"])
        jobs.append(cfg("qwen2.5:14b-instruct-q4_K_M", "--task", "t1", "--variant", "oob", "--num-ctx", "0"))
        jobs.append(cfg("qwen2.5:14b-instruct-q4_K_M", "--task", "t1", "--variant", "naive"))
        jobs.append(cfg("qwen2.5:14b-instruct-q4_K_M", "--task", "t1", "--variant", "nojson"))
        for t in ("t1", "t3"):
            jobs.append(cfg("qwen3.5:9b-q8_0", "--task", t))
            for th in ("on", "off"):
                jobs.append(["src/run.py", "--task", t, "--model", "qwen3.5:9b", "--split", "test", "--run", "r1", "--think", th])
    else:
        raise SystemExit(f"unknown phase {phase}")
    return jobs


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    phase = sys.argv[1]
    jobs = plan(phase)
    log(f"=== phase {phase}: {len(jobs)} jobs")
    for n, job in enumerate(jobs, 1):
        if STOP.exists():
            log("STOP file present, stopping before next job")
            return
        label = " ".join(job[1:])
        log(f"[{n}/{len(jobs)}] start {label}")
        started = time.time()
        proc = subprocess.run([PY, *job], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        tail = (proc.stdout or "").strip().splitlines()[-2:] + (proc.stderr or "").strip().splitlines()[-3:]
        log(f"[{n}/{len(jobs)}] exit {proc.returncode} in {time.time() - started:.0f}s: {' | '.join(tail)[:600]}")
    log(f"=== phase {phase} done")


if __name__ == "__main__":
    main()
