"""Snapshot the Ollama library, apply Report No. 03's selection rule, and freeze the field.

    python report03/ops/field_03.py snapshot   # fetch listing + tag pages, apply the rule, write ops/field_03.json
    python report03/ops/field_03.py pull       # pull the frozen field, record the local digests

The rule (REPORT-03-PLAN.md, Section 3, as operationalized here and registered verbatim):

  current     the family's library entry was updated within 365 days of the snapshot, it is a
              general-purpose instruction model (not code, OCR, translation, medical, math,
              safety-classifier or embedding), and the same developer has no later generation
              that offers a model in the same class. The last clause is No. 02's precedent:
              qwen3.5 was chosen over the more-pulled qwen3.
  dense       24B to 32B parameters, not mixture-of-experts.
  moe         mixture-of-experts, active parameters under 25B, q4 file size at most
              GPU + system memory minus 8 GB of headroom.
  pick        the two most-pulled current families per class, from distinct developers; within
              a family, the largest qualifying size. Tag: the plain q4_K_M instruct build, the
              packaging No. 02 used. MTP (multi-token prediction) builds are excluded because
              their draft heads change the decoding path.
  stretch     the largest qualifying model in the field doubles as the stretch model; the field is
              four models, not five.
  replace     a field model that does not load usably on the reference machine is reported in the
              fit table as the stretch result, and the next-ranked current family in its class,
              from a developer the class does not already have, takes its scored slot. Decided on
              load alone, before any scored run.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "snapshots"
OUT = ROOT / "ops" / "field_03.json"
LIB = "https://ollama.com/library"
UA = {"User-Agent": "Mozilla/5.0 (Black Lily benchmark field snapshot)"}

SNAPSHOT_DATE = date(2026, 9, 23)
RECENT_DAYS = 365
GPU_GB, SYSTEM_GB, HEADROOM_GB = 12.0, 63.0, 8.0
DENSE_RANGE = (24.0, 32.0)
MOE_ACTIVE_MAX = 25.0

SPECIALIZED = re.compile(r"coder|code|ocr|translate|medgemma|meditron|safeguard|guard|embed|math|devstral|codestral|sql")
# Developer release lines, oldest first. A family is superseded when a later entry in its line
# offers a model in the same class. Only lines that reach a candidate class need listing.
LINES = {
    "google": ["gemma", "gemma2", "gemma3", "gemma4"],
    "alibaba": ["qwen", "qwen2", "qwen2.5", "qwen3", "qwen3-vl", "qwen3-next", "qwen3.5", "qwen3.6",
                "qwen3.8", "qwen3.8-flash-next"],
    "openai": ["gpt-oss"],
    "nvidia": ["nemotron", "nemotron-3-nano", "nemotron-3-super", "nemotron-cascade-2", "nemotron3",
               "nemotron-3.5-lightning"],
    "mistral": ["mistral-small", "mistral-small3.1", "mistral-small3.2", "magistral", "mistral-medium-3.5"],
    "ibm": ["granite4.1", "granite4.2"],
    "allenai": ["olmo2", "olmo-3", "olmo-3.1"],
    "zhipu": ["glm-4.7-flash"],
    "liquid": ["lfm2"],
    "meta": ["llama4"],
    "deepseek": ["deepseek-r1"],
}
# Active parameter counts the tag names do not carry, from the developer's model card.
ACTIVE = {
    "gpt-oss:20b": (21.0, 3.6, "https://openai.com/index/introducing-gpt-oss/"),
    "gpt-oss:120b": (117.0, 5.1, "https://openai.com/index/introducing-gpt-oss/"),
}


def fetch(url: str, dest: Path) -> str:
    if dest.exists():
        return dest.read_text(encoding="utf-8")
    r = httpx.get(url, headers=UA, timeout=60, follow_redirects=True)
    r.raise_for_status()
    dest.write_text(r.text, encoding="utf-8")
    time.sleep(0.5)
    return r.text


def parse_count(s: str) -> float:
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1], 1)
    return float(s.rstrip("KMB").replace(",", "")) * mult


def parse_listing(text: str) -> list[dict]:
    fams = []
    for li in re.findall(r'<li\s+class="flex items-baseline.*?</li>', text, re.S):
        t = re.sub(r"\s+", " ", li)
        name = re.search(r'href="/library/([^"]+)"', t).group(1)
        chips = [html.unescape(s).strip() for s in re.findall(r'<span\s+class="inline-flex[^"]*">([^<]+)</span>', t)]
        pulls = re.search(r'<span >([\d.,]+[KMB]?)</span> <span class="hidden sm:flex">&nbsp;Pulls', t)
        upd = re.search(r'title="([A-Z][a-z]{2} \d+, \d{4})', t)
        fams.append({
            "name": name,
            "capabilities": [c for c in chips if not re.search(r"\d", c)],
            "sizes": [c for c in chips if re.search(r"\d", c)],
            "pulls": parse_count(pulls.group(1)) if pulls else 0,
            "pulls_display": pulls.group(1) if pulls else None,
            "updated": datetime.strptime(upd.group(1), "%b %d, %Y").date().isoformat() if upd else None,
        })
    return fams


def parse_tags(text: str) -> list[dict]:
    t = re.sub(r"\s+", " ", text)
    rows = re.findall(
        r'<span class="group-hover:underline">([^<]+)</span> </span> </div> </div> </div> '
        r'<div class="flex flex-col text-neutral-500 text-\[13px\]"> <span> <span class="font-mono"> (\w+)</span> . '
        r"([\d.]+)([KMG]B) . ([^<]*?) . <span", t)
    unit = {"KB": 1e-6, "MB": 1e-3, "GB": 1.0}
    return [{"tag": r[0], "digest12": r[1], "size_gb": float(r[2]) * unit[r[3]], "context": r[4].strip()} for r in rows]


def params_of(tag: str) -> tuple[float | None, float | None]:
    """Total and active parameters in billions from the tag name, (total, None) when dense."""
    if tag in ACTIVE:
        return ACTIVE[tag][0], ACTIVE[tag][1]
    suffix = tag.split(":", 1)[1]
    if m := re.match(r"(\d+(?:\.\d+)?)b-a(\d+(?:\.\d+)?)b", suffix):
        return float(m.group(1)), float(m.group(2))
    if m := re.match(r"(\d+)x(\d+(?:\.\d+)?)b", suffix):
        return None, float(m.group(2))
    if m := re.match(r"(\d+(?:\.\d+)?)b(?:-|$)", suffix):
        return float(m.group(1)), None
    return None, None


def q4_build(tags: list[dict], size: str) -> dict | None:
    """The plain q4_K_M instruct build of one size: no MTP, coding, QAT or other variant."""
    fam = tags[0]["tag"].split(":")[0] if tags else ""
    base = next((t for t in tags if t["tag"] == f"{fam}:{size}"), None)
    plain = [t for t in tags if t["tag"].startswith(f"{fam}:{size}") and t["tag"].endswith("q4_K_M")
             and not re.search(r"mtp|coding|qat|instruct-q4_K_M-", t["tag"])]
    pick = min(plain, key=lambda t: len(t["tag"])) if plain else base
    if pick is None:
        return None
    resolved = dict(pick)
    if base and base["digest12"] != pick["digest12"]:
        resolved["default_tag"] = base["tag"]
        resolved["default_digest12"] = base["digest12"]
    return resolved


def developer(name: str) -> str | None:
    return next((d for d, line in LINES.items() if name in line), None)


def classify(size_tag: str, build: dict) -> str | None:
    total, active = params_of(size_tag)
    if active is not None:
        fits = build["size_gb"] <= GPU_GB + SYSTEM_GB - HEADROOM_GB
        return "moe" if active < MOE_ACTIVE_MAX and fits else None
    if total is not None and DENSE_RANGE[0] <= total <= DENSE_RANGE[1]:
        return "dense"
    return None


def snapshot() -> None:
    SNAP.mkdir(parents=True, exist_ok=True)
    listing = parse_listing(fetch(f"{LIB}?sort=popular", SNAP / "library_popular.html"))
    cutoff = SNAPSHOT_DATE.toordinal() - RECENT_DAYS
    candidates: list[dict] = []
    screened: list[dict] = []
    for fam in listing:
        name = fam["name"]
        reason = None
        if not fam["updated"] or date.fromisoformat(fam["updated"]).toordinal() < cutoff:
            reason = "not updated within 365 days"
        elif SPECIALIZED.search(name) or "embedding" in fam["capabilities"]:
            reason = "specialized, not a general-purpose instruction model"
        big = [s for s in fam["sizes"] if re.match(r"\d", s)]
        if reason is None and big == [] and "cloud" not in fam["capabilities"]:
            big = ["?"]
        if reason:
            screened.append({"name": name, "reason": reason})
            continue
        tags = parse_tags(fetch(f"{LIB}/{name}/tags", SNAP / f"tags_{name}.html"))
        sizes = sorted({t["tag"].split(":")[1].split("-")[0] for t in tags if re.match(r"[\w.-]+:\d", t["tag"])})
        if not sizes:
            screened.append({"name": name, "reason": "no tag states a parameter count"})
        for size in sizes:
            # MoE tags carry the active count after the size: gemma4:26b-a4b-..., qwen3.6:35b-a3b.
            suffixes = [t["tag"].split(":")[1] for t in tags]
            variants = {m.group(1) for s in suffixes if s == size or s.startswith(size + "-")
                        if (m := re.match(r"(\d+(?:\.\d+)?b(?:-a\d+(?:\.\d+)?b)?)", s))}
            full = max(variants, key=len) if variants else size
            build = q4_build(tags, size)
            if build is None:
                continue
            cls = classify(f"{name}:{full}", build) or classify(f"{name}:{size}", build)
            if cls is None:
                continue
            total, active = params_of(f"{name}:{full}")
            if total is None or active is None:
                total, active = params_of(f"{name}:{size}")
            candidates.append({
                "family": name, "developer": developer(name), "pulls": fam["pulls"],
                "pulls_display": fam["pulls_display"], "updated": fam["updated"], "class": cls,
                "size": size, "total_b": total, "active_b": active, "build": build,
            })
    # Supersession: a later entry in the same developer line offering the same class.
    for c in candidates:
        line = LINES.get(c["developer"] or "", [])
        later = [o["family"] for o in candidates if o["class"] == c["class"] and o["developer"] == c["developer"]
                 and o["family"] in line and c["family"] in line and line.index(o["family"]) > line.index(c["family"])]
        c["superseded_by"] = sorted(set(later)) or None
        c["developer"] = c["developer"] or c["family"]  # undeclared: its own line, never superseded
    field: dict[str, list[dict]] = {}
    for cls in ("dense", "moe"):
        pool = [c for c in candidates if c["class"] == cls and not c["superseded_by"]]
        best: dict[str, dict] = {}
        for c in sorted(pool, key=lambda c: (-c["pulls"], -(c["total_b"] or 0))):
            fam_best = best.get(c["family"])
            if fam_best is None or (c["total_b"] or 0) > (fam_best["total_b"] or 0):
                best[c["family"]] = c
        ranked = sorted(best.values(), key=lambda c: -c["pulls"])
        picks, devs = [], set()
        for c in ranked:
            if c["developer"] in devs:
                continue
            picks.append(c)
            devs.add(c["developer"])
            if len(picks) == 2:
                break
        field[cls] = picks
    out = {
        "snapshot_date": SNAPSHOT_DATE.isoformat(),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": f"{LIB}?sort=popular",
        "rule": __doc__.split("The rule", 1)[1].strip(),
        "memory_budget_gb": {"gpu": GPU_GB, "system": SYSTEM_GB, "headroom": HEADROOM_GB},
        "field": {cls: [f"{c['family']}:{c['build']['tag'].split(':')[1]}" for c in picks] for cls, picks in field.items()},
        "candidates": sorted(candidates, key=lambda c: (c["class"], -c["pulls"])),
        "screened_out": screened,
        "listing": listing,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for cls in ("dense", "moe"):
        print(f"--- {cls}")
        for c in out["candidates"]:
            if c["class"] != cls:
                continue
            flag = "PICK" if any(c is p for p in field[cls]) else ("superseded by " + ",".join(c["superseded_by"]) if c["superseded_by"] else "")
            print(f"  {c['family']:<22} {c['pulls_display']:>6} {c['updated']} {c['size']:<6} "
                  f"total={c['total_b']} active={c['active_b']} {c['build']['tag']} {c['build']['size_gb']}GB {flag}")
    print("field:", json.dumps(out["field"]))


def pull() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    models = [m for picks in data["field"].values() for m in picks]
    for m in models:
        print(f"=== {m} {time.strftime('%H:%M:%S')}", flush=True)
        with httpx.stream("POST", "http://127.0.0.1:11434/api/pull", json={"model": m}, timeout=None) as r:
            last = ""
            for line in r.iter_lines():
                ev = json.loads(line) if line else {}
                if "error" in ev:
                    raise SystemExit(f"pull {m} failed: {ev['error']}")
                status = ev.get("status", "")
                if status != last and not status.startswith("pulling "):
                    print(status, flush=True)
                last = status
    local = {t["name"]: t for t in httpx.get("http://127.0.0.1:11434/api/tags", timeout=30).json()["models"]}
    data["pulled"] = {m: {"digest": local[m]["digest"], "size_bytes": local[m]["size"],
                          "details": local[m].get("details", {})} for m in models}
    for m in models:
        want = next(c["build"]["digest12"] for c in data["candidates"] if f"{c['family']}:{c['build']['tag'].split(':')[1]}" == m)
        if not data["pulled"][m]["digest"].startswith(want):
            raise SystemExit(f"{m}: local digest {data['pulled'][m]['digest'][:12]} != snapshot {want}")
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("PULLS_DONE", flush=True)


def replace() -> None:
    """A field model that cannot load on the reference machine makes way for the next-ranked current
    family in its class (distinct developer from the class's other pick). Decided on load alone, before
    any scored run; the model that failed stays in the fit table as the stretch result.

        python report03/ops/field_03.py replace gpt-oss:120b "reason"
    """
    failed, reason = sys.argv[2], sys.argv[3]
    data = json.loads(OUT.read_text(encoding="utf-8"))
    cls = next(c for c, picks in data["field"].items() if failed in picks)
    tag = lambda c: f"{c['family']}:{c['build']['tag'].split(':')[1]}"  # noqa: E731
    keep = [m for m in data["field"][cls] if m != failed]
    keep_devs = {c["developer"] or c["family"] for c in data["candidates"] if tag(c) in keep}
    tried = {failed, *keep, *data.get("did_not_load", {})}
    pool = sorted((c for c in data["candidates"] if c["class"] == cls and not c["superseded_by"]
                   and (c["developer"] or c["family"]) not in keep_devs and tag(c) not in tried),
                  key=lambda c: -c["pulls"])
    if not pool:
        raise SystemExit(f"no current {cls} family left to replace {failed}")
    nxt = pool[0]
    data.setdefault("did_not_load", {})[failed] = {"class": cls, "reason": reason, "replaced_by": tag(nxt),
                                                   "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    data["field"][cls] = [*keep, tag(nxt)]
    data.get("pulled", {}).pop(failed, None)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"{failed} -> {tag(nxt)} ({nxt['pulls_display']} pulls, {nxt['build']['size_gb']} GB)")


if __name__ == "__main__":
    {"snapshot": snapshot, "pull": pull, "replace": replace}[sys.argv[1]]()
