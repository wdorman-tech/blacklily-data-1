"""Register Report No. 03: hash the pre-registration and every file the method depends on.

    python report03/ops/register.py

Refuses if the pre-registration is still marked DRAFT or if a registration already exists. After
this, nothing above Section 13 of preregistration.md changes; deviations are appended there.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
OUT = R3 / "ops" / "REGISTRATION.json"
FILES = [
    R3 / "preregistration.md", R3 / "ops" / "field_03.json", R3 / "ops" / "fit_03.json",
    R3 / "ops" / "control_03.json", R3 / "ops" / "gpu_queue_03.py", R3 / "src" / "build_results_03.py",
    R2 / "src" / "run.py", R2 / "src" / "common.py", R2 / "src" / "grade.py", R2 / "src" / "judge.py",
    R2 / "src" / "stats.py", R2 / "prompts" / "HASHES.json",
]


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"already registered at {json.loads(OUT.read_text())['registered_at']}")
    if "DRAFT" in (R3 / "preregistration.md").read_text(encoding="utf-8").split("## 1.")[0]:
        raise SystemExit("preregistration.md is still marked DRAFT")
    out = {"registered_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "sha256": {str(f.relative_to(R3.parent)).replace("\\", "/"): hashlib.sha256(f.read_bytes()).hexdigest()
                      for f in FILES}}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out["sha256"].items():
        print(f"{v[:16]}  {k}")


if __name__ == "__main__":
    main()
