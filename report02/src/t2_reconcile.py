"""Reconcile the two blind materiality labels on each real T2 pair into the key.

Both labelers say material: material. Both say minor: not material. They disagree:
contested, excluded from the recall denominator, and listed in review/ for a human decision.
Reports Cohen's kappa for the two labelers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KEYS, ROOT, read, write_json  # noqa: E402


def kappa(pairs: list[tuple[bool, bool]]) -> float:
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main() -> None:
    all_pairs: dict[str, list[tuple[bool, bool]]] = {"dev": [], "test": []}
    contested = []
    for kp in sorted((KEYS / "t2").glob("t2_*.json")):
        key = json.loads(read(kp))
        if key.get("source") != "sec_edgar_10k_item_1a":
            continue
        la = {x["aid"]: x for x in json.loads(read(KEYS / "t2" / "_labels" / f"{key['pair_id']}.A.json"))["labels"]}
        lb = {x["aid"]: x for x in json.loads(read(KEYS / "t2" / "_labels" / f"{key['pair_id']}.B.json"))["labels"]}
        for s in key["sections"]:
            a, b = la.get(s["aid"], {}), lb.get(s["aid"], {})
            s["description"] = a.get("description") or b.get("description", "")
            if s["status"] != "modified":
                continue
            ma, mb = a.get("material"), b.get("material")
            if ma is None or mb is None:
                raise SystemExit(f"{key['pair_id']} {s['aid']}: missing label (A={ma}, B={mb})")
            all_pairs[key["split"]].append((bool(ma), bool(mb)))
            s["labels"] = {"A": {"material": ma, "rationale": a.get("rationale", "")},
                           "B": {"material": mb, "rationale": b.get("rationale", "")}}
            if ma == mb:
                s["material"] = bool(ma)
            else:
                s["material"] = "contested"
                contested.append({"pair_id": key["pair_id"], "split": key["split"], "aid": s["aid"],
                                  "heading": s["current_heading"], "diff": s["diff"],
                                  "A": s["labels"]["A"], "B": s["labels"]["B"],
                                  "description_A": a.get("description", ""), "description_B": b.get("description", "")})
        write_json(kp, key)
    stats = {}
    for split, pairs in all_pairs.items():
        agree = sum(a == b for a, b in pairs)
        stats[split] = {"modified_sections": len(pairs), "agreement": agree,
                        "agreement_pct": round(100 * agree / max(1, len(pairs)), 1),
                        "kappa": round(kappa(pairs), 3),
                        "both_material": sum(a and b for a, b in pairs),
                        "both_minor": sum((not a) and (not b) for a, b in pairs)}
    write_json(ROOT / "review" / "t2_materiality_contested.json", {"stats": stats, "contested": contested})
    print(json.dumps(stats, indent=1))
    print(f"{len(contested)} contested sections written to review/t2_materiality_contested.json")


if __name__ == "__main__":
    main()
