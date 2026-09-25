"""Mechanical checks on the synthetic corpus and every key, run before any test-split run.

  1. No em or en dashes in any synthetic document or key.
  2. Word counts inside each spec's range.
  3. Key self-tests: every expected value matches its own accept patterns and no reject
     pattern; every quote or span appears verbatim in its document.
  4. Every invented entity name is searched on SEC EDGAR (company names) and on the IAPD
     adviser search. Any hit is written to review/ for a human decision.

    python src/qa_corpus.py [--names]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx  # noqa: E402

from common import CORPUS, KEYS, ROOT, normalize, read, write_json  # noqa: E402
from edgar import USER_AGENT  # noqa: E402

FL = re.IGNORECASE | re.DOTALL
DASHES = re.compile("[—–]")
RANGES = {  # (min, max) words per synthetic document, from the specs
    "t1": (3500, 6100), "t1_d11": (8300, 8900), "t2": (2700, 3400), "t5": (4200, 5800),
    "t6": (300, 520), "t7": (350, 900),
    "01_brochure.md": (4300, 5300), "02_compliance_manual.md": (4300, 5300),
    "03_valuation_policy.md": (1700, 2400), "04_business_continuity_plan.md": (1700, 2400),
    "05_fee_schedule.md": (600, 1000), "06_policy_update_memo.md": (700, 1200),
}


def synthetic_docs() -> list[Path]:
    out = []
    for task in ("t1", "t3", "t5", "t6", "t7"):
        out += sorted((CORPUS / task).rglob("*.md"))
    out += sorted(p for p in (CORPUS / "t2").rglob("*.md") if re.search(r"t2_s\d+", str(p)))
    return out


def word_range(p: Path) -> tuple[int, int] | None:
    task = p.relative_to(CORPUS).parts[0]
    if task == "t1":
        return RANGES["t1_d11"] if p.stem == "t1_d11" else RANGES["t1"]
    if task == "t3":
        return RANGES.get(p.name)
    return RANGES.get(task)


def m(pats: list[str], text: str) -> bool:
    return any(re.search(p, text, FL) for p in pats or [])


def self_test_keys() -> list[str]:
    problems: list[str] = []
    for kp in sorted((KEYS / "t1").glob("*.json")):
        k = json.loads(read(kp))
        doc = next(CORPUS.glob(f"t1/*/{k['doc_id']}.md"), None)
        dn = normalize(read(doc)) if doc else ""
        for f, spec in k["fields"].items():
            e = normalize(spec["expected"])
            if not m(spec.get("accept", []), e):
                problems.append(f"{kp.name}:{f}: expected does not match accept")
            for kind, pats in (spec.get("reject") or {}).items():
                if m(pats, e):
                    problems.append(f"{kp.name}:{f}: expected matches reject {kind}")
            q = normalize(spec.get("quote", ""))
            if q and q not in dn:
                problems.append(f"{kp.name}:{f}: quote not verbatim")
        if len(k["fields"]) != 20:
            problems.append(f"{kp.name}: {len(k['fields'])} fields, not 20")
    for kp in sorted((KEYS / "t3").glob("t3_f*.json")):
        k = json.loads(read(kp))
        firm = next(CORPUS.glob(f"t3/*/{k['firm_id']}"), None)
        docs = {p.name: normalize(read(p)) for p in firm.glob("*.md")} if firm else {}
        if len(k["questions"]) != 40:
            problems.append(f"{kp.name}: {len(k['questions'])} questions, not 40")
        for q in k["questions"]:
            e = normalize(q["expected"])
            if not m(q.get("accept", []), e):
                problems.append(f"{kp.name}:{q['qid']}: expected does not match accept")
            for kind, pats in (q.get("reject") or {}).items():
                if m(pats, e):
                    problems.append(f"{kp.name}:{q['qid']}: expected matches reject {kind}")
            if q["answerable"]:
                src = docs.get(q.get("source_document", ""), "")
                if normalize(q.get("quote", "")) not in src:
                    problems.append(f"{kp.name}:{q['qid']}: quote not verbatim in {q.get('source_document')}")
    for kp in sorted((KEYS / "t7").glob("*.json")):
        k = json.loads(read(kp))
        doc = next(CORPUS.glob(f"t7/*/{k['piece_id']}.md"), None)
        dn = normalize(read(doc)) if doc else ""
        for x in k["planted"] + k.get("decoys", []):
            if normalize(x["span"]) not in dn:
                problems.append(f"{kp.name}:{x.get('iid') or x.get('did')}: span not verbatim")
    for kp in sorted((KEYS / "t6").glob("*.json")):
        k = json.loads(read(kp))
        doc = next(CORPUS.glob(f"t6/*/{k['sheet_id']}.md"), None)
        if doc and normalize(k["disclosure"]) not in normalize(read(doc)):
            problems.append(f"{kp.name}: disclosure not verbatim in sheet")
    for kp in sorted((KEYS / "t4").glob("t4_*.json")):
        k = json.loads(read(kp))
        doc = next(CORPUS.glob(f"t4/*/{k['doc_id']}.md"), None)
        dn = normalize(read(doc)) if doc else ""
        if len(k["facts"]) != 10:
            problems.append(f"{kp.name}: {len(k['facts'])} facts, not 10")
        for f in k["facts"]:
            if normalize(f["quote"]) not in dn:
                problems.append(f"{kp.name}:{f['fid']}: quote not verbatim")
    return problems


ENTITY = re.compile(
    r"\b((?:[A-Z][a-z]+[a-z'\-]*\s+){1,4}?)(?:&\s+[A-Z][a-z]+\s+)?"
    r"(LLP|LLC|L\.P\.|Ltd\.|Limited|Inc\.|Partners|Capital|Management|Advisors|Advisers|Fund Services|"
    r"Securities|Trust Company|Bank|Group|Wealth|Asset Management|Associates)\b")
STOP = {"The", "This", "Each", "Such", "Any", "No", "All", "General", "Limited", "Investment", "Fund",
        "Master", "Feeder", "Class", "Section", "Appendix", "Supplement", "Chief", "Senior", "Managing",
        "Independent", "Prime", "Key", "Advisory", "Delaware", "Cayman", "New", "United", "States", "Our",
        "Your", "Private", "Registered", "Plan", "Partnership", "Company", "Manager", "Adviser", "Firm"}


def entity_cores(texts: list[str]) -> set[str]:
    cores = set()
    for t in texts:
        for mt in ENTITY.finditer(t):
            words = [w for w in mt.group(1).split() if w not in STOP]
            if len(words) >= 1 and all(w[0].isupper() for w in words):
                core = " ".join(words[:2])
                if len(core) >= 5:
                    cores.add(core)
    return cores


def edgar_hits(client: httpx.Client, core: str) -> list[str]:
    """EDGAR entity names containing the invented core name (EDGAR's own entity index)."""
    r = client.get("https://efts.sec.gov/LATEST/search-index", params={"keysTyped": core})
    try:
        hits = r.json().get("hits", {}).get("hits", [])
    except ValueError:
        return []
    names = [h.get("_source", {}).get("entity", "") for h in hits]
    return [n for n in names if core.lower() in n.lower()][:10]


def iapd_hits(client: httpx.Client, core: str) -> list[str]:
    r = client.get("https://api.adviserinfo.sec.gov/search/firm",
                   params={"query": core, "hl": "true", "nrows": "12", "start": "0", "r": "25",
                           "sort": "score+desc", "wt": "json"})
    try:
        hits = r.json().get("hits", {}).get("hits", [])
    except ValueError:
        return []
    names = [h.get("_source", {}).get("firm_name", "") for h in hits]
    return [n for n in names if core.lower() in n.lower()][:10]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", action="store_true", help="also search EDGAR and IAPD for every invented name")
    args = ap.parse_args()
    report: dict = {"dashes": [], "word_counts": [], "key_problems": [], "name_hits": {}}
    docs = synthetic_docs()
    for p in docs + sorted(KEYS.rglob("*.json")):
        if p.suffix == ".json" and ("_labels" in p.parts or p.parent.name == "t4" or "t2_" in p.name and "_s" not in p.name):
            continue  # real-document keys quote filings verbatim, dashes included
        if DASHES.search(read(p)):
            report["dashes"].append(str(p.relative_to(ROOT)))
    for p in docs:
        rng = word_range(p)
        n = len(read(p).split())
        if rng and not (rng[0] <= n <= rng[1]):
            report["word_counts"].append(f"{p.relative_to(CORPUS)}: {n} words, spec {rng[0]}-{rng[1]}")
    report["key_problems"] = self_test_keys()
    if args.names:
        cores = sorted(entity_cores([read(p) for p in docs]))
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True) as c:
            for core in cores:
                try:
                    e, i = edgar_hits(c, core), iapd_hits(c, core)
                except httpx.HTTPError as exc:
                    e, i = [f"error {exc}"], []
                if e or i:
                    report["name_hits"][core] = {"edgar": e, "iapd": i}
                time.sleep(0.3)
        report["names_checked"] = len(cores)
    write_json(ROOT / "review" / "qa_corpus.json", report)
    for k in ("dashes", "word_counts", "key_problems"):
        print(f"{k}: {len(report[k])}")
        for x in report[k][:40]:
            print("   ", x)
    if args.names:
        print(f"names checked: {report['names_checked']}, with hits: {len(report['name_hits'])}")
        for core, h in list(report["name_hits"].items())[:60]:
            print(f"    {core}: EDGAR {h['edgar'][:3]} IAPD {h['iapd'][:3]}")


if __name__ == "__main__":
    main()
