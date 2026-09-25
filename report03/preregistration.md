# Benchmark Report No. 03: Pre-registration

Registered 2026-09-23, after the dev split and before any field model has seen a test-split
item. SHA-256 of this file and of every file the method depends on are in
`ops/REGISTRATION.json`. Changes after registration are appended in Section 13 with the date and
the reason. Nothing above Section 13 is edited after registration.

## 1. Question

On hardware a firm already owns, how much of the gap between local open-weight models and a
frontier model closes when the model is no longer required to fit in graphics memory, and what
does that cost in wall clock on the reference machine? Scope is fixed to No. 02's seven tasks,
the four models below, the settings below and the reference machine. No result is extrapolated
beyond them. Quality and speed are reported as separate properties: quality belongs to the
weights, quantization, context window and prompt; speed belongs to the machine.

## 2. Subjects

Frozen 2026-09-23 by `ops/field_03.py snapshot` under the rule in that script's docstring.
Snapshot pages in `snapshots/`, candidates and screening reasons in `ops/field_03.json`.

| Role | Tag | Class | Digest (first 12) |
|---|---|---|---|
| Field | `gemma4:31b-it-q4_K_M` | Dense, 31B | 6316f0629137 |
| Field | `qwen3.8:27b-q4_K_M` | Dense, 27B, hybrid attention | 25b843619e94 |
| Field | `gemma4:26b-a4b-it-q4_K_M` | MoE, 26B total, 4B active | 5571076f3d70 |
| Field (replacement) | `qwen3.6:35b-a3b-q4_K_M` | MoE, 35B total, 3B active | 07d35212591f |
| Stretch, fit table only | `gpt-oss:120b` | MoE, 117B total, 5.1B active, MXFP4 | a951a23b46a1 |
| Frontier reference | Claude Opus 5 | Imported from No. 02, not re-run | No. 02 test runs r1 to r3 |
| Resident anchors | No. 02's four local models | Imported from No. 02, not re-run | No. 02 manifests |

Local digests are checked against the snapshot on pull; a mismatch stops the study.

gpt-oss:120b was the second MoE pick by the rule. It did not load usably on the reference
machine (Section 10), so under the replacement rule (`ops/field_03.py replace`: the next-ranked
current family in the class, from a developer the class does not already have, decided on load
alone and before any scored run) `qwen3.6:35b-a3b-q4_K_M` takes its place. gpt-oss:120b is
reported in the fit table as the stretch result.

## 3. How each subject is called

Unchanged from No. 02 Section 3: `report02/src/run.py`, byte-identical system and user text,
temperature 0, top_p 0.9, repeat_penalty 1.0, num_ctx 16384, per-task generation budget,
constrained JSON where No. 02 used it. Ollama 0.34.2 with flash attention on and a q8_0 KV
cache, confirmed from the server's startup log before every run. Frozen prompt hashes
(`report02/prompts/HASHES.json`) are checked by the runner before any test-split run.

Layer placement is left to Ollama. No field model is forced on or off the GPU; the spill a
reader sees is what the runtime chose on this machine.

Thinking, passed explicitly on every call: `off` for all four field models, matching No. 02's
main arm. The fit probe and the dev split (one item per task per model, 28 items) confirmed each
model answers every task with no reasoning tokens, stops on its own, and produces output the
graders parse without a problem.

## 4. Roles and blinding

Unchanged from No. 02 Section 4. The frontier column is No. 02's Claude Opus 5 test runs,
dated 2026-09-21 and 2026-09-22, produced from the same prompt hashes on the same items. No
new frontier subject calls are made.

## 5. Corpus and split

No. 02's corpus, keys and test split, unchanged. Items scored per field model:

| Task | Items | Note |
|---|---|---|
| T1 fund term extraction | 9 | full |
| T2 change detection | 22 | full, gap task |
| T3 grounded Q&A | 40 | firm pack `t3_f04` only |
| T4 filing brief | 12 | full, gap task |
| T5 meeting to CRM | 9 | full, gap task |
| T6 client drafting | 15 | full |
| T7 marketing review | 20 | full, gap task |

The T3 pack was chosen before any field model ran, using No. 02 results only: the pack whose
primary and hallucination scores deviate least from the full 120 items, summed over No. 02's
five subjects (f04 7.8 points, f03 9.5, f02 10.0). Every comparison on T3 pairs the field
model's 40 items with the frontier's results on the same 40 items.

## 6. Tasks and metrics

Unchanged from No. 02 Section 6.

## 7. Grading

Unchanged from No. 02 Section 7, including every amendment in No. 02 Section 13 (regex-miss
adjudication and list pairing), applied to field models exactly as to No. 02's subjects.
Judge verdicts are cached; No. 02's cached verdicts are reused where the unit is identical.

## 8. Tiers

No. 02 Section 8, unchanged, against the frontier's mean over its three No. 02 runs.

## 9. Statistics

- **One run per field model per task.** No. 02 ran every local subject three times, and runs two
  and three reproduced run one exactly on every model and task (No. 02 run-to-run table).
- Paired cluster bootstrap of field minus frontier, 10,000 resamples, No. 02's seed and
  clusters. If the interval contains a tier boundary, the paper says so next to the tier.
- Where a primary metric lands within one point of a tier boundary, that task is run a second
  time and both runs are reported.

## 10. The reference machine and the resident-versus-spilled control

Reference machine: one RTX 5070 (12 GB), Ryzen 7 7700X, 63 GB system memory, Windows 11,
the desktop's normal background workload running (about 34 GB of system memory available at
the field snapshot). It is a deliberately modest floor, not a recommended deployment.

**Control.** `gemma4:12b` is rerun on T1, T6 and the T3 pack with 24 of its 48 layers forced
into system memory (`--num-gpu 24`, spill fraction 0.50), everything else identical to No. 02's
main arm, and its outputs are compared byte for byte with No. 02's resident run 1, after the
same grading and adjudication. Two checks guard the comparison: a fresh resident T1 run today
(rules out drift since No. 02) and a repeat of the spilled run (tests whether the spilled path
is itself deterministic). The control ran on 2026-09-23 before registration: it tests the
runtime, not a subject, and no analysis choice below depends on it. Result, recorded here
because it is already known (`ops/control_03.json`):

- Fresh resident T1: 9 of 9 items byte-identical to No. 02 run 1. No drift.
- Spilled repeat: byte-identical to the first spilled run on both items run.
- Spilled against resident: T1 0 of 9 identical, T6 0 of 15, T3 26 of 40. Primary metric
  T1 97.8 to 96.7, T6 94.8 to 94.8, T3 95.0 to 95.0; hallucination metrics unchanged on all
  three.

So placement changes the tokens and each placement is deterministic. The paper therefore does
not claim that a model emits the same text on a faster machine. It claims what was measured:
moving half the layers out of graphics memory changed the wording of most answers and moved
the scores by at most about a point, with no change in hallucination.

## 11. Operational metrics

Per field model and task, on the reference machine: seconds per item, output tokens per
second, prompt tokens per second, time to first token (prompt evaluation time with the model
already loaded), peak graphics memory, **spill fraction** (`1 - size_vram / size` from the
Ollama load), system memory high-water, and total wall clock. Per model: the Section 6
arithmetic of the plan (per-layer cache size from the model's own metadata), measured load
footprint and measured overhead, and the smallest single card that would hold the model
resident at 16K, from the manufacturer's specification page. Every speed figure is labeled
as a measurement of the reference machine.

**Ten-hour ceiling.** Each field model has ten hours of test-split wall clock. The plan's five
hours was set before any measurement; the fit probe projects the slowest field model at 8.35
hours and the field at about 16 hours in total, inside the plan's GPU budget, so the ceiling
was raised before registration to let every model finish every task. Tasks run in
the order T2, T4, T5, T7, T1, T6, T3, so the gap tasks come first. A model that reaches the
ceiling is stopped mid-task and recorded as **did not complete**: every task it finished is
graded and tiered, a task it did not finish is reported as items completed out of items
scheduled and is not tiered, and the paper names memory bandwidth on the reference machine as
the reason. A model that does not load, or does not answer a dev item, is reported in the fit
table only.

## 12. Published regardless of outcome

Every field model on every task it finished, gap closed or not. A null result goes on the
cover. The control result, whichever way it lands. The fit table for every field model,
including any that did not load. Raw outputs, reasoning traces, manifests and
`ops/field_03.json` in the public repository before the paper is published.

## 13. Deviations

**2026-09-23, after registration, during the test split. `src/build_results_03.py` extended.**
The exhibit build added data sections to the results builder (`spill_curve`, `size_ladder`,
`hardware`) and made model class and parameter counts come from Ollama's own metadata instead of
typed values. No metric, tier, bootstrap, item set or subject changed: the tier, primary metric
and confidence interval of all 14 field-model task results available at the time were compared
before and after the edit and are identical. Registered hash `5963c18ce1381a98`, new hash
`05654af7a555d8ff`.

**2026-09-23 19:30, test split paused for about four and a half hours.** The GPU was released to
the owner until midnight. The queue was stopped mid-task (qwen3.8, T2, 20 of 22 items saved);
the elapsed 1.82 hours were credited to that model's ten-hour ceiling, the in-flight item is
rerun on resume, and per-item timings are unaffected because every item is timed on its own.

**2026-09-24, after scoring, while writing the paper. The frontier column is one run per item.**
Sections 2 and 8 above describe the frontier as No. 02's test runs r1 to r3 and tier against its
mean over three runs. No. 02 ran Claude Opus 5 once per test item (No. 02 pre-registration,
deviation of 2026-09-22, logged before any test-split run), so every frontier figure and tier in
this report is against that single run, as in No. 02. The data never held more than one frontier
run per item, so no metric, tier or interval changes; `meta.frontier_source` in `results.json`,
which repeated "r1 to r3", is corrected.

**2026-09-24, after scoring, while writing the paper. `src/build_results_03.py` extended again.**
Four records were added to `results.json`, none of them a metric: the registered hash and time of
this file from `ops/REGISTRATION.json`, each field model's wall clock as the queue counted it
(`ops/queue_state.json`, model loads included), the byte comparison of the second spilled control
run with the first, and the corrected frontier source above. Every metric, tier and interval was
compared before and after the edit and is identical.

**2026-09-24, after scoring, reporting change: speed and run time are not reported.** Section 11
listed per-model speed, time to first token and wall clock on the reference machine. At the
founder's direction the paper and the website report quality only. The reason is the one Section
10 already gives: the reference machine is a deliberately modest floor that held every field model
partly in system memory, while a client deployment sizes the graphics card to hold the whole model,
so run times measured here describe no machine a client would buy. No run time on other hardware
is claimed, because none was measured. The timing data stays in `results.json` and the run
manifests and will be in the public repository. No metric, tier or item set changed.
