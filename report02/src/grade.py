"""Deterministic graders for every task, plus hooks for the judged parts.

Each grader returns, per item, a list of graded units. A unit is the thing a metric counts
(a field, a key change, a question, a key fact, an action item, a required fact, a planted
issue). Every unit carries: uid, score (0, 0.5, 1), verdict, error_kind, and flags used by
the trap and hallucination metrics. Aggregation lives in stats.py.

    python src/grade.py runs/<model>/<task>/<run_dir>
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KEYS, NO1, extract_json, normalize, quote_grounded, read, write_json  # noqa: E402
from numbers_ground import ground_numbers  # noqa: E402
from t2_blocks import heading_key, norm, split_markdown  # noqa: E402

_g1_spec = importlib.util.spec_from_file_location("no1_grade", NO1 / "src" / "grade.py")
no1 = importlib.util.module_from_spec(_g1_spec)  # type: ignore[arg-type]
sys.modules["no1_grade"] = no1  # dataclasses in No. 01's grader look themselves up here
_g1_spec.loader.exec_module(no1)  # type: ignore[union-attr]

FLAGS = re.IGNORECASE | re.DOTALL


def any_match(patterns: list[str], text: str) -> str | None:
    for p in patterns or []:
        if re.search(p, text, FLAGS):
            return p
    return None


def reject_kind(rejects: dict, text: str) -> str | None:
    for kind, pats in (rejects or {}).items():
        if any_match(pats, text):
            return kind
    return None


@dataclass
class Unit:
    uid: str
    score: float
    verdict: str  # CORRECT PARTIAL WRONG MISSING HALLUCINATION STALE ABSTAINED FABRICATED ...
    kind: str = ""  # unit type within the task
    error_kind: str | None = None
    trap: str = "none"
    hallucination: bool = False
    got: str = ""
    expected: str = ""
    extra: dict = field(default_factory=dict)


# --- T1 --------------------------------------------------------------------------------------


def grade_t1(item_id: str, raw: str, meta: dict) -> dict:
    from tasks import t1_key  # local import: tasks imports common only

    key = t1_key(item_id)
    doc_raw = read(Path(meta["meta"]["doc_path"]))
    doc_norm = no1.normalize(doc_raw)
    index = no1.build_heading_index(doc_raw)
    parsed, problems = extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}
    units = []
    for name, spec in key["fields"].items():
        entry = parsed.get(name) or {}
        if isinstance(entry, str):
            entry = {"value": entry}
        if not isinstance(entry, dict):
            entry = {}
        got = str(entry.get("value", "") or "").strip()
        got_norm = no1.normalize(got)
        trap = spec.get("trap_type") or (
            "absence" if spec.get("absence_test") else "supersession" if spec.get("supersession_test") else "none")
        if key["doc_id"] in no1_trap_map() and name in no1_trap_map()[key["doc_id"]]:
            trap = no1_trap_map()[key["doc_id"]][name]
        if not got_norm:
            units.append(Unit(name, 0.0, "MISSING", "field", "no_value", trap, False, got, spec["expected"]))
            continue
        score, verdict, err = 0.0, "WRONG", None
        if no1.matches_any(spec.get("accept", []), got_norm):
            score, verdict = 1.0, "CORRECT"
        elif no1.matches_any(spec.get("partial", []), got_norm):
            score, verdict, err = 0.5, "PARTIAL", "incomplete"
        if verdict != "CORRECT":
            for kind, pats in (spec.get("reject") or {}).items():
                if no1.matches_any(pats, got_norm):
                    err = kind
                    if verdict == "WRONG":
                        verdict = ("HALLUCINATION" if kind.upper().startswith("HALLUCINATED")
                                   else "STALE" if kind.upper().startswith("STALE") else "WRONG")
                    break
        if spec.get("absence_test") and verdict in {"WRONG", "PARTIAL"}:
            verdict, score = "HALLUCINATION", 0.0
        units.append(Unit(
            name, score, verdict, "field", err, trap, verdict == "HALLUCINATION", got, spec["expected"],
            {"citation_valid": no1.citation_is_valid(str(entry.get("citation", "")), index),
             "quote_grounded": no1.quote_is_grounded(str(entry.get("quote", "")), doc_norm)},
        ))
    return {"units": [asdict(u) for u in units], "parse_problems": problems}


_NO1_TRAPS: dict | None = None


def no1_trap_map() -> dict:
    """Trap categories for No. 01's documents, whose keys predate trap_type."""
    global _NO1_TRAPS
    if _NO1_TRAPS is None:
        _NO1_TRAPS = {}
        for d in ("doc1_meridian_ridge", "doc2_calder_wyeth", "doc3_ashgrove"):
            k = json.loads(read(NO1 / "ground_truth" / f"{d}.json"))
            m = {}
            for name, spec in k["fields"].items():
                if spec.get("absence_test"):
                    m[name] = "absence"
                elif spec.get("supersession_test"):
                    m[name] = "supersession"
            _NO1_TRAPS[d] = m
    return _NO1_TRAPS


# --- T2 --------------------------------------------------------------------------------------


def _t2_sections(pair_dir: Path) -> tuple[list, list]:
    return split_markdown(read(pair_dir / "prior.md")), split_markdown(read(pair_dir / "current.md"))


def _locate(change: dict, prior: list, current: list) -> tuple[str, object | None, str]:
    """Find which section a reported change points at: by quote first, then heading."""
    q = norm(str(change.get("quote", "")))
    ctype = str(change.get("type", "")).lower().strip()
    order = [("prior", prior), ("current", current)] if ctype == "removed" else [("current", current), ("prior", prior)]
    # 1. The heading the prompt asks for, when it names a section almost exactly.
    h = heading_key(str(change.get("heading", "")))
    best_h, best_hs, best_hside = None, 0.0, ""
    if h:
        for side, secs in order:
            for s in secs:
                sc = SequenceMatcher(None, h, heading_key(s.heading)).ratio()
                if sc > best_hs:
                    best_h, best_hs, best_hside = s, sc, side
    if best_h is not None and best_hs >= 0.9:
        return best_hside, best_h, "heading"
    # 2. The section holding the most of the quote (8-word windows), so shared boilerplate
    #    in a neighbouring section does not capture the report.
    if len(q) >= 20:
        words = q.split()
        probes = [q] + [" ".join(words[i:i + 8]) for i in range(0, max(1, len(words) - 7), 2)]
        best_q, best_hits, best_qside = None, 0, ""
        for side, secs in order:
            for s in secs:
                body = norm(s.text)
                hits = sum(1 for pr in probes if pr and pr in body)
                if hits > best_hits:
                    best_q, best_hits, best_qside = s, hits, side
        if best_q is not None:
            return best_qside, best_q, "quote"
    # 3. A looser heading match.
    if best_h is not None and best_hs >= 0.8:
        return best_hside, best_h, "heading_fuzzy"
    return "", None, "unlocated"


def grade_t2(item_id: str, raw: str, meta: dict) -> dict:
    """Units: one per key section that changed (recall), plus one per reported change (precision)."""
    pair_dir = Path(meta["meta"]["pair_path"])
    key = json.loads(read(KEYS / "t2" / f"{item_id}.json"))
    prior, current = _t2_sections(pair_dir)
    sections = t2_key_sections(key, prior, current)
    parsed, problems = extract_json(raw)
    changes = parsed.get("changes", []) if isinstance(parsed, dict) else []
    changes = [c for c in changes if isinstance(c, dict)]

    by_prior = {s["prior_heading"]: s for s in sections if s["prior_heading"]}
    by_current = {s["current_heading"]: s for s in sections if s["current_heading"]}
    hit: dict[str, list] = {}
    reported = []
    for n, c in enumerate(changes):
        side, sec, how = _locate(c, prior, current)
        ks = None
        if sec is not None:
            ks = (by_current if side == "current" else by_prior).get(sec.heading)
        if ks is None:
            verdict, halluc = "FABRICATED", True  # points at nothing in either version
        elif ks["status"] in {"unchanged", "moved"}:
            verdict, halluc = "INVENTED_CHANGE", True
        else:
            verdict, halluc = "REAL_CHANGE", False
            hit.setdefault(ks["aid"], []).append(n)
        loc_ok = bool(ks) and SequenceMatcher(
            None, heading_key(str(c.get("heading", ""))),
            heading_key(ks["current_heading"] or ks["prior_heading"])).ratio() >= 0.75
        reported.append(Unit(
            f"reported_{n + 1:02d}", 0.0 if halluc else 1.0, verdict, "reported", None,
            ks["status"] if ks else "none", halluc, str(c.get("description", ""))[:400],
            (ks or {}).get("current_heading") or (ks or {}).get("prior_heading", ""),
            {"located_by": how, "type_reported": c.get("type"), "location_correct": loc_ok,
             "material": (ks or {}).get("material"), "duplicate": bool(ks) and len(hit.get((ks or {}).get("aid", ""), [])) > 1},
        ))

    recall = []
    for s in sections:
        if s["status"] in {"unchanged", "moved"} or s.get("material") is not True:
            continue
        found = s["aid"] in hit
        trap = s["status"] if s["status"] in {"added", "removed"} else ("subtle" if s.get("subtle") else "modified")
        recall.append(Unit(
            s["aid"], 1.0 if found else 0.0, "DETECTED" if found else "MISSED", "material_change",
            None if found else "missed", trap, False, "", s.get("description", ""),
        ))
    return {"units": [asdict(u) for u in recall + reported], "parse_problems": problems,
            "n_reported": len(changes), "contested": sum(1 for s in sections if s.get("material") == "contested")}


def t2_key_sections(key: dict, prior: list, current: list) -> list[dict]:
    """Normalize real (alignment-based) and synthetic (author-listed) keys to one shape."""
    if "sections" in key:  # real 10-K pair: alignment plus reconciled labels
        return key["sections"]
    from t2_blocks import align

    out = []
    listed = {}
    for ch in key["changes"]:
        for h in (ch.get("prior_heading"), ch.get("current_heading")):
            if h:
                listed[heading_key(h)] = ch
    for i, a in enumerate(align(prior, current), 1):
        h = heading_key((a.current or a.prior).heading)
        ch = listed.get(h)
        status = a.status
        material = False if status in {"unchanged", "moved"} else True
        if ch is not None:
            material = bool(ch.get("material")) and ch.get("type") not in {"minor", "moved"}
            if ch.get("type") == "minor":
                status = "modified"
        out.append({"aid": f"a{i:02d}", "status": status,
                    "prior_heading": a.prior.heading if a.prior else "",
                    "current_heading": a.current.heading if a.current else "",
                    "material": material if status not in {"unchanged", "moved"} else False,
                    "description": (ch or {}).get("description", ""),
                    "subtle": bool((ch or {}).get("subtle"))})
    return out


# --- T3 --------------------------------------------------------------------------------------

ABSTAIN_RX = re.compile(
    r"not_in_documents|not\s+in\s+(the\s+)?documents|not\s+(stated|specified|addressed|provided|disclosed|included|found)"
    r"|(is|are)n't\s+(stated|specified|addressed|provided|disclosed|included|found)"
    r"|(do|does|did)\s+not\s+(state|specify|address|say)|(do|does|did)n't\s+(state|specify|address|say)"
    r"|no\s+information", re.I)
# The subset of ABSTAIN_RX that can only mean "the documents lack the answer". A bare "not included"
# or "not provided" is also how a correct answer states a fact ("unfunded commitments are not
# included"), so on an answerable question an accept match overrides those, but never these.
DOC_ABSTAIN_RX = re.compile(
    r"not_in_documents|not\s+in\s+(the\s+)?(provided\s+)?documents|no\s+information"
    r"|(do|does|did)\s+not\s+(state|specify|address|say)|(do|does|did)n't\s+(state|specify|address|say)", re.I)


def grade_t3(item_id: str, raw: str, meta: dict) -> dict:
    firm, qid = item_id.split(".", 1)
    key = json.loads(read(KEYS / "t3" / f"{firm}.json"))
    q = next(x for x in key["questions"] if x["qid"] == qid)
    parsed, problems = extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}
    ans = str(parsed.get("answer", "") or "").strip()
    a_norm = normalize(ans)
    abstained = bool(ABSTAIN_RX.search(a_norm)) and len(a_norm.split()) <= 25
    if abstained and q["answerable"] and any_match(q.get("accept"), a_norm) and not DOC_ABSTAIN_RX.search(a_norm):
        abstained = False
    trap = q.get("trap", "none")
    if not a_norm:
        u = Unit(qid, 0.0, "MISSING", "question", "no_answer", trap, False, ans, q["expected"])
    elif not q["answerable"]:
        if abstained:
            u = Unit(qid, 1.0, "ABSTAINED", "question", None, trap, False, ans, q["expected"])
        else:
            u = Unit(qid, 0.0, "FABRICATED", "question", reject_kind(q.get("reject"), a_norm) or "answered_unanswerable",
                     trap, True, ans, q["expected"])
    elif abstained:
        u = Unit(qid, 0.0, "FALSE_ABSTAIN", "question", "abstained_on_answerable", trap, False, ans, q["expected"])
    elif any_match(q.get("accept"), a_norm):
        u = Unit(qid, 1.0, "CORRECT", "question", None, trap, False, ans, q["expected"])
    else:
        rk = reject_kind(q.get("reject"), a_norm)
        partial = any_match(q.get("partial"), a_norm)
        if rk and rk.upper().startswith("STALE"):
            u = Unit(qid, 0.0, "STALE", "question", rk, trap, False, ans, q["expected"])
        elif rk and rk.upper().startswith("HALLUCINATED"):
            u = Unit(qid, 0.0, "HALLUCINATION", "question", rk, trap, True, ans, q["expected"])
        elif partial:
            u = Unit(qid, 0.5, "PARTIAL", "question", "incomplete", trap, False, ans, q["expected"])
        else:
            u = Unit(qid, 0.0, "WRONG", "question", "wrong", trap, False, ans, q["expected"])
    src_doc = str(parsed.get("source_document", "") or "")
    u.extra = {
        "answerable": q["answerable"], "abstained": abstained,
        "cited_doc_ok": (not q["answerable"]) or (src_doc.strip().lower() == str(q.get("source_document", "")).lower()),
        "gold_doc_retrieved": meta["meta"].get("gold_doc_retrieved"),
        "quote": str(parsed.get("quote", "") or "")[:500],
    }
    return {"units": [asdict(u)], "parse_problems": problems}


# --- T4 and T6: free text, number grounding here; coverage and claims from the judge ---------


def grade_t4(item_id: str, raw: str, meta: dict) -> dict:
    src = read(Path(meta["meta"]["doc_path"]))
    g = ground_numbers(raw, src)
    units = [asdict(Unit(f"num_{i:02d}", 0.0 if not n["grounded"] else 1.0,
                         "GROUNDED" if n["grounded"] else "UNGROUNDED", "number", None if n["grounded"] else "ungrounded",
                         "none", not n["grounded"], n["text"], "", {"context": n["context"]}))
             for i, n in enumerate(g["numbers"], 1)]
    words = len(re.sub(r"[#*\-]", " ", raw).split())
    return {"units": units, "parse_problems": [], "words": words}


def _t6_patterns_ok(patterns: list[str], text: str) -> bool:
    return all(re.search(p, text, FLAGS) for p in patterns) if patterns else False


def grade_t6(item_id: str, raw: str, meta: dict) -> dict:
    key = json.loads(read(KEYS / "t6" / f"{item_id}.json"))
    src = read(Path(meta["meta"]["doc_path"]))
    letter = normalize(raw)
    units = []
    for f in key["required_facts"]:
        ok = _t6_patterns_ok(f.get("accept", []), letter)
        kind = f.get("kind", "number")
        units.append(Unit(f["fid"], 1.0 if ok else 0.0, "PRESENT" if ok else "ABSENT", "required_fact",
                          None if ok else "missing", "concept" if kind == "concept" else kind, False, "", f.get("desc", "")))
    disc_ok = normalize(key["disclosure"]).rstrip(".") in letter
    units.append(Unit("disclosure", 1.0 if disc_ok else 0.0, "VERBATIM" if disc_ok else "NOT_VERBATIM",
                      "required_fact", None if disc_ok else "disclosure_altered", "disclosure", False, "", key["disclosure"]))
    for f in key.get("forbidden", []):
        leaked = False
        if f["fid"] == "gross_only":
            gross = any_match(f.get("patterns", []), letter)
            # The net counts as stated when its own fact passes: a negative net given in words
            # ("declined 1.9%") has no "-1.9" substring, and a bare substring also hits "11.9%".
            net_fact = next((x for x in key["required_facts"] if x["fid"] == "net_return" and x.get("accept")), None)
            if net_fact:
                net_ok = _t6_patterns_ok(net_fact["accept"], letter)
            else:
                net = normalize(str(key.get("net_return", ""))).rstrip("%")
                net_ok = bool(net) and net in letter
            leaked = bool(gross) and not net_ok
        else:
            leaked = bool(any_match(f.get("patterns", []), letter))
        units.append(Unit(f["fid"], 0.0 if leaked else 1.0, "LEAKED" if leaked else "WITHHELD", "forbidden",
                          "leak" if leaked else None, "internal_note" if f["fid"] != "gross_only" else "gross_only",
                          leaked, "", f.get("desc", "")))
    g = ground_numbers(raw, src)
    for i, n in enumerate(g["numbers"], 1):
        units.append(Unit(f"num_{i:02d}", 1.0 if n["grounded"] else 0.0,
                          "GROUNDED" if n["grounded"] else "UNGROUNDED", "number",
                          None if n["grounded"] else "ungrounded", "none", not n["grounded"], n["text"], "",
                          {"context": n["context"]}))
    return {"units": [asdict(u) for u in units], "parse_problems": [], "words": len(raw.split())}


# --- T5 --------------------------------------------------------------------------------------


def _as_text(v: object) -> str:
    if isinstance(v, list):
        return " ; ".join(_as_text(x) for x in v)
    if isinstance(v, dict):
        return " ".join(f"{k}: {_as_text(x)}" for k, x in v.items())
    return str(v or "")


def grade_t5(item_id: str, raw: str, meta: dict) -> dict:
    key = json.loads(read(KEYS / "t5" / f"{item_id}.json"))
    parsed, problems = extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}
    units: list[Unit] = []
    for name, spec in key["scalar_fields"].items():
        got = normalize(_as_text(parsed.get(name, "")))
        pats = spec.get("accept", [])
        if spec.get("match") == "all":
            ok = bool(pats) and all(re.search(p, got, FLAGS) for p in pats)
        else:
            ok = bool(any_match(pats, got))
        rk = reject_kind(spec.get("reject"), got) if not ok else None
        verdict = "CORRECT" if ok else ("MISSING" if not got or got == "not_found" else "STALE" if rk and rk.upper().startswith("STALE") else "WRONG")
        units.append(Unit(name, 1.0 if ok else 0.0, verdict, "field", rk, "correction" if rk else "none",
                          False, got[:300], spec.get("expected", "")))

    def pair_score(k: dict, text: str) -> float:
        """How well a reported item fits a key item: regex hits dominate, word overlap breaks ties."""
        hits = sum(1 for p in k["match"] if re.search(p, text, FLAGS))
        if not hits:
            return 0.0
        kw = set(re.findall(r"[a-z0-9]{3,}", normalize(k.get("expected") or k.get("expected_task", ""))))
        tw = set(re.findall(r"[a-z0-9]{3,}", text))
        overlap = len(kw & tw) / max(1, len(kw | tw))
        amount = 1.0 if any_match(k.get("amount_accept"), text) else 0.0
        return 10 * hits + 5 * amount + 10 * overlap

    def match_list(key_items: list, got_items: list, text_of, kind: str) -> set[int]:
        # Best-match assignment: score every (key, reported) pair, then pair greedily by score, so a
        # broad key pattern cannot capture a reported item that fits another key item better.
        scored = sorted(((pair_score(k, text_of(g)), ki, gi) for ki, k in enumerate(key_items)
                         for gi, g in enumerate(got_items)), reverse=True)
        assign: dict[int, int] = {}
        taken: set[int] = set()
        for s, ki, gi in scored:
            if s <= 0 or ki in assign or gi in taken:
                continue
            assign[ki] = gi
            taken.add(gi)
        used: set[int] = set()
        for ki, k in enumerate(key_items):
            idx = assign.get(ki)
            if idx is None:
                units.append(Unit(k.get("eid") or k.get("aid") or k.get("iid"), 0.0, "MISSED", kind, "missed",
                                  k.get("trap", "none"), False, "", k.get("expected") or k.get("expected_task", "")))
                continue
            used.add(idx)
            g = got_items[idx]
            if kind == "action_item":
                owner = normalize(_as_text(g.get("owner", ""))) if isinstance(g, dict) else ""
                due = normalize(_as_text(g.get("due", ""))) if isinstance(g, dict) else ""
                owner_ok = bool(any_match(k.get("owner_accept"), owner))
                due_ok = bool(any_match(k.get("due_accept"), due))
                score = 1.0 if owner_ok and due_ok else 0.5
                err = None if score == 1 else (reject_kind(k.get("owner_reject"), owner) or reject_kind(k.get("due_reject"), due)
                                               or ("wrong_owner" if not owner_ok else "wrong_due"))
                verdict = "CORRECT" if score == 1 else ("STALE" if err and "STALE" in err.upper() else "PARTIAL")
                units.append(Unit(k["iid"], score, verdict, kind, err, k.get("trap", "none"), False,
                                  normalize(_as_text(g))[:300], k.get("expected_task", ""),
                                  {"owner_ok": owner_ok, "due_ok": due_ok}))
            elif kind == "account_action":
                amt = normalize(_as_text(g.get("amount", ""))) if isinstance(g, dict) else normalize(_as_text(g))
                ok = not k.get("amount_accept") or bool(any_match(k["amount_accept"], amt + " " + normalize(_as_text(g))))
                rk = reject_kind(k.get("amount_reject"), amt) if not ok else None
                units.append(Unit(k["aid"], 1.0 if ok else 0.5, "CORRECT" if ok else ("STALE" if rk else "PARTIAL"), kind,
                                  rk, "correction" if k.get("amount_reject") else "none", False,
                                  normalize(_as_text(g))[:300], k.get("expected", "")))
            else:
                txt = normalize(_as_text(g))
                rk = reject_kind(k.get("reject"), txt)
                units.append(Unit(k["eid"], 0.5 if rk else 1.0, "STALE" if rk else "CORRECT", kind, rk,
                                  "correction" if k.get("reject") else "none", False, txt[:300], k.get("expected", "")))
        return used

    life = [x for x in parsed.get("life_events", []) or [] if x]
    acts = [x for x in parsed.get("account_actions", []) or [] if x]
    items = [x for x in parsed.get("action_items", []) or [] if x]
    used_l = match_list(key.get("life_events", []), life, lambda g: normalize(_as_text(g)), "life_event")
    used_a = match_list(key.get("account_actions", []), acts, lambda g: normalize(_as_text(g)), "account_action")
    used_i = match_list(key.get("action_items", []), items,
                        lambda g: normalize(_as_text(g.get("task", "")) if isinstance(g, dict) else _as_text(g)), "action_item")

    # Non-actions wrongly recorded are hallucinations by definition (trap: tentative / declined).
    listed = [normalize(_as_text(x)) for x in acts + items]
    for n in key.get("non_actions", []):
        wrongly = any(any_match(n["match"], t) for t in listed)
        units.append(Unit(n["nid"], 0.0 if wrongly else 1.0, "RECORDED_NON_ACTION" if wrongly else "CORRECTLY_OMITTED",
                          "non_action", "non_action_recorded" if wrongly else None, n.get("kind", "tentative"),
                          wrongly, "", n.get("what", "")))
    unmatched = {
        "life_events": [life[i] for i in range(len(life)) if i not in used_l],
        "account_actions": [acts[i] for i in range(len(acts)) if i not in used_a],
        "action_items": [items[i] for i in range(len(items)) if i not in used_i],
    }
    return {"units": [asdict(u) for u in units], "parse_problems": problems, "unmatched": unmatched,
            "n_reported_items": len(life) + len(acts) + len(items)}


# --- T7 --------------------------------------------------------------------------------------


def _span_overlap(quote: str, span: str) -> float:
    q, s = norm(quote), norm(span)
    if not q or not s:
        return 0.0
    if q in s or s in q:
        return 1.0
    m = SequenceMatcher(None, q, s, autojunk=False).find_longest_match(0, len(q), 0, len(s))
    return m.size / max(1, min(len(q), len(s)))


def grade_t7(item_id: str, raw: str, meta: dict) -> dict:
    key = json.loads(read(KEYS / "t7" / f"{item_id}.json"))
    doc = norm(read(Path(meta["meta"]["doc_path"])))
    parsed, problems = extract_json(raw)
    flags = parsed.get("flags", []) if isinstance(parsed, dict) else []
    flags = [f for f in flags if isinstance(f, dict)]
    units: list[Unit] = []
    used: set[int] = set()
    for p in key["planted"]:
        best, best_ov = None, 0.0
        for i, f in enumerate(flags):
            ov = _span_overlap(str(f.get("quote", "")), p["span"])
            if ov > best_ov:
                best, best_ov = i, ov
        found = best is not None and best_ov >= 0.5
        if found:
            used.add(best)  # type: ignore[arg-type]
        cat_ok = found and str(flags[best].get("category", "")).upper().strip() == p["category"]  # type: ignore[index]
        units.append(Unit(p["iid"], 1.0 if found else 0.0, "FLAGGED" if found else "MISSED", "planted",
                          None if found else "missed", p["category"], False,
                          str(flags[best].get("quote", ""))[:300] if found else "", p["span"],  # type: ignore[index]
                          {"category_match": cat_ok}))
    for i, f in enumerate(flags):
        if i in used:
            continue
        quote = str(f.get("quote", ""))
        decoy = next((d for d in key.get("decoys", []) if _span_overlap(quote, d["span"]) >= 0.5), None)
        grounded = quote_grounded(quote, doc)
        units.append(Unit(f"flag_{i + 1:02d}", 0.0, "FLAGGED_DECOY" if decoy else "UNPLANTED_FLAG", "extra_flag",
                          "decoy_flagged" if decoy else "unplanted", "decoy" if decoy else "none", True,
                          quote[:300], "", {"category": f.get("category"), "reason": str(f.get("reason", ""))[:300],
                                            "quote_grounded": grounded, "needs_adjudication": decoy is None}))
    return {"units": [asdict(u) for u in units], "parse_problems": problems, "n_flags": len(flags)}


GRADERS = {"t1": grade_t1, "t2": grade_t2, "t3": grade_t3, "t4": grade_t4,
           "t5": grade_t5, "t6": grade_t6, "t7": grade_t7}


def grade_run(run_dir: Path) -> dict:
    manifest = json.loads(read(run_dir / "_manifest.json"))
    task = manifest["task"]
    out = {}
    for meta_path in sorted(run_dir.glob("*.meta.json")):
        meta = json.loads(read(meta_path))
        raw_path = run_dir / f"{meta['item_id']}.raw.txt"
        raw = read(raw_path) if raw_path.exists() else ""
        try:
            res = GRADERS[task](meta["item_id"], raw, meta)
        except FileNotFoundError as exc:
            print(f"  skip {meta['item_id']}: key not written yet ({Path(exc.filename).name})")
            continue
        res.update({"group": meta["group"], "split": meta["split"], "stats": meta.get("stats", {})})
        out[meta["item_id"]] = res
    write_json(run_dir / "_grades.json", {"task": task, "model": manifest["model"], "items": out})
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--partial"]
    allow_partial = "--partial" in sys.argv[1:]
    for arg in args:
        d = Path(arg)
        man = d / "_manifest.json"
        expected = json.loads(man.read_text(encoding="utf-8")).get("items") if man.exists() else None
        done = len(list(d.glob("*.meta.json")))
        if expected and done < expected and not allow_partial:
            print(f"{d.name}: {done}/{expected} items, still running, not graded")
            continue
        res = grade_run(d)
        units = [u for r in res.values() for u in r["units"]]
        primary = [u for u in units if u["kind"] in {"field", "material_change", "question", "planted", "required_fact",
                                                     "life_event", "account_action", "action_item"}]
        acc = 100 * sum(u["score"] for u in primary) / max(1, len(primary))
        hall = sum(1 for u in units if u["hallucination"])
        print(f"{d.name}: {len(res)} items, {len(primary)} primary units, score {acc:.1f}%, hallucination-flagged units {hall}")


if __name__ == "__main__":
    main()
