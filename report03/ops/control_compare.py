"""Resident-versus-spilled control: compare gemma4:12b's spilled outputs with No. 02's resident run 1.

    python report03/ops/control_compare.py

Per task: the share of items whose output is byte-identical, how many differing items change
their graded counts, and the primary and hallucination metric on each side, both after
adjudication (the published grading) and on the regex grader alone (which needs no judge call,
so it is a like-for-like check even before the spilled run is adjudicated).
Grades the spilled runs first if they have no _grades.json. Writes report03/ops/control_03.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
sys.path.insert(0, str(R2 / "src"))
from stats import PRIMARY_KINDS, load_run, metric  # noqa: E402

BASE = R2 / "runs" / "gemma4-12b"
RESIDENT = "test-default-thinkoff-ctx16384-r1"
SPILLED = "test-default-thinkoff-gpu24-ctx16384-r1"


def regex_primary(run_dir: Path, task: str, ids: list[str]) -> float:
    items = json.loads((run_dir / "_grades.json").read_text(encoding="utf-8"))["items"]
    units = [u for i in ids for u in items[i]["units"] if u["kind"] in PRIMARY_KINDS[task]]
    return round(100 * sum(u["score"] for u in units) / len(units), 1) if units else float("nan")


def main() -> None:
    out: dict = {"resident": RESIDENT, "spilled": SPILLED, "tasks": {}}
    for task in ("t1", "t6", "t3"):
        res, spl = BASE / task / RESIDENT, BASE / task / SPILLED
        if not spl.exists():
            continue
        subprocess.run([str(R3.parent / ".venv" / "Scripts" / "python.exe"), "src/grade.py", str(spl)],
                       cwd=R2, check=True, capture_output=True)
        a, b = load_run(res), load_run(spl)
        ids = sorted(b.items)
        same, differ = 0, []
        for item in ids:
            if (res / f"{item}.raw.txt").read_bytes() == (spl / f"{item}.raw.txt").read_bytes():
                same += 1
            else:
                graded = [k for k in a.items[item]["counts"] if k != "words"]  # length is not a grade
                differ.append({"item": item, "counts_differ": any(a.items[item]["counts"].get(k) != b.items[item]["counts"].get(k)
                                                                   for k in graded)})
        loaded = json.loads((spl / "_manifest.json").read_text(encoding="utf-8")).get("loaded", {})
        row = {
            "items": len(ids), "identical": same, "differ": differ,
            "spill_fraction": round(1 - loaded["size_vram_bytes"] / loaded["size_bytes"], 4),
            "adjudicated_spilled": (spl / "_judge").exists(),
            "resident": {m: metric([a], m, ids)["mean"] for m in ("primary", "halluc")},
            "spilled": {m: metric([b], m, ids)["mean"] for m in ("primary", "halluc")},
            "regex_only_primary": {"resident": regex_primary(res, task, ids), "spilled": regex_primary(spl, task, ids)},
        }
        out["tasks"][task] = row
        print(f"{task}: {same}/{len(ids)} identical, {sum(d['counts_differ'] for d in differ)} change counts; "
              f"primary {row['resident']['primary']} -> {row['spilled']['primary']} "
              f"(regex only {row['regex_only_primary']['resident']} -> {row['regex_only_primary']['spilled']}), "
              f"halluc {row['resident']['halluc']} -> {row['spilled']['halluc']}, spill {row['spill_fraction']}, "
              f"adjudicated={row['adjudicated_spilled']}")
    fresh = BASE / "t1" / "test-default-thinkoff-ctx16384-ctl"
    if fresh.exists():
        pairs = [(r, BASE / "t1" / RESIDENT / r.name) for r in sorted(fresh.glob("*.raw.txt"))]
        same = sum(x.read_bytes() == y.read_bytes() for x, y in pairs)
        out["resident_rerun_t1"] = {"items": len(pairs), "identical_to_no02_r1": same}
        print(f"fresh resident rerun t1: {same}/{len(pairs)} identical to No. 02 run 1")
    (R3 / "ops" / "control_03.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
