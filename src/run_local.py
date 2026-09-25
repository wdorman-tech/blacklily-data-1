"""Run the fund-document extraction workflow against a local Ollama model."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from schema import (
    FIELD_NAMES,
    NAIVE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_naive_user_prompt,
    build_user_prompt,
    empty_record,
)

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
RUNS = ROOT / "runs"
OLLAMA = "http://127.0.0.1:11434"


def load_docs(only: str | None) -> list[tuple[str, str]]:
    docs = sorted(CORPUS.glob("*.md"))
    if only:
        docs = [d for d in docs if only in d.stem]
    if not docs:
        raise SystemExit(f"no documents matched {only!r} in {CORPUS}")
    return [(d.stem, d.read_text(encoding="utf-8")) for d in docs]


def coerce(raw: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Parse model output into the schema, recording every repair we had to make."""
    problems: list[str] = []
    text = raw.strip()

    if text.startswith("```"):
        problems.append("wrapped_in_markdown_fence")
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.rsplit("```", 1)[0]

    start, end = text.find("{"), text.rfind("}")
    if start > 0 or (end != -1 and end < len(text.strip()) - 1):
        problems.append("prose_around_json")
    if start == -1 or end == -1:
        return empty_record(), problems + ["no_json_object_found"]
    text = text[start : end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return empty_record(), problems + [f"invalid_json:{exc.msg}"]

    if not isinstance(parsed, dict):
        return empty_record(), problems + ["json_not_an_object"]

    record = empty_record()
    for name in FIELD_NAMES:
        if name not in parsed:
            problems.append(f"missing_field:{name}")
            continue
        entry = parsed[name]
        if isinstance(entry, str):
            problems.append(f"flat_string_not_object:{name}")
            record[name] = {"value": entry, "citation": "", "quote": ""}
            continue
        if not isinstance(entry, dict):
            problems.append(f"bad_field_type:{name}")
            continue
        record[name] = {
            "value": str(entry.get("value", "") or ""),
            "citation": str(entry.get("citation", "") or ""),
            "quote": str(entry.get("quote", "") or ""),
        }

    for extra in set(parsed) - set(FIELD_NAMES):
        problems.append(f"extra_field:{extra}")

    return record, problems


def call_ollama(
    model: str,
    document: str,
    *,
    num_ctx: int,
    temperature: float,
    json_mode: bool,
    naive: bool = False,
) -> tuple[str, dict]:
    system = NAIVE_SYSTEM_PROMPT if naive else SYSTEM_PROMPT
    user = build_naive_user_prompt(document) if naive else build_user_prompt(document)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.0,
            "num_predict": 4096,
        },
    }
    if json_mode:
        payload["format"] = "json"

    started = time.perf_counter()
    with httpx.Client(timeout=1800.0) as client:
        resp = client.post(f"{OLLAMA}/api/chat", json=payload)
        resp.raise_for_status()
        body = resp.json()
    wall = time.perf_counter() - started

    prompt_tokens = body.get("prompt_eval_count", 0)
    out_tokens = body.get("eval_count", 0)
    eval_ns = body.get("eval_duration", 0) or 1
    stats = {
        "wall_seconds": round(wall, 2),
        "prompt_tokens": prompt_tokens,
        "output_tokens": out_tokens,
        "output_tokens_per_sec": round(out_tokens / (eval_ns / 1e9), 1),
        "load_seconds": round(body.get("load_duration", 0) / 1e9, 2),
    }
    return body["message"]["content"], stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:14b-instruct-q4_K_M")
    ap.add_argument("--tag", required=True, help="output subdirectory under runs/")
    ap.add_argument("--doc", default=None, help="substring filter on document stem")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument(
        "--naive",
        action="store_true",
        help="use the unengineered first-attempt prompt (ablation)",
    )
    ap.add_argument(
        "--no-json-mode",
        action="store_true",
        help="disable Ollama constrained JSON decoding (ablation)",
    )
    args = ap.parse_args()

    outdir = RUNS / args.tag
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "model": args.model,
        "tag": args.tag,
        "num_ctx": args.num_ctx,
        "temperature": args.temperature,
        "json_mode": not args.no_json_mode,
        "prompt": "naive" if args.naive else "engineered",
        "docs": {},
    }

    for doc_id, document in load_docs(args.doc):
        print(f"[{args.tag}] {doc_id} ... ", end="", flush=True)
        raw, stats = call_ollama(
            args.model,
            document,
            num_ctx=args.num_ctx,
            temperature=args.temperature,
            json_mode=not args.no_json_mode,
            naive=args.naive,
        )
        record, problems = coerce(raw)

        (outdir / f"{doc_id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        (outdir / f"{doc_id}.raw.txt").write_text(raw, encoding="utf-8")
        manifest["docs"][doc_id] = {**stats, "parse_problems": problems}

        flag = "OK" if not problems else f"{len(problems)} parse issue(s)"
        print(
            f"{stats['wall_seconds']}s  "
            f"{stats['prompt_tokens']} in / {stats['output_tokens']} out  "
            f"{stats['output_tokens_per_sec']} tok/s  [{flag}]"
        )

    (outdir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"[{args.tag}] wrote {outdir}")


if __name__ == "__main__":
    main()
