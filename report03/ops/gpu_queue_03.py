"""Serial GPU job queue for Report No. 03. Each job is one report02/src/run.py invocation.

    python report03/ops/gpu_queue_03.py dev       # dev split, every field model, every task
    python report03/ops/gpu_queue_03.py control   # resident-versus-spilled control (gemma4:12b)
    python report03/ops/gpu_queue_03.py test      # test split, one run, gap tasks first, 10-hour ceiling

Runs land in report02/runs under each model's own slug, next to the frontier runs they pair with.
Finished items are skipped by run.py, and the time each model has spent is kept in
ops/queue_state.json, so the queue is safe to kill and restart. Touch ops/STOP to stop after the
current job. A model that reaches its ceiling is stopped mid-job and recorded as did-not-complete;
the items it finished stay on disk and are reported.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
PY = str(R3.parent / ".venv" / "Scripts" / "python.exe")
LOG = R3 / "logs" / "gpu_queue_03.log"
STATE = R3 / "ops" / "queue_state.json"
STOP = R3 / "ops" / "STOP"

# Shortest projected wall clock first, so an overrun costs the least (plan Section 10).
# gpt-oss:120b did not load usably (ops/fit_03.json); qwen3.6:35b-a3b replaced it (ops/field_03.json).
FIELD = ["gemma4:26b-a4b-it-q4_K_M", "qwen3.6:35b-a3b-q4_K_M", "qwen3.8:27b-q4_K_M", "gemma4:31b-it-q4_K_M"]
# Mandatory, no default: No. 02 lost ten runs to a thinking model spending its budget on reasoning.
# Thinking off matches No. 02's main arm; gpt-oss cannot turn reasoning off, so it runs at its lowest level.
THINK = {"gemma4:26b-a4b-it-q4_K_M": "off", "qwen3.6:35b-a3b-q4_K_M": "off", "qwen3.8:27b-q4_K_M": "off",
         "gemma4:31b-it-q4_K_M": "off", "gpt-oss:120b": "low", "gemma4:12b": "off"}
TASKS = ["t2", "t4", "t5", "t7", "t1", "t6", "t3"]  # the four No. 02 gap tasks first
T3_PACK = "t3_f04"  # registered: the pack whose No. 02 results sit closest to the full 120 items
# Set from the fit probe before registration: the slowest field model projects 8.35 h for its 127 items and the
# field 15.7 h in total, inside the plan's 12 to 20 GPU-hour budget. Ten hours lets every model finish every task.
CEILING_S = 10 * 3600
CONTROL_MODEL, CONTROL_GPU_LAYERS = "gemma4:12b", 24  # 48 blocks: half the layers leave graphics memory


def t3_pack_ids() -> str:
    sys.path.insert(0, str(R2 / "src"))
    from tasks import items_for  # noqa: PLC0415

    return ",".join(i.item_id for i in items_for("t3", "test") if i.item_id.startswith(T3_PACK + "."))


def job(model: str, task: str, split: str, *extra: str, run: str = "r1") -> list[str]:
    return ["src/run.py", "--task", task, "--model", model, "--split", split, "--run", run,
            "--think", THINK[model], *extra]


def plan(phase: str) -> list[tuple[str, list[str]]]:
    jobs: list[tuple[str, list[str]]] = []
    if phase == "dev":
        for m in FIELD:
            for t in TASKS:  # one item per task: the fit probe already confirmed each model answers
                jobs.append((m, job(m, t, "dev", "--limit", "1")))
    elif phase == "control":
        for t in ("t1", "t6"):
            jobs.append((CONTROL_MODEL, job(CONTROL_MODEL, t, "test", "--num-gpu", str(CONTROL_GPU_LAYERS))))
        jobs.append((CONTROL_MODEL, job(CONTROL_MODEL, "t3", "test", "--num-gpu", str(CONTROL_GPU_LAYERS),
                                        "--items", t3_pack_ids())))
        # Fresh resident rerun, so a spilled-versus-resident difference cannot be server or driver drift
        # since No. 02. Run id "ctl" keeps it out of No. 02's r1-r3 aggregates.
        jobs.append((CONTROL_MODEL, job(CONTROL_MODEL, "t1", "test", run="ctl")))
    elif phase == "test":
        for m in FIELD:
            for t in TASKS:
                extra = ["--items", t3_pack_ids()] if t == "t3" else []
                jobs.append((m, job(m, t, "test", *extra)))
    else:
        raise SystemExit(f"unknown phase {phase}")
    return jobs


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def unload_all() -> None:
    for m in httpx.get("http://127.0.0.1:11434/api/ps", timeout=30).json().get("models", []):
        httpx.post("http://127.0.0.1:11434/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=300)


def main() -> None:
    phase = sys.argv[1]
    jobs = plan(phase)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    spent = state.setdefault(phase, {}).setdefault("spent_s", {})
    dnc = state[phase].setdefault("did_not_complete", {})
    log(f"=== phase {phase}: {len(jobs)} jobs")
    current = None
    for n, (model, argv) in enumerate(jobs, 1):
        if STOP.exists():
            log("STOP file present, stopping before next job")
            return
        if model in dnc:
            continue
        # Unload whenever the model or its forced placement changes. Ollama reuses a loaded runner when a
        # request does not set num_gpu, so without this a "resident" job can silently run spilled.
        placement = (model, argv[argv.index("--num-gpu") + 1] if "--num-gpu" in argv else None)
        if placement != current:
            unload_all()
            current = placement
        budget = CEILING_S - spent.get(model, 0) if phase == "test" else None
        label = " ".join(argv[1:])
        log(f"[{n}/{len(jobs)}] start {label}" + (f" (budget {budget / 3600:.2f} h)" if budget else ""))
        started = time.time()
        try:
            proc = subprocess.run([PY, *argv], cwd=R2, capture_output=True, text=True, encoding="utf-8",
                                  timeout=budget, check=False)
            tail = (proc.stdout or "").strip().splitlines()[-2:] + (proc.stderr or "").strip().splitlines()[-3:]
            outcome = f"exit {proc.returncode}: {' | '.join(tail)[:600]}"
        except subprocess.TimeoutExpired:
            dnc[model] = {"task": argv[2], "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "reason": "reached the ten-hour ceiling on the reference machine"}
            outcome = "CEILING reached, model recorded as did not complete"
            unload_all()
        elapsed = time.time() - started
        if phase == "test":
            spent[model] = spent.get(model, 0) + elapsed
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
        log(f"[{n}/{len(jobs)}] {outcome} in {elapsed:.0f}s")
    unload_all()
    log(f"=== phase {phase} done")


if __name__ == "__main__":
    main()
