"""Freeze the prompts before the first test-split run (pre-registration section 5).

Writes prompts/HASHES.json: the sha256 of every prompt file, of No. 01's schema.py (the T1
prompt source), and of each task's rendered system prompt. src/run.py refuses to run the
test split unless the current files match.

    python ops/freeze_prompts.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from common import sha256  # noqa: E402
from tasks import TASKS, load_prompt  # noqa: E402


def current() -> dict:
    files = {p.name: sha256(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "prompts").glob("*.py"))}
    files["no1_schema.py"] = sha256((ROOT.parent / "src" / "schema.py").read_text(encoding="utf-8"))
    systems = {t: sha256(load_prompt(t).SYSTEM) for t in TASKS}
    return {"files": files, "systems": systems}


def main() -> None:
    out = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **current()}
    (ROOT / "prompts" / "HASHES.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
