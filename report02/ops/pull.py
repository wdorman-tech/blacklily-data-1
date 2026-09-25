"""Pull the model field through the Ollama HTTP API, one at a time, logging progress."""

import json
import sys
import time

import httpx

MODELS = sys.argv[1:]
for m in MODELS:
    print(f"=== {m} {time.strftime('%H:%M:%S')}", flush=True)
    last = ""
    with httpx.stream("POST", "http://127.0.0.1:11434/api/pull", json={"model": m}, timeout=None) as r:
        for line in r.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            status = ev.get("status", "")
            if "error" in ev:
                print("ERROR", ev["error"], flush=True)
                break
            if status != last and not status.startswith("pulling "):
                print(status, flush=True)
            last = status
    print(f"--- done {m} {time.strftime('%H:%M:%S')}", flush=True)
print("PULLS_DONE", flush=True)
