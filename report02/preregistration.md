# Benchmark Report No. 02: Pre-registration

Registered 2026-09-21, before any system under test has seen any test-split item.
Changes after this date are appended in Section 13 with the date and the reason. Nothing
above Section 13 is edited after registration.

## 1. Question

For recurring document work inside a registered investment adviser, family office or hedge
fund, where does an open-weight model running on one consumer GPU match a frontier model,
and where does it fall short? Scope is fixed to the seven tasks, the models, the settings
and the hardware below. No result is extrapolated beyond them.

## 2. Subjects

| Role | Model | Notes |
|---|---|---|
| Frontier reference | Claude Opus 5 (`claude-opus-5`) | Through headless Claude Code, see Section 3 |
| Local, continuity | `qwen2.5:14b-instruct-q4_K_M` | The Report No. 01 model |
| Local, current | `gemma4:12b` | Most-pulled current family in the Ollama library that fits 12 GB (checked 2026-09-21) |
| Local, current | `qwen3.5:9b` | Second most-pulled current family that fits |
| Local, current (optional) | `ministral-3:14b` | Included only if it fits entirely on the GPU at 16K context with a q8_0 KV cache, measured |
| Size ablation | `qwen2.5:7b-instruct-q4_K_M` | Reproduces No. 01's 7B finding; one run per task |

Exact tags and weight digests are recorded in every run manifest. Each model runs in the
mode Ollama serves by default (thinking on or off as the model ships), recorded per run;
thinking tokens count toward latency. A thinking on/off comparison is run separately
(Section 10).

Hardware: one NVIDIA GeForce RTX 5070 (12 GB), Ryzen 7 7700X, 63 GB RAM, Windows 11.
Runtime: Ollama 0.34.2 with flash attention on and a q8_0 KV cache, confirmed from the
server's own startup log before every run and written to the manifest. A run refuses to
start if either setting is off.

## 3. How each subject is called

- **Byte-identical prompts.** For every item, local and frontier subjects receive the same
  system text and the same user text, built once by `src/tasks.py`. Each item's prompt
  hash is stored with its output.
- **Local:** Ollama `/api/chat`, temperature 0, top_p 0.9, repeat_penalty 1.0, num_ctx
  16384 unless a configuration experiment says otherwise, constrained JSON decoding on for
  JSON tasks. Serial, one item at a time.
- **Frontier:** `claude -p --safe-mode --tools "" --model claude-opus-5
  --system-prompt-file <task system prompt> --output-format stream-json`, from an empty
  working directory, one fresh session per item, prompt on standard input. `--safe-mode`
  disables instruction files, skills, plugins, hooks and MCP servers; `--tools ""` removes
  every tool; the task's system prompt replaces Claude Code's own. Temperature is not
  controllable through Claude Code. Thinking runs at Claude Code's default and its token
  count is recorded.
- Raw outputs of both subjects go through the same parser.

This is a change from the brief, which planned the frontier as workflow subagents.
Subagents inherit the workspace's instruction files and hooks, including a standing
instruction to keep replies short, which would contaminate the drafting tasks. Headless
Claude Code with the flags above removes that, removes all tools, and removes Claude
Code's own system prompt, which also retires No. 01's "extra system prompt" limitation.

## 4. Roles and blinding

- **Author** (Claude Opus 5 agents with file tools): writes synthetic documents and all
  keys, key-fact lists and rubrics into `corpus/` and `keys/`.
- **Verifier** (separate agents): checks every key item against its document (quote and
  location), independently. On real documents, T2 materiality is labeled twice by two
  blind labelers; agreement is reported as Cohen's kappa and disagreements are marked
  contested, excluded from the recall denominator, and sent to `review/`.
- **Subject** (Section 3): sees only the task prompt and the document. The frontier has no
  tools. Every frontier transcript is kept and scanned: a transcript with any tool call, or
  an init event listing any tool, fails the blinding check and the item is re-run.
- **Grader:** deterministic code wherever the task allows (Section 7). A separate judge
  where it does not.

The Author, Verifier, judge and frontier subject are all Claude. That is disclosed in the
paper as a limitation: synthetic documents written by Claude may suit Claude, and Claude
judges Claude against open models.

## 5. Corpus and split

Dev items are used for prompt engineering and grader debugging only. Prompts are frozen
and hashed (`prompts/HASHES.json`) before the first test-split run. Test results are
reported; dev results are not.

| Task | Source | Dev | Test | Graded test units (approx.) |
|---|---|---|---|---|
| T1 Fund term extraction | Synthetic PPMs, OMs, LPAs, side letters | No. 01's 3 documents + 1 | 9 documents | 180 fields |
| T2 Change detection | Real: 10-K Item 1A, FY2024 vs FY2025, 8 issuers, cut into aligned excerpts. Synthetic: 2 LPA and 2 compliance manual version pairs | 5 real excerpts (2 issuers) + 1 synthetic | 19 real excerpts (6 issuers) + 3 synthetic | about 110 material changes, plus every reported change |
| T3 Grounded Q&A | Synthetic firm packs (6 documents, 15K to 18K words) and 40-question DDQs | 1 firm | 3 firms | 120 questions |
| T4 Filing brief | Real: Form 8-K Exhibit 99.1 earnings releases furnished July and August 2026 | 4 releases | 12 releases | 120 key facts, plus every number and claim |
| T5 Meeting to CRM | Synthetic transcripts, 4,200 to 5,800 words | 3 | 9 | about 150 fields and items |
| T6 Client drafting | Synthetic fact sheets | 5 | 15 | 135 required elements, plus every number |
| T7 Marketing review | Synthetic drafts against a checklist derived from Rule 206(4)-1 | 5 | 20 | about 50 planted issues, plus every flag |

Real documents come from SEC EDGAR with a declared User-Agent, under the fair-access rate.
The T4 releases were furnished after the training cutoff of every model tested. Synthetic
documents carry the synthetic-document banner, and every invented entity name is checked
against EDGAR company search and the IAPD adviser search before any run.

## 6. Tasks and metrics

Each task has one primary metric, one hallucination metric (two for T4) and named trap
categories. "Points" are percentage points.

| Task | Primary metric | Hallucination metric | Trap categories |
|---|---|---|---|
| T1 | Field accuracy: mean over fields, correct 1, partial 0.5 | Share of fields graded hallucination (a substantive value where the key says absent, or a reject pattern marked fabricated) | absence, supersession (including late-position and precedence), side letter, table-only, layered fee, holding-not-commitment, class variants |
| T2 | Material-change recall: key material changes located by at least one report | Invented-change rate: reports that point at an unchanged or moved section, or at nothing in either version, over all reports | added, removed, subtle modification, moved section |
| T3 | Answer accuracy over all questions: answerable correct 1 / partial 0.5; unanswerable correctly abstained 1 | Fabrication rate: answers to unanswerable questions plus answers matching a fabricated-value pattern, over all questions | supersession, near-miss unanswerable, clean unanswerable, multi-part |
| T4 | Key-fact coverage: facts the judge finds stated correctly (figure, period and GAAP basis), over 10 per release | (a) Ungrounded-number rate, deterministic. (b) Unsupported-claim rate: atomic claims the judge finds unsupported by the release, over all claims | non-GAAP basis, guidance |
| T5 | CRM accuracy: mean over scalar fields and key list items (life events, account actions, action items with owner and due date; an item with the right task but wrong owner or date scores 0.5) | Invented-item rate: recorded non-actions plus reported items the adjudicator finds unsupported by the transcript, over all reported list items | corrected figure, reassigned owner, changed due date, tentative idea, declined proposal |
| T6 | Required-content rate: eight required facts plus the disclosure reproduced verbatim, per sheet | Ungrounded-number rate | disclosure verbatim, internal note withheld, gross-only performance |
| T7 | Planted-issue recall | False-flag rate: flags on decoys plus unplanted flags the adjudicator finds are not a checklist issue, over all flags | decoy, each checklist code |

Also reported without entering the tier: citation validity and quote grounding (T1, T3),
location accuracy (T2), false-abstention rate (T3), words per output (T4, T6), blind
pairwise preference on clarity and tone (T6), category match (T7).

## 7. Grading

- **Structured output** (T1, T2, T3, T5, T7): regex accept, partial and reject patterns
  from the key, No. 01's normalization, absence and supersession handling, citation and
  quote checks. Unparseable output scores zero on every unit it should have produced.
- **Number grounding** (T4, T6): every number in the output must appear in the source
  after normalization for units, scale, rounding to the output's shown precision, percent
  and basis-point forms and sign written in words (`src/numbers_ground.py`). Years,
  calendar days, quarter labels, list markers and form or rule numbers are not counted.
- **Judge** (T4 coverage and claims; T6 commentary points that the regex misses, and
  pairwise preference; T5 unmatched reported items; T7 unplanted flags): a separate
  headless Claude Opus 5 session per call, no tools, structured output. Subjects are
  anonymized. For pairwise preference each pair is judged twice with positions swapped;
  a pair that flips is scored a tie.
- **Human calibration:** A human reviewer blind-grades 40 judged units sampled at random
  across the judged metrics (seed 20260921). Judge-human agreement is reported per task.
  Below 80% on a task, that task's judged metric is labeled indicative only. Until the
  calibration is complete, every judged metric is labeled calibration pending.

## 8. Tiers

Each local model gets one tier per task, computed by code from test results:

- **Parity:** primary metric no more than 3 points below frontier, AND each hallucination
  metric no more than 1 point above frontier's, AND no trap category failed more often
  than by frontier (unit failures summed over test items, averaged over runs).
- **Usable with review:** primary metric no more than 10 points below frontier, AND each
  hallucination metric at or under 3%.
- **Gap:** everything else.

## 9. Statistics

- Three runs per subject per task on the test split (local at temperature 0; frontier
  in three fresh sessions per item). Reported: mean, minimum and maximum across runs.
- 95% confidence intervals on the local-minus-frontier difference by paired cluster
  bootstrap, 10,000 resamples, seed 20260921. The resampling unit is the document, never
  the field: T1 document; T2 issuer (each synthetic pair is its own cluster); T3 firm and
  answering document (unanswerable questions form one cluster per firm), because three
  firms alone cannot support a bootstrap; T4 release; T5 transcript; T6 fact sheet; T7
  piece.
- If the interval on a difference contains a tier boundary (-3 or -10 points), the paper
  says the result is not distinguishable at this sample size, next to the tier.

## 10. Configuration experiments

Run on the test split, one run each unless stated.

- **Context sweep:** T1 at num_ctx 2048, 4096, 8192, 16384 and 32768 for
  `qwen2.5:14b` and `gemma4:12b`; T3 with the whole firm pack at 4096, 8192, 16384 and
  32768. VRAM and speed recorded; offload at 32K measured, not avoided.
- **Silent failure:** among runs where the prompt was truncated (prompt tokens processed
  below the item's full prompt length), the share whose output parses as valid,
  complete-looking output (valid JSON with every required key) with nothing indicating
  that input was lost.
- **Long documents** (T3 firm packs exceed the 16K budget): truncation of the full pack,
  retrieval (qwen3-embedding:0.6b, 280-word chunks with 40-word overlap, top 8, cached
  once so every subject receives identical context) and map-reduce (pack in three parts,
  all questions per part, then a reduce call). Two labeled comparisons: "same input"
  (frontier receives the retrieved chunks) and "as deployed" (frontier receives the whole
  pack).
- **Quantization:** `qwen3.5:9b` at q4_K_M vs q8_0 on T1 and T3, offload measured.
- **Prompt:** No. 01's naive prompt vs the engineered prompt on T1.
- **Constrained JSON decoding:** on vs off on T1.
- **Thinking:** on vs off for `qwen3.5:9b` on T1 and T3.

## 11. Operational metrics

Local only: seconds per item, output tokens per second, prompt tokens, peak VRAM (sampled
from nvidia-smi once a second), whether the model sat entirely on the GPU, and other
processes' VRAM at start. Frontier wall-clock through Claude Code is not API latency and
is not reported as speed. No cost figure is published.

## 12. Published regardless of outcome

Every task result at the same size, wins and losses. Every configuration result. At least
one verbatim failure from each side per task, where one exists. The corpus, keys, prompts,
raw outputs, graders and `results.json` in a public repository before the paper is
published.

## 13. Deviations

**2026-09-21, before any test-split run. Added: regex-miss adjudication.** The keys and
their accept patterns were written by Claude, so they may recognize Claude's phrasing of a
correct answer more readily than another model's. To keep that from penalizing local
models, every test unit in T1, T3 and T5 that the patterns grade WRONG or PARTIAL (not
hallucination, stale or missing) is sent, for every subject alike, to a blind judge that
sees only the field or question, the key's expected answer and the subject's answer. A
unit the judge finds equivalent is re-scored correct and logged as adjudicated. The same
logic applies to list matching: in T5 the adjudicator of unmatched CRM items also sees the
key items that went unfound and may pair an item with one of them (an action item then
scores 1 only if its owner and due date match the transcript's final version, else 0.5);
in T7 the adjudicator of unplanted flags may pair a flag with an unmatched planted issue.
The count of adjudicated units per subject is reported, and adjudicated units enter the
calibration pool.

**2026-09-22, before any test-split run. Thinking mode fixed off for the two current local
models.** Ollama serves `gemma4:12b` and `qwen3.5:9b` with thinking on by default. On the dev
split at num_ctx 16384, gemma4 spent its entire generation budget on thinking and returned an
empty answer on every T1 document (done_reason "length", 14,270 characters of thinking, no
content), scoring zero. With thinking off it scored 100% on the same documents. A deployment
handing a model an 8,000-token document in a 16K window cannot spend the generation budget on
thinking, so the main comparison runs both current models with thinking off, recorded in every
manifest, and thinking on becomes a configuration arm on T1 and T3.

**2026-09-22, before any test-split run. Reduced frontier and judge scope.** Corpus
authoring and verification consumed the study's budget for hosted model calls. Changes:
the frontier runs once per test item, not three times (its run-to-run spread is not
reported, and its point estimate is a single run); a judge verdict is reused whenever a later run
produces a byte-identical judge prompt (common at temperature zero), so only outputs that
differ cost a new call; T6 pairwise preference is judged on first runs only; the T3 "as deployed" comparison (frontier reads the whole pack) runs once; a
planned second adversarial audit of the synthetic keys is dropped, leaving the one
independent verification pass plus the human spot-check. Local models still run three
times.

**2026-09-23, during the configuration arms. Thinking mode was missing from the configuration
runs and ten of them were rerun.** The main comparison runs the thinking-capable models with
thinking off, for the reason logged on 2026-09-22. The configuration queue did not pass that
setting, so the Gemma 4 context sweep, the T3 whole-pack sweep, the quantization arm and the
T3 map-reduce arm all ran with thinking on and measured thinking mode rather than the setting
under test. The failure is visible in the outputs: the map-reduce reduce step returned nothing
parseable on every call and the quantization arm scored zero. The ten affected runs are kept,
unused, in `runs/_invalid_thinkon/`; `ops/gpu_queue.py` now passes the thinking setting to every
configuration job, and the ten were rerun with thinking off. The arms that were never affected,
because those models have no thinking mode, are the Qwen2.5 14B context sweep and the
out-of-the-box, naive-prompt and JSON-off arms.

**2026-09-22, during the test runs. Calibration packet drawn from run 1 only.** Section 7
registers 40 judged units sampled at random across the judged metrics. Local decoding is
deterministic at temperature zero, so runs 2 and 3 reproduce run 1's outputs; sampling across
all three runs would have put the same text in front of the human grader more than once
without adding information. The pool is therefore restricted to the first test run of each
model, and the quota, the seed and the sample size are unchanged. Two defects found while
building the packet are also recorded here: the sampler matched the wrong filename for the
judged T5 lists and so drew zero meeting-notes items, and the T5 and T7 items were written
without the output they ask about. Both were fixed before the packet was released for
grading; no earlier packet was graded.

**2026-09-21, before any test-split run. Local runs start 2026-09-22.** The workstation's
GPU was unavailable for this study on the night of 2026-09-21 at the owner's request. Dev
work on the frontier, grading code and review packets continued; no local model ran.
