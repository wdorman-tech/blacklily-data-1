"""Task registry: which items exist, and the exact messages each subject receives.

An Item carries the finished system and user text. Local and frontier subjects are both
driven from Item.system / Item.user, which is how byte-identical prompts are guaranteed.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from common import CORPUS, KEYS, NO1, OLLAMA, PROMPTS, ROOT, read, sha256, write_json

TASKS = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
EMBED_MODEL = "qwen3-embedding:0.6b"
RETRIEVAL_K = 8
CHUNK_WORDS = 280
CHUNK_OVERLAP = 40


def load_prompt(task: str):
    spec = importlib.util.spec_from_file_location(f"prompt_{task}", PROMPTS / f"{task}.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@dataclass
class Item:
    task: str
    item_id: str
    split: str
    group: str  # bootstrap resampling unit
    system: str
    user: str
    json_mode: bool
    num_predict: int
    meta: dict = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return sha256(self.system + "\n\x00\n" + self.user)


def _split_dirs(task: str, split: str) -> list[Path]:
    return [CORPUS / task / s for s in (["dev", "test"] if split == "all" else [split])]


# --- T1 -------------------------------------------------------------------------------------

NO1_DOCS = ["doc1_meridian_ridge", "doc2_calder_wyeth", "doc3_ashgrove"]


def t1_items(split: str, variant: str) -> list[Item]:
    p = load_prompt("t1")
    docs: list[tuple[str, str, Path]] = []
    if split in ("dev", "all"):
        docs += [(d, "dev", NO1 / "corpus" / f"{d}.md") for d in NO1_DOCS]
    for d in _split_dirs("t1", split):
        docs += [(f.stem, d.name, f) for f in sorted(d.glob("*.md"))]
    items = []
    for doc_id, sp, path in docs:
        text = read(path)
        naive = variant == "naive" or variant == "oob"
        items.append(Item(
            "t1", doc_id, sp, doc_id,
            p.NAIVE_SYSTEM if naive else p.SYSTEM,
            p.build_naive_user(text) if naive else p.build_user(text),
            p.JSON_MODE, p.NUM_PREDICT,
            {"doc_path": str(path), "doc_words": len(text.split())},
        ))
    return items


def t1_key(doc_id: str) -> dict:
    path = NO1 / "ground_truth" / f"{doc_id}.json" if doc_id in NO1_DOCS else KEYS / "t1" / f"{doc_id}.json"
    return json.loads(read(path))


# --- T2 -------------------------------------------------------------------------------------


def t2_items(split: str, variant: str) -> list[Item]:
    p = load_prompt("t2")
    items = []
    for d in _split_dirs("t2", split):
        for pair in sorted(x for x in d.iterdir() if x.is_dir()):
            prior, current = read(pair / "prior.md"), read(pair / "current.md")
            m = re.match(r"t2_([a-z]+)_\d+$", pair.name)
            group = m.group(1) if m else pair.name  # real pairs cluster by issuer
            items.append(Item(
                "t2", pair.name, d.name, group, p.SYSTEM, p.build_user(prior, current),
                p.JSON_MODE, p.NUM_PREDICT,
                {"pair_path": str(pair), "doc_words": len(prior.split()) + len(current.split()),
                 "source": "real" if m else "synthetic"},
            ))
    return items


# --- T3 -------------------------------------------------------------------------------------


def _doc_label(text: str) -> str:
    """Title and date line from the head of a firm document, used in every chunk header."""
    head = text.splitlines()[:12]
    title = next((ln.lstrip("# ").strip() for ln in head if ln.startswith("# ")), "")
    date = ""
    for ln in head:
        if m := re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})", ln):
            date = m.group(1)
            break
    return f"{title}{', dated ' + date if date else ''}"


def chunk_document(name: str, text: str) -> list[dict]:
    label = _doc_label(text)
    chunks: list[dict] = []
    section, parent, buf = "Preamble", "", []

    def flush() -> None:
        words = " ".join(buf).split()
        if not words:
            return
        step = CHUNK_WORDS - CHUNK_OVERLAP
        for start in range(0, max(1, len(words) - CHUNK_OVERLAP), step):
            piece = " ".join(words[start : start + CHUNK_WORDS])
            if piece:
                chunks.append({"doc": name, "label": label,
                               "section": f"{parent} > {section}" if parent else section,
                               "text": piece})
            if start + CHUNK_WORDS >= len(words):
                break

    for line in text.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            flush()
            buf = []
            h = line.lstrip("# ").strip()
            if line.startswith("## "):
                parent, section = h, h
            else:
                section = h
            continue
        buf.append(line)
    flush()
    for i, c in enumerate(chunks):
        c["cid"] = f"{name}#{i:03d}"
    return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    with httpx.Client(timeout=600) as client:
        for i in range(0, len(texts), 32):
            r = client.post(f"{OLLAMA}/api/embed", json={"model": EMBED_MODEL, "input": texts[i : i + 32]})
            r.raise_for_status()
            out += r.json()["embeddings"]
    return out


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def t3_retrieval(firm_dir: Path, key: dict) -> dict:
    """Retrieve top-k chunks per question once, cache, and reuse for every subject."""
    cache = ROOT / "runs" / "_retrieval" / f"{firm_dir.name}.json"
    if cache.exists():
        return json.loads(read(cache))
    chunks = []
    for doc in sorted(firm_dir.glob("*.md")):
        chunks += chunk_document(doc.name, read(doc))
    vecs = _embed([f"{c['label']}\n{c['section']}\n{c['text']}" for c in chunks])
    instr = "Instruct: Given a due diligence questionnaire question, retrieve the firm policy passages that answer it\nQuery: "
    qvecs = _embed([instr + q["question"] for q in key["questions"]])
    per_q = {}
    for q, qv in zip(key["questions"], qvecs):
        scored = sorted(((_cos(qv, v), i) for i, v in enumerate(vecs)), reverse=True)[:RETRIEVAL_K]
        per_q[q["qid"]] = [{"cid": chunks[i]["cid"], "score": round(s, 4)} for s, i in scored]
    out = {"embed_model": EMBED_MODEL, "k": RETRIEVAL_K, "chunk_words": CHUNK_WORDS,
           "chunk_overlap": CHUNK_OVERLAP, "chunks": chunks, "retrieved": per_q}
    write_json(cache, out)
    return out


def t3_items(split: str, variant: str) -> list[Item]:
    """variant: 'retrieval' (default), 'fullpack', or 'fullpack' with a ctx override."""
    p = load_prompt("t3")
    items = []
    for d in _split_dirs("t3", split):
        for firm in sorted(x for x in d.iterdir() if x.is_dir()):
            key = json.loads(read(KEYS / "t3" / f"{firm.name}.json"))
            docs = {f.name: read(f) for f in sorted(firm.glob("*.md"))}
            pack = "\n\n".join(p.format_document(n, t) for n, t in docs.items())
            ret = t3_retrieval(firm, key) if not variant.startswith("fullpack") else None
            by_cid = {c["cid"]: c for c in ret["chunks"]} if ret else {}
            for q in key["questions"]:
                if ret:
                    sel = [by_cid[r["cid"]] for r in ret["retrieved"][q["qid"]]]
                    sel.sort(key=lambda c: c["cid"])  # document order, not score order
                    context = "\n\n".join(p.format_chunk(c["doc"], c["label"], c["section"], c["text"]) for c in sel)
                    retrieved_docs = sorted({c["doc"] for c in sel})
                else:
                    context, retrieved_docs = pack, sorted(docs)
                gold_doc = q.get("source_document", "")
                items.append(Item(
                    "t3", f"{firm.name}.{q['qid']}", d.name,
                    f"{firm.name}:{gold_doc or 'unanswerable'}",
                    p.SYSTEM, p.build_user(q["question"], context), p.JSON_MODE, p.NUM_PREDICT,
                    {"firm": firm.name, "qid": q["qid"], "answerable": q["answerable"],
                     "trap": q.get("trap", "none"), "retrieved_docs": retrieved_docs,
                     "gold_doc_retrieved": (not gold_doc) or gold_doc in retrieved_docs,
                     "doc_words": len(context.split())},
                ))
    return items


# --- T4 to T7: one document per item ---------------------------------------------------------


def _single_doc_items(task: str, split: str) -> list[Item]:
    p = load_prompt(task)
    items = []
    for d in _split_dirs(task, split):
        for f in sorted(d.glob("*.md")):
            text = read(f)
            items.append(Item(task, f.stem, d.name, f.stem, p.SYSTEM, p.build_user(text),
                              p.JSON_MODE, p.NUM_PREDICT,
                              {"doc_path": str(f), "doc_words": len(text.split())}))
    return items


def items_for(task: str, split: str, variant: str = "default") -> list[Item]:
    if task == "t1":
        return t1_items(split, variant)
    if task == "t2":
        return t2_items(split, variant)
    if task == "t3":
        return t3_items(split, variant)
    return _single_doc_items(task, split)
