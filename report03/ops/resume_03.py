"""Unattended tail of Report No. 03: finish the test queue, then grade, judge and build results.

    python report03/ops/resume_03.py

Scheduled for 2026-09-24 00:00 after the test split was paused
for the GPU's owner. Every step is resumable, so running this twice is harmless. Log: logs/resume_03.log.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
PY = str(R3.parent / ".venv" / "Scripts" / "python.exe")
LOG = R3 / "logs" / "resume_03.log"
sys.path.insert(0, str(R2 / "src"))
sys.path.insert(0, str(R3 / "ops"))
from common import model_slug  # noqa: E402
from gpu_queue_03 import FIELD, TASKS  # noqa: E402


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def step(argv: list[str], cwd: Path) -> None:
    log("run " + " ".join(argv[:4]) + (" ..." if len(argv) > 4 else ""))
    proc = subprocess.run([PY, *argv], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False)
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-3:]
    log(f"exit {proc.returncode}: {' | '.join(tail)[:500]}")


def run_dirs() -> list[str]:
    dirs = []
    for m in FIELD:
        for t in TASKS:
            d = R2 / "runs" / model_slug(m) / t / "test-default-thinkoff-ctx16384-r1"
            if (d / "_manifest.json").exists():
                dirs.append(str(d.relative_to(R2)))
    return dirs


def main() -> None:
    try:
        httpx.get("http://127.0.0.1:11434/api/version", timeout=10).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log(f"Ollama server not reachable ({exc}); start it with report02/ops/ollama-serve.cmd and rerun")
        raise SystemExit(1) from exc
    step(["ops/gpu_queue_03.py", "test"], R3)
    dirs = run_dirs()
    step(["src/grade.py", *dirs], R2)
    step(["src/judge.py", "absolute", *dirs], R2)
    step(["src/build_results_03.py"], R3)
    log("resume_03 done")


if __name__ == "__main__":
    main()
