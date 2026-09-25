# Black Lily benchmark data

The full record behind Black Lily's pre-registered benchmarks of open-weight models, run on hardware a firm owns, against Claude Opus 5 on investment adviser documents. Corpus, answer keys, frozen prompts, every raw output and transcript, the graders, and the `results.json` that every published number comes from.

> [!NOTE]
> **For AI agents**
> - Every published number is a field in `report02/results.json` or `report03/results.json`. Read those first and cite by JSON path.
> - One run is one folder: `report02/runs/<model>/<task>/<split>-<variant>-r<n>/`. No. 03's models write there too.
> - Run every command from the repo root. Rebuilding results needs no GPU and no API key.
> - Treat `corpus/`, `keys/`, `prompts/` and every file listed in `report03/ops/REGISTRATION.json` as read-only. Hashes pin them.
> - Files are stored byte for byte. Never normalize line endings.

## Reports

| | Question | Read |
|---|---|---|
| **No. 01** | Can a 14B model on one 12 GB card extract 20 fund terms as well as Claude? | `onepager/results.json` |
| **No. 02** | Where do models that fit on one 12 GB card hold, and where do they break? | [Where local models hold, and where they break](https://blacklily.ai/research/local-vs-frontier) |
| **No. 03** | What does a larger local model close? | [What a larger local model closes, and what card would hold it](https://blacklily.ai/research/larger-local-models) |

## Results

Primary metric on the test split. Tiers against Claude Opus 5 were fixed before any run:
● **parity**: within 3 points, no more unsupported content, no trap failed more often.
◐ **usable with review**: within 10 points, unsupported content at most 3%.
○ **gap**: anything else.
Confidence intervals, trap tables and error breakdowns are in `results.json`.

**No. 02: models that fit on one 12 GB card** (local: mean of three runs; Claude: one run)

| Task | Metric | Gemma 4 12B | Qwen3.5 9B | Qwen2.5 14B | Ministral 3 14B | Claude Opus 5 |
|---|---|---:|---:|---:|---:|---:|
| T1 Fund term extraction | Field accuracy | 97.8 ◐ | 96.7 ◐ | 93.9 ◐ | 97.2 ◐ | **100.0** |
| T2 Change detection | Material-change recall | 78.0 ○ | 66.7 ○ | 75.6 ○ | 82.1 ○ | **93.5** |
| T3 Grounded Q&A | Answer accuracy | 96.7 ◐ | 97.5 ◐ | 85.0 ○ | 96.7 ◐ | **99.2** |
| T4 Filing brief | Key-fact coverage | 76.7 ○ | 75.0 ○ | 60.0 ○ | 75.0 ○ | **98.3** |
| T5 Meeting notes to CRM | CRM accuracy | 85.4 ○ | 80.1 ○ | 72.8 ○ | 87.6 ○ | **100.0** |
| T6 Client drafting | Required-content rate | 94.8 ◐ | 98.5 ● | 95.6 ◐ | 97.0 ○ | **100.0** |
| T7 Marketing review | Planted-issue recall | 66.7 ○ | 55.6 ○ | 53.3 ○ | 62.2 ○ | **86.7** |

**No. 03: larger local models** (one run each; T3 is scored on one 40-question firm pack, so it differs from No. 02)

| Task | Metric | Gemma 4 31B | Qwen3.8 27B | Gemma 4 26B-A4B | Qwen3.6 35B-A3B | Claude Opus 5 |
|---|---|---:|---:|---:|---:|---:|
| T1 Fund term extraction | Field accuracy | 98.6 ◐ | 99.4 ● | 99.2 ◐ | 98.3 ◐ | **100.0** |
| T2 Change detection | Material-change recall | 87.0 ◐ | 94.3 ◐ | 89.4 ◐ | 77.2 ○ | **93.5** |
| T3 Grounded Q&A | Answer accuracy | 97.5 ◐ | 97.5 ◐ | 95.0 ◐ | 93.8 ◐ | **100.0** |
| T4 Filing brief | Key-fact coverage | 84.2 ○ | 85.0 ○ | 75.0 ○ | 82.5 ○ | **98.3** |
| T5 Meeting notes to CRM | CRM accuracy | 91.6 ◐ | 95.5 ◐ | 93.3 ◐ | 89.3 ○ | **100.0** |
| T6 Client drafting | Required-content rate | 99.3 ● | 99.3 ● | 98.5 ◐ | 99.3 ● | **100.0** |
| T7 Marketing review | Planted-issue recall | 88.9 ◐ | 73.3 ○ | 75.6 ○ | 64.4 ○ | **86.7** |

**No. 01:** Qwen2.5 14B scored 98.3% field accuracy against Claude Opus 5's 100%, with 0% hallucination on both, stable across three runs. A 7B model scored 95.0%. Ollama's default 4K context scored 0.8%.

## Layout

```text
.
├── corpus/ ground_truth/ baseline/ runs/ src/   No. 01: documents, keys, Claude baseline, local runs, grader
├── onepager/results.json                        No. 01 results
├── report02/
│   ├── preregistration.md     method of record; deviations in Section 13
│   ├── results.json           source of every No. 02 number
│   ├── corpus/  keys/         inputs and answer keys per task, dev and test splits
│   ├── prompts/               frozen prompts; HASHES.json is checked before any test run
│   ├── specs/                 how the synthetic documents were written
│   ├── runs/                  every output, transcript, grade and judge verdict (No. 02 and No. 03)
│   ├── review/                contested T2 materiality labels, excluded from recall
│   ├── src/                   runner, graders, judge, results builder, EDGAR fetcher
│   └── ops/                   GPU queue, fit probe, prompt freezer, Ollama launcher
└── report03/
    ├── preregistration.md  results.json
    ├── ops/                   model field, fit probe, control, GPU queue, REGISTRATION.json
    ├── snapshots/             the ollama.com pages the field was chosen from
    └── src/build_results_03.py
```

Inside a run folder:

| File | Contents |
|---|---|
| `_manifest.json` | model tag and digest, Ollama server flags, context size, GPU placement |
| `<item>.raw.txt` | the model's output, verbatim |
| `<item>.thinking.txt` | reasoning trace, where the model produced one |
| `<item>.meta.json` | prompt hashes, input document, token counts, timings |
| `<item>.transcript.jsonl` | Claude Code event stream (Claude runs and judge calls) |
| `_grades.json` | regex grading, unit by unit |
| `_judge/` | judge verdicts with their transcripts |

`runs/_judge_cache/` holds verdicts by prompt hash, `_pairwise/` the T6 preference judgments, `_retrieval/` the T3 retrieval record, and `_invalid_thinkon/` the configuration runs quarantined for running with thinking on (preregistration Section 13).

## Reproduce

```sh
uv sync

# Rebuild both results files from the shipped grades and verdicts.
# git diff then shows only meta.generated.
uv run report02/src/build_results.py
uv run report03/src/build_results_03.py

# Regrade a run from its raw outputs.
uv run report02/src/grade.py report02/runs/qwen3.5-9b/t1/test-default-thinkoff-ctx16384-r1
```

Rerunning models:

- **Local:** Ollama 0.34.2 with flash attention and a q8_0 KV cache. Start it with `report02/ops/ollama-serve.cmd`, or elsewhere `mkdir -p report02/logs && OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_NUM_PARALLEL=1 ollama serve >> report02/logs/ollama-server.log 2>&1` (the runner reads the flags back from that log). One job: `uv run report02/src/run.py --task t1 --model qwen3.5:9b --split test --run r1 --think off`. Every job: `uv run report02/ops/gpu_queue.py test` and `uv run report03/ops/gpu_queue_03.py test` (these call `.venv/Scripts/python.exe`, so Windows).
- **Claude and the judge:** headless Claude Code (`claude -p`, no tools). `--model claude-opus-5` on the runner; `uv run report02/src/judge.py absolute <run dirs>` for verdicts.
- The runner refuses a test run whose prompts do not match `report02/prompts/HASHES.json`.

## Data

- **Invented:** every fund, firm and person in T1, T3, T5, T6, T7 and T2's synthetic pairs.
- **Public:** T2's real pairs are 10-K Item 1A risk factors (FY2024 against FY2025). T4 is Form 8-K Exhibit 99.1 earnings releases. Both come from SEC EDGAR. The cached filings are not included; refetch with `EDGAR_USER_AGENT="Name you@example.com" uv run report02/src/edgar.py 10k|8k <tickers>`.
- **Anonymized:** paths are repo-relative. Claude transcripts keep model, messages, thinking, usage and timings, and drop session, request and message IDs, thinking signatures, cost fields and the local environment; tool-use IDs are renumbered. Personal names and locations are redacted. No document, key, prompt, model output, grade or verdict changed.
- **Hashes:** both `results.json` files were rebuilt from this release and match the published numbers; their `meta.prereg_sha256` is the hash of the preregistration shipped here. Every file in `report03/ops/REGISTRATION.json` matches its registered hash except the preregistration (Section 13 grows after registration; the text above it still matches, see `meta.registration`) and `build_results_03.py` (a logged deviation).
- **Not included:** the paper and website builders and working logs.
