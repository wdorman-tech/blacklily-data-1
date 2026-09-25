"""Hardware sizing table for Report No. 03 (plan Section 6, exhibit 7).

    python report03/ops/cards_03.py

For every model that loaded in the fit probe, the smallest current NVIDIA card whose stated memory
holds the measured loaded footprint at 16K context plus the measured desktop reserve. gpt-oss:120b,
which did not load, gets two analytic rows labeled "not measured". Writes report03/ops/cards_03.json.

Each row compares its card margin with the generation excess measured for that same model (graphics
memory at peak beyond what Ollama placed there). No model's excess stands in for another's.

Reads files only: no model is loaded and the GPU is not queried. Every measured number comes from
report03/ops/fit_03.json, report03/ops/field_03.json, report03/results.json, report02/ops/fit.json,
the report02 run manifests, or report03/ops/show_03.json once it exists. show_03.json holds the
per-layer inputs that gemma4:12b's legacy fit entry and the No. 02 rows lack; it is written later by
fit_probe_03.arithmetic(), which calls /api/show only and loads nothing. Until then those cells are
"pending". The card facts below are external facts, each quoted verbatim from the manufacturer's own
specification page on nvidia.com, never a retailer.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

R3 = Path(__file__).resolve().parent.parent
R2 = R3.parent / "report02"
sys.path.insert(0, str(R2 / "src"))
from common import model_slug, write_json

GB, GIB, MIB = 10**9, 2**30, 2**20
CHECKED = "2026-09-23"
GEFORCE = "https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/"
PRO = "https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/"
GEFORCE_SECTION = "Specifications: Memory Specs, Standard Memory Config"
PRO_SECTION = "Specifications: Memory Configuration"

# memory_gb_stated is the number printed on the page; memory_as_stated is the page's own string.
CARDS: list[dict] = [
    {"card": "GeForce RTX 5070", "line": "GeForce RTX 50 series", "memory_gb_stated": 12,
     "memory_as_stated": "12 GB GDDR7", "url": GEFORCE + "rtx-5070-family/", "section": GEFORCE_SECTION,
     "note": "the reference machine's card"},
    {"card": "GeForce RTX 5060 Ti 16 GB", "line": "GeForce RTX 50 series", "memory_gb_stated": 16,
     "memory_as_stated": "16 GB / 8 GB GDDR7", "url": GEFORCE + "rtx-5060-family/", "section": GEFORCE_SECTION,
     "note": "the page lists two memory variants; only the 16 GB variant is in the card list"},
    {"card": "GeForce RTX 5070 Ti", "line": "GeForce RTX 50 series", "memory_gb_stated": 16,
     "memory_as_stated": "16 GB GDDR7", "url": GEFORCE + "rtx-5070-family/", "section": GEFORCE_SECTION},
    {"card": "GeForce RTX 5080", "line": "GeForce RTX 50 series", "memory_gb_stated": 16,
     "memory_as_stated": "16 GB GDDR7", "url": GEFORCE + "rtx-5080/", "section": GEFORCE_SECTION},
    {"card": "NVIDIA RTX PRO 4000 Blackwell", "line": "RTX PRO Blackwell workstation", "memory_gb_stated": 24,
     "memory_as_stated": "24GB GDDR7 with error-correcting code (ECC)", "url": PRO + "rtx-pro-4000/",
     "section": PRO_SECTION},
    {"card": "GeForce RTX 5090", "line": "GeForce RTX 50 series", "memory_gb_stated": 32,
     "memory_as_stated": "32 GB GDDR7", "url": GEFORCE + "rtx-5090/", "section": GEFORCE_SECTION},
    {"card": "NVIDIA RTX PRO 4500 Blackwell Workstation Edition", "line": "RTX PRO Blackwell workstation",
     "memory_gb_stated": 32, "memory_as_stated": "32GB GDDR7 with error-correcting code (ECC)",
     "url": PRO + "rtx-pro-4500/", "section": PRO_SECTION},
    {"card": "NVIDIA RTX PRO 5000 Blackwell 48 GB", "line": "RTX PRO Blackwell workstation", "memory_gb_stated": 48,
     "memory_as_stated": "48 GB GDDR7 with ECC", "url": PRO + "rtx-pro-5000/", "section": PRO_SECTION,
     "note": "the page lists a 48 GB and a 72 GB variant"},
    {"card": "NVIDIA RTX PRO 5000 Blackwell 72 GB", "line": "RTX PRO Blackwell workstation", "memory_gb_stated": 72,
     "memory_as_stated": "72 GB GDDR7 with ECC", "url": PRO + "rtx-pro-5000/", "section": PRO_SECTION,
     "note": "the page lists a 48 GB and a 72 GB variant"},
    {"card": "NVIDIA RTX PRO 6000 Blackwell Workstation Edition", "line": "RTX PRO Blackwell workstation",
     "memory_gb_stated": 96, "memory_as_stated": "96 GB GDDR7 with error-correcting code (ECC)",
     "url": PRO + "rtx-pro-6000/", "section": PRO_SECTION},
]
# Cards named in the task that nvidia.com did not state memory for. Checked 2026-09-23: none.
DROPPED: list[dict] = []

# The hypothetical memory kit of plan Section 3, Arm B. An input to the analytic row, not a measurement.
UPGRADE_RAM_GB = 128
# No. 03 main arm (thinking off) and No. 02's non-thinking models, both at 16K. Excludes the -gpuNN control.
MAIN_ARM_RUNS = ("test-default-thinkoff-ctx16384-r1", "test-default-ctx16384-r1")
NO2_BASELINE = "resident baseline (No. 02)"

FIT_REL, SHOW_REL = "report03/ops/fit_03.json", "report03/ops/show_03.json"
SHOW = R3 / "ops" / "show_03.json"
PENDING_HOW = ("when the GPU is free, call report03/ops/fit_probe_03.py's arithmetic(model, size_bytes) for each "
               "pending model (it issues /api/show only and loads no model), save the results to "
               f"{SHOW_REL} as {{model: arithmetic}}, and rerun this script")
SENSITIVITY = {"if_gb_read_as_gib": "if GB is read as GiB",
               "if_gb_read_at_reference_driver_scale": "at the scale the reference card's driver reports"}


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def gb(b: float | None) -> float | None:
    return None if b is None else round(b / GB, 2)


def gib(b: float | None) -> float | None:
    return None if b is None else round(b / GIB, 2)


def check_cards() -> None:
    for c in CARDS:
        n = c["memory_gb_stated"]
        if f"{n} GB" not in c["memory_as_stated"] and f"{n}GB" not in c["memory_as_stated"]:
            raise SystemExit(f"{c['card']}: {n} does not appear in the quoted string {c['memory_as_stated']!r}")
        if not c["url"].startswith("https://www.nvidia.com/"):
            raise SystemExit(f"{c['card']}: source is not nvidia.com")


def smallest(need_bytes: int, unit_bytes: float) -> dict:
    """Smallest memory tier in CARDS that holds need_bytes, reading the stated GB as unit_bytes each."""
    for tier in sorted({c["memory_gb_stated"] for c in CARDS}):
        cap = round(tier * unit_bytes)
        if cap >= need_bytes:
            return {"tier_gb_stated": tier, "cards": [c["card"] for c in CARDS if c["memory_gb_stated"] == tier],
                    "capacity_bytes": cap, "margin_bytes": cap - need_bytes}
    return {"tier_gb_stated": None, "cards": [], "capacity_bytes": None, "margin_bytes": None}


def reading(need: int, unit_bytes: float, excess: int | None) -> dict:
    r = smallest(need, unit_bytes)
    r["margin_gb"] = gb(r["margin_bytes"])
    known = excess is not None and r["margin_bytes"] is not None
    r["margin_covers_generation_excess"] = r["margin_bytes"] >= excess if known else None
    r["margin_after_own_excess_bytes"] = r["margin_bytes"] - excess if known else None
    r["margin_after_own_excess_gb"] = gb(r["margin_after_own_excess_bytes"])
    return r


def own_excess(e: dict, src: str) -> dict:
    """This model's graphics memory at peak beyond the part of its loaded footprint Ollama placed there."""
    peak, before, vram, loaded = e.get("peak_vram_mib"), e.get("vram_before_mib"), e.get("size_vram_bytes"), \
        e.get("loaded_size_bytes")
    if peak is None or before is None or not vram:
        return {"status": "not measured", "bytes": None, "gb": None, "why": f"{src} has no peak and before reading"}
    rise = (peak - before) * MIB
    if rise < vram:
        return {"status": "not measured", "bytes": None, "gb": None,
                "why": (f"{src} records vram_before_mib {before:,} and peak_vram_mib {peak:,}: graphics memory rose "
                        f"by {rise:,} B, less than the {vram:,} B Ollama placed there, so the before reading was "
                        "taken with an earlier model still resident")}
    x = rise - vram
    spilled = vram < loaded
    out = {"status": "measured", "bytes": x, "gb": gb(x), "source": src,
           "placement": "spilled" if spilled else "fully resident",
           "arithmetic": (f"(peak {peak:,} MiB - before {before:,} MiB) x 2^20 B = {rise:,} B, minus the {vram:,} B "
                          f"Ollama placed in graphics memory = {x:,} B = {gb(x)} GB")}
    if spilled:
        out["caveat"] = (f"measured while spilled ({1 - vram / loaded:.1%} of the loaded footprint in system memory): "
                         "the compute buffer of a split load may differ from that of a fully resident load on a "
                         "larger card, so this excess may not carry over to a fully resident load")
    return out


def verdict(need: int, excess: dict, s: dict) -> dict:
    dec, x = s["smallest_card"], excess["bytes"]
    t = dec["tier_gb_stated"]
    if t is None:
        return {"status": "no card", "note": f"need {gb(need)} GB exceeds every card in the list"}
    if x is None:
        return {"status": "unknown",
                "note": (f"this model's generation excess is unknown ({excess['why']}), so whether the margin covers "
                         "it is unknown; no other model's measurement stands in for it")}
    if dec["margin_covers_generation_excess"]:
        return {"status": "covered",
                "note": (f"the {dec['margin_gb']} GB margin covers this model's own generation excess of {gb(x)} GB "
                         f"with {dec['margin_after_own_excess_gb']} GB left")}
    alt = [k for k in SENSITIVITY if s[k]["tier_gb_stated"] == t and s[k]["margin_covers_generation_excess"]]
    note = (f"need {gb(need)} GB + this model's own generation excess {gb(x)} GB = {gb(need + x)} GB, more than "
            f"{t} x 10^9 B: the {dec['margin_gb']} GB margin is {gb(-dec['margin_after_own_excess_bytes'])} GB short")
    if alt:
        note += "; the same card covers it " + " and ".join(
            f"{SENSITIVITY[k]} ({s[k]['margin_after_own_excess_gb']} GB left)" for k in alt)
    if excess.get("caveat"):
        note += "; the excess was measured while spilled and may not carry over to a fully resident load"
    return {"status": "marginal" if alt else "not covered", "note": note}


def sizing(need: int, excess: dict, driver_unit: float) -> dict:
    """The answer under the decimal reading, two sensitivity readings, and the margin against this model's own
    generation excess under each. The excess is never taken from another model."""
    x = excess["bytes"]
    dec = reading(need, GB, x)
    out: dict = {"smallest_card": dec}
    for key, unit in (("if_gb_read_as_gib", GIB), ("if_gb_read_at_reference_driver_scale", driver_unit)):
        r = reading(need, unit, x)
        r["changes_answer"] = r["tier_gb_stated"] != dec["tier_gb_stated"]
        if r["changes_answer"] and r["tier_gb_stated"] is not None:
            r["note"] = (f"{SENSITIVITY[key]}, the answer moves to the {r['tier_gb_stated']} GB tier with a "
                         f"{r['margin_gb']} GB margin, "
                         + (f"{r['margin_after_own_excess_gb']} GB after this model's own generation excess"
                            if x is not None else "and this model's generation excess is unknown"))
        out[key] = r
    if x is not None:
        wx = smallest(need + x, GB)
        out["with_own_generation_excess"] = {
            "need_bytes": need + x, "need_gb": gb(need + x),
            "arithmetic": (f"need {need:,} B + this model's own generation excess {x:,} B = {need + x:,} B = "
                           f"{gb(need + x)} GB"),
            "tier_gb_stated": wx["tier_gb_stated"], "cards": wx["cards"], "margin_gb": gb(wx["margin_bytes"]),
            "changes_answer": wx["tier_gb_stated"] != dec["tier_gb_stated"],
        }
    out["verdict"] = verdict(need, excess, out)
    return out


def manifest_check(model: str, loaded: int | None, vram: int | None) -> dict:
    """Loaded footprint in the scored runs' manifests, against the fit probe's."""
    seen: dict[tuple, list[str]] = {}
    for run in MAIN_ARM_RUNS:
        for p in sorted((R2 / "runs" / model_slug(model)).glob(f"*/{run}/_manifest.json")):
            ld = load(p).get("loaded") or {}
            if ld.get("size_bytes"):
                seen.setdefault((ld["size_bytes"], ld.get("size_vram_bytes")), []).append(p.parent.parent.name)
    if not seen:
        return {"manifests": 0, "note": "no main-arm manifest with a loaded block yet"}
    return {"manifests": sum(len(v) for v in seen.values()),
            "distinct": [{"size_bytes": k[0], "size_vram_bytes": k[1], "tasks": v} for k, v in seen.items()],
            "matches_probe": list(seen) == [(loaded, vram)]}


def pending_kv(note: str, **extra: object) -> dict:
    return {**extra, "kv_bytes_at_ctx": None, "kv_gb_at_ctx": None, "status": "pending", "note": note,
            "resolve": PENDING_HOW}


def pending_fields(row: dict) -> list[str]:
    """Cells that a rendered table must show as 'pending', never blank or zero."""
    vals = {"parameters": row["parameters"], "bits_per_weight": row["bits_per_weight"],
            "kv_bytes_at_ctx": row["kv"]["kv_bytes_at_ctx"], "computed_footprint_bytes": row["computed_footprint_bytes"],
            "measured_overhead_bytes": row["measured_overhead_bytes"]}
    return [k for k, v in vals.items() if v is None]


def kv_block(a: dict, ctx: int) -> dict:
    if "attention_layers" not in a:
        return pending_kv("this fit_03.json entry predates the per-layer arithmetic (plan Section 6 correction); "
                          "its cache figure exceeds the whole non-weight footprint, so it is not used. KV, computed "
                          "footprint and measured overhead are pending until the per-layer inputs are read.",
                          method="legacy (plain-transformer formula, every layer at full context)",
                          kv_bytes_at_ctx_in_file=a.get("kv_bytes_at_ctx"))
    full = a["kv_bytes_per_token_full_layers_q8_0"] * ctx
    rest = a["kv_bytes_at_ctx"] - full
    lines = [(f"full-context attention layers: {a['kv_bytes_per_token_full_layers_q8_0']:,} B/token x {ctx:,} "
             f"tokens = {full:,} B")]
    if a["sliding_window_layers"]:
        lines.append(f"sliding-window layers ({a['sliding_window_layers']} of {a['attention_layers']}, window "
                     f"{a['sliding_window']:,} tokens): {rest:,} B")
    if a.get("full_attention_interval"):
        lines.append(f"hybrid: {a['attention_layers']} of {a['block_count']} layers keep a KV cache (every "
                     f"{a['full_attention_interval']}th); the recurrent state of the rest lands in overhead")
    lines.append(f"total at {ctx:,} tokens, q8_0 (1.0625 B/element): {a['kv_bytes_at_ctx']:,} B = "
                 f"{gb(a['kv_bytes_at_ctx'])} GB")
    return {"method": "per-layer (plan Section 6)", "attention_layers": a["attention_layers"],
            "block_count": a["block_count"], "sliding_window_layers": a["sliding_window_layers"],
            "sliding_window": a["sliding_window"], "head_count_kv": a["head_count_kv"],
            "key_length": a["key_length"], "value_length": a["value_length"],
            "kv_bytes_per_token_full_layers_q8_0": a["kv_bytes_per_token_full_layers_q8_0"],
            "kv_bytes_at_ctx": a["kv_bytes_at_ctx"], "kv_gb_at_ctx": gb(a["kv_bytes_at_ctx"]), "arithmetic": lines}


def model_row(model: str, e: dict, klass: str, active_b: float | None, reserve: int, show: dict,
              driver_unit: float) -> dict:
    ctx, weights, loaded, vram = e["num_ctx"], e["size_bytes"], e["loaded_size_bytes"], e["size_vram_bytes"]
    a, src = e["arithmetic"], FIT_REL
    if "attention_layers" not in a and model in show:
        a, src = show[model], SHOW_REL
    kv = {**kv_block(a, ctx), "source": src}
    kv_bytes = kv["kv_bytes_at_ctx"]
    computed = weights + kv_bytes if kv_bytes is not None else None
    overhead = loaded - weights - kv_bytes if kv_bytes is not None else None
    # fit_03.json's own overhead figure is only comparable when its own per-layer arithmetic produced the KV.
    if overhead is not None and src == FIT_REL and overhead != e["measured_overhead_bytes"]:
        raise SystemExit(f"{model}: overhead {overhead} disagrees with fit_03.json {e['measured_overhead_bytes']}")
    resident = round(vram / loaded, 4)
    if abs(resident - (1 - e["spill_fraction"])) > 1e-4:
        raise SystemExit(f"{model}: resident fraction {resident} disagrees with spill_fraction {e['spill_fraction']}")
    need = loaded + reserve
    ref_tier = next(c["memory_gb_stated"] for c in CARDS if c.get("note") == "the reference machine's card")
    fits_ref = ref_tier * GB >= need
    excess = own_excess(e, FIT_REL)
    row = {
        "model": model, "class": klass,
        "parameters": a["parameter_count"], "active_parameters_b_library": active_b,
        "quantization": (e.get("details") or {}).get("quantization_level"),
        "bits_per_weight": a["bits_per_weight"], "context_tokens": ctx,
        "weights_file_bytes": weights, "weights_file_gb": gb(weights),
        "kv": kv,
        "computed_footprint_bytes": computed, "computed_footprint_gb": gb(computed),
        "loaded_footprint_bytes": loaded, "loaded_footprint_gb": gb(loaded), "loaded_footprint_gib": gib(loaded),
        "loaded_minus_weights_bytes": loaded - weights,
        "measured_overhead_bytes": overhead, "measured_overhead_gb": gb(overhead),
        "size_vram_bytes_reference_machine": vram,
        "resident_fraction_reference_machine": resident,
        "manifest_check": manifest_check(model, loaded, vram),
        "need_bytes": need, "need_gb": gb(need),
        "need_arithmetic": f"loaded {loaded:,} B + desktop reserve {reserve:,} B = {need:,} B = {gb(need)} GB",
        "generation_excess": excess,
        **sizing(need, excess, driver_unit),
        "rule_check_on_reference_card": {"fits_by_rule": fits_ref, "fully_resident_measured": bool(e["fully_on_gpu"]),
                                         "agree": fits_ref == bool(e["fully_on_gpu"])},
    }
    row["pending"] = pending_fields(row)
    return row


def no2_row(model: str, e: dict, reserve: int, show: dict, driver_unit: float) -> dict:
    loaded, vram, weights, ctx = e["loaded_size_bytes"], e["size_vram_bytes"], e["size_bytes"], e["context_length"]
    a = show.get(model)
    kv = ({**kv_block(a, ctx), "source": SHOW_REL} if a else
          pending_kv("report02/ops/fit.json holds no per-layer inputs and no numeric parameter count", source=None))
    kv_bytes = kv["kv_bytes_at_ctx"]
    computed = weights + kv_bytes if kv_bytes is not None else None
    overhead = loaded - weights - kv_bytes if kv_bytes is not None else None
    need = loaded + reserve
    excess = own_excess(e, "report02/ops/fit.json")
    row = {
        "model": model, "class": NO2_BASELINE,
        "parameters": a["parameter_count"] if a else None, "parameter_size_library": e["details"]["parameter_size"],
        "quantization": e["details"]["quantization_level"],
        "bits_per_weight": a["bits_per_weight"] if a else None, "context_tokens": ctx,
        "weights_file_bytes": weights, "weights_file_gb": gb(weights),
        "kv": kv,
        "computed_footprint_bytes": computed, "computed_footprint_gb": gb(computed),
        "loaded_footprint_bytes": loaded, "loaded_footprint_gb": gb(loaded), "loaded_footprint_gib": gib(loaded),
        "loaded_minus_weights_bytes": loaded - weights,
        "measured_overhead_bytes": overhead, "measured_overhead_gb": gb(overhead),
        "size_vram_bytes_reference_machine": vram,
        "resident_fraction_reference_machine": round(vram / loaded, 4),
        "manifest_check": manifest_check(model, loaded, vram),
        "need_bytes": need, "need_gb": gb(need),
        "need_arithmetic": f"loaded {loaded:,} B + desktop reserve {reserve:,} B = {need:,} B = {gb(need)} GB",
        "generation_excess": excess,
        **sizing(need, excess, driver_unit),
    }
    row["pending"] = pending_fields(row)
    return row


def stretch_row(model: str, e: dict, klass: str, active_b: float | None, installed_gb: float,
                reserve: int, driver_unit: float) -> dict:
    lo = e["load_observed"]
    gpu_b, cpu_b = round(lo["gpu_model_buffer_mib"] * MIB), round(lo["cpu_model_buffer_mib"] * MIB)
    kv = {**kv_block(e["arithmetic"], e["num_ctx"]), "source": FIT_REL}
    need = gpu_b + cpu_b + kv["kv_bytes_at_ctx"] + reserve
    unknown = {"status": "unknown", "bytes": None, "gb": None,
               "why": "the model did not load, so its compute buffer during generation was never observed"}
    fit_a = sizing(need, unknown, driver_unit)

    avail_now = round(lo["sys_available_before_gb"] * GB)
    installed_now = round(installed_gb * GIB)
    other_use = installed_now - avail_now
    installed_up = UPGRADE_RAM_GB * GB
    avail_up = installed_up - other_use
    private_b = round(lo["runner_private_gb_at_abort"] * GIB)
    host_need = max(cpu_b, private_b)
    left = avail_up - host_need
    gpu_side = gpu_b + kv["kv_bytes_at_ctx"] + reserve
    return {
        "model": model, "class": klass, "parameters": e["arithmetic"]["parameter_count"],
        "active_parameters_b_library": active_b, "bits_per_weight": e["arithmetic"]["bits_per_weight"],
        "context_tokens": e["num_ctx"], "loaded": e["loaded"], "outcome": e["outcome"],
        "weights_file_bytes": e["size_bytes"], "weights_file_gb": gb(e["size_bytes"]),
        "kv": kv,
        "observed_at_load": {
            "at": lo["at"], "source": "Ollama runner log during the aborted load (fit_03.json load_observed)",
            "gpu_model_buffer_mib": lo["gpu_model_buffer_mib"], "gpu_model_buffer_bytes": gpu_b,
            "gpu_model_buffer_gb": gb(gpu_b), "gpu_model_buffer_gib": gib(gpu_b),
            "cpu_model_buffer_mib": lo["cpu_model_buffer_mib"], "cpu_model_buffer_bytes": cpu_b,
            "cpu_model_buffer_gb": gb(cpu_b), "cpu_model_buffer_gib": gib(cpu_b),
            "buffers_sum_bytes": gpu_b + cpu_b, "weights_file_bytes": e["size_bytes"],
            "units_note": f"the runner logs MiB. {lo['gpu_model_buffer_mib']} MiB is {gb(gpu_b)} GB or "
                          f"{gib(gpu_b)} GiB; {lo['cpu_model_buffer_mib']} MiB is {gb(cpu_b)} GB or {gib(cpu_b)} GiB. "
                          "A figure written as the MiB value divided by 1,000 is neither unit.",
            "layers_on_gpu": lo["layers_on_gpu"], "load_mode": lo["load_mode"],
        },
        "analytic_not_measured": {
            "a_smallest_single_card": {
                "label": "not measured: arithmetic only, no such card was tested",
                "need_bytes": need, "need_gb": gb(need),
                "arithmetic": [
                    f"GPU model buffer {lo['gpu_model_buffer_mib']} MiB = {gpu_b:,} B",
                    f"+ CPU model buffer {lo['cpu_model_buffer_mib']} MiB = {cpu_b:,} B",
                    f"+ KV cache at {e['num_ctx']:,} tokens, per-layer arithmetic = {kv['kv_bytes_at_ctx']:,} B",
                    f"+ desktop reserve = {reserve:,} B",
                    f"= {need:,} B = {gb(need)} GB",
                    ("the compute buffer used during generation is unknown for this model: it never generated on "
                     "the reference machine, the buffer is not included in the need, and no other model's "
                     "measurement stands in for it, so margin_covers_generation_excess is null"),
                ],
                "generation_compute_buffer": "unknown for this model: never observed, not included",
                **fit_a,
            },
            "b_reference_machine_with_more_memory": {
                "label": f"not measured: the reference machine with {UPGRADE_RAM_GB} GB of system memory "
                         f"instead of {installed_gb:g} was not tested",
                "question": "is there room for the CPU model buffer",
                "arithmetic": [
                    f"installed now: {installed_gb:g} GB, read as GiB = {installed_now:,} B",
                    f"available before the load (measured): {lo['sys_available_before_gb']} GB = {avail_now:,} B",
                    (f"desktop workload and system use = {installed_now:,} - {avail_now:,} = {other_use:,} B "
                    f"({gb(other_use)} GB), assumed unchanged after the upgrade"),
                    f"upgrade: {UPGRADE_RAM_GB} GB, read as 10^9 B each (conservative) = {installed_up:,} B",
                    (f"available after the upgrade = {installed_up:,} - {other_use:,} = {avail_up:,} B "
                    f"({gb(avail_up)} GB)"),
                    (f"host memory needed, at least: the larger of the CPU model buffer {cpu_b:,} B and the runner's "
                    f"private memory when the load was aborted, {lo['runner_private_gb_at_abort']} GB read as GiB = "
                    f"{private_b:,} B, so {host_need:,} B ({gb(host_need)} GB)"),
                    f"left over = {avail_up:,} - {host_need:,} = {left:,} B ({gb(left)} GB)",
                    (f"GPU side, unchanged by the upgrade: buffer {gpu_b:,} B + KV {kv['kv_bytes_at_ctx']:,} B + "
                    f"desktop reserve {reserve:,} B = {gpu_side:,} B ({gb(gpu_side)} GB); the buffer was "
                    "allocated on the reference card during the observed load"),
                ],
                "available_after_upgrade_bytes": avail_up, "host_need_lower_bound_bytes": host_need,
                "left_over_bytes": left, "left_over_gb": gb(left),
                "room_for_cpu_buffer": left > 0,
                "caveats": [
                    "the runner's private memory is a lower bound: the load was aborted before it finished",
                    "room to hold the model is not a speed claim; no speed is estimated for this configuration",
                    "the desktop's other memory use is assumed to stay at the level measured before the load",
                ],
            },
        },
    }


def main() -> None:
    check_cards()
    fit = load(R3 / "ops" / "fit_03.json")
    field = load(R3 / "ops" / "field_03.json")
    hw = load(R3 / "results.json")["hardware"]
    no2 = load(R2 / "ops" / "fit.json")

    klass = {m: c for c, ms in field["field"].items() for m in ms}
    klass.update({m: v["class"] for m, v in field["did_not_load"].items()})
    active = {c["build"]["tag"]: c["active_b"] for c in field["candidates"]}

    before = {m: e["vram_before_mib"] for m, e in fit.items() if e.get("vram_before_mib") is not None}
    reserve_src = min(before, key=before.get)
    reserve_mib = before[reserve_src]
    reserve = reserve_mib * MIB

    show = load(SHOW) if SHOW.exists() else {}

    totals = sorted({g["vram_total_mib"] for p in (R2 / "runs").glob("*/*/*/_manifest.json")
                     for g in [(load(p).get("gpu_before") or {})] if g.get("vram_total_mib")})
    if not totals:
        raise SystemExit("no report02 run manifest records gpu_before.vram_total_mib; the driver-scale reading needs one")
    ref_card = next(c for c in CARDS if c.get("note") == "the reference machine's card")
    ref_label = (f"the reference machine: {hw['gpu']} ({ref_card['memory_gb_stated']} GB), {hw['cpu']}, "
                 f"{hw['ram_gb']} GB system memory, {hw['os']}")
    # Bytes per stated GB on the one card whose driver was read; the smallest total if several were recorded.
    driver_unit = min(totals) * MIB / ref_card["memory_gb_stated"]

    rows = [model_row(m, e, klass.get(m, NO2_BASELINE), active.get(m), reserve, show, driver_unit)
            for m, e in fit.items() if e.get("loaded_size_bytes")]
    no2_rows = [no2_row(m, e, reserve, show, driver_unit) for m, e in no2.items() if m not in fit]
    stretch = [stretch_row(m, e, klass[m], active.get(m), hw["ram_gb"], reserve, driver_unit)
               for m, e in fit.items() if e.get("loaded") is False]
    excess_by_model = {r["model"]: {k: r["generation_excess"].get(k) for k in ("status", "bytes", "gb", "placement")}
                       for r in rows + no2_rows}
    excess_by_model.update({s["model"]: {"status": "unknown", "bytes": None, "gb": None, "placement": None}
                            for s in stretch})
    pending = {r["model"]: r["pending"] for r in rows + no2_rows if r["pending"]}
    spilled = [r["model"] for r in rows if r["generation_excess"].get("placement") == "spilled"]
    unmeasured = [r["model"] for r in rows + no2_rows if r["generation_excess"]["bytes"] is None]

    out = {
        "generated_by": "report03/ops/cards_03.py", "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": "plan Section 6 and exhibit 7: the smallest single current NVIDIA card whose stated memory "
                   "holds each model's measured loaded footprint plus the measured desktop reserve",
        "reference_machine": ref_label,
        "settings": {"context_tokens": sorted({e["num_ctx"] for e in fit.values()}),
                     "kv_cache": sorted({e["server"]["kv_cache_type"] for e in fit.values() if e.get("server")}),
                     "flash_attention": sorted({e["server"]["flash_attention"] for e in fit.values() if e.get("server")}),
                     "num_parallel": sorted({e["server"]["num_parallel"] for e in fit.values() if e.get("server")})},
        "units": {
            "assumption": "NVIDIA's spec pages state memory in GB and none of them defines GB. This table reads "
                          "NVIDIA GB as 10^9 bytes (decimal), the conservative reading, and applies it to every card "
                          "and every row. Ollama reports bytes; nvidia-smi and the runner log report MiB (2^20 B).",
            "evidence_against_decimal": {
                "vram_total_mib_reported_by_driver": totals,
                "card": ref_card["card"], "memory_as_stated": ref_card["memory_as_stated"],
                "driver_total_bytes": [t * MIB for t in totals],
                "note": "on the one card measured, the driver reports more than the decimal reading of its stated "
                        "memory, so the decimal reading understates capacity; each row also shows the answer "
                        "if NVIDIA GB is read as GiB and at the reference driver's scale, and whether either "
                        "changes it",
            },
            "reference_driver_scale": {
                "vram_total_mib": min(totals), "stated_gb": ref_card["memory_gb_stated"],
                "bytes_per_stated_gb": round(driver_unit), "gib_bytes": GIB,
                "note": (f"the reference card's driver reports {min(totals):,} MiB for {ref_card['memory_gb_stated']} "
                         f"GB stated, {round(driver_unit):,} B per stated GB against {GIB:,} B for a GiB, so the "
                         f"GiB reading {'overstates' if driver_unit < GIB else 'does not overstate'} what the driver "
                         "exposes; applied to other cards as a sensitivity only, since no other card's driver was read"),
            },
        },
        "desktop_reserve": {
            "mib": reserve_mib, "bytes": reserve, "gb": gb(reserve), "source_entry": reserve_src,
            "rule": "the minimum vram_before_mib across fit_03.json entries: graphics memory already in use before "
                    "any model loads, with the desktop display driven by the same card",
            "observed_mib": before,
        },
        "generation_excess_check": {
            "by_model": excess_by_model,
            "definition": ("(peak graphics memory during generation - graphics memory in use before the load) x 2^20 B, "
                           "minus the part of the loaded footprint Ollama placed in graphics memory (size_vram_bytes; "
                           "on a fully resident load that is the whole loaded footprint). Computed for every entry "
                           "with a peak reading whose before reading was taken with no earlier model resident"),
            "use": ("not part of the sizing rule. Each row compares its margin only with the excess measured for "
                    "that same model; no model's excess stands in for another's, and where a model's own excess "
                    "was not measured margin_covers_generation_excess is null"),
            "verdicts": {
                "covered": "the decimal-reading margin holds this model's own excess",
                "marginal": ("the decimal-reading margin does not hold it, but the same card does if GB is read as "
                             "GiB or at the reference driver's scale"),
                "not covered": "no reading holds it on that card",
                "unknown": "this model's own excess was not measured",
            },
            "caveat": ("an excess measured while the model was spilled is the GPU-side compute buffer of a split "
                       "load; a fully resident load on a larger card may need a different amount, so a spilled "
                       "model's excess may not carry over to a fully resident load"),
        },
        "pending": {
            "rows": pending,
            "why": ("these rows' fit entries carry no per-layer cache inputs (gemma4:12b's entry predates the "
                    "per-layer arithmetic) or, for the No. 02 rows, no numeric parameter count"),
            "resolve": PENDING_HOW,
            "render": "a rendered table shows these cells as 'pending', never blank or zero",
        },
        "cards": [{**c, "checked": CHECKED} for c in CARDS],
        "cards_dropped": DROPPED,
        "cards_dropped_note": "every card in the list had its memory stated on its nvidia.com specification page"
                              if not DROPPED else "cards whose memory nvidia.com does not state",
        "models": rows,
        "no02_resident": no2_rows,
        "stretch": stretch,
        "assumptions": [
            ("NVIDIA GB is read as 10^9 bytes (see units); the GiB reading and the reference driver's scale are "
             "shown as sensitivities, never as the answer"),
            ("the sizing rule is loaded footprint plus desktop reserve; each row's own measured generation excess is "
             "checked against the margin and reported as a verdict, and with_own_generation_excess shows the answer "
             "with that excess added to the need"),
            (f"desktop reserve is {reserve_mib} MiB, the minimum measured on the reference machine with its display "
            "attached to the same card; a card that drives no display would need less, and it is applied to every card"),
            ("loaded footprint is Ollama's reported size at the settings above; another context length, cache type or "
            "parallel request count changes it"),
            "single card only; splitting a model across two cards is not considered",
            ("the card list is the one fixed for this study (GeForce RTX 50 series and RTX PRO Blackwell workstation "
            "line); the RTX 5060 Ti is its 16 GB variant; both RTX PRO 5000 variants are listed"),
            "no prices (plan Section 6 open question)",
            "measured overhead = loaded footprint - weights file - per-layer KV arithmetic",
            (f"gpt-oss:120b row (b): installed memory of {hw['ram_gb']} GB is read as GiB (the larger, conservative "
            "desktop use), measured available memory as 10^9 B (how fit_probe_03.py records it), the upgrade kit as "
            "10^9 B (conservative), and the runner's private memory at abort as GiB (conservative)"),
        ],
        "not_verified": [
            "whether NVIDIA's GB means 10^9 or 2^30 bytes: no spec page says",
            ("why measured overhead is negative for most models (Ollama's loaded footprint is smaller than the weights "
            "file plus the computed cache); the cause was not investigated"),
            *([(f"per-layer KV, computed footprint and measured overhead for {', '.join(pending)}: pending until "
                "/api/show is read (see pending)")] if pending else []),
            *([(f"whether the generation excess of {', '.join(spilled)} carries over to a fully resident load: each "
                "was measured while spilled")] if spilled else []),
            *([f"the generation excess of {', '.join(unmeasured)}: not measured (see each row's generation_excess)"]
              if unmeasured else []),
            ("gpt-oss:120b analytic rows: no card or memory upgrade was tested, and its generation compute buffer "
            "is unknown: it was never observed"),
            "whether each card suits a given chassis, power supply or cooling: not assessed",
        ],
    }
    for bad in (chr(0x2014), chr(0x2013)):
        if bad in json.dumps(out, ensure_ascii=False):
            raise SystemExit("dash character in output")
    write_json(R3 / "ops" / "cards_03.json", out)

    def short(cards: list[str]) -> str:
        return " / ".join(c.replace("NVIDIA ", "").replace("GeForce ", "") for c in cards) or "none"

    def cell(v: float | None, fmt: str = "{:.2f}") -> str:
        return "pending" if v is None else fmt.format(v)

    print(f"Desktop reserve {reserve_mib} MiB ({reserve_src}); NVIDIA GB read as 10^9 B; "
          f"resident % measured on {ref_label}; excess = this model's own generation excess")
    hdr = (f"{'model':<26}{'class':<11}{'params':>8}{'weights':>8}{'KV':>9}{'computed':>9}{'loaded':>8}{'ovh':>9}"
           f"{'res%':>6}{'need':>7}{'excess':>9}  card (tier): verdict")
    print(hdr)
    print("-" * len(hdr))
    notes = []
    for r in rows + no2_rows:
        sc, ex = r["smallest_card"], r["generation_excess"]["gb"]
        cls = "No.02" if r["class"] == NO2_BASELINE else r["class"]
        p = r["parameters"]
        print(f"{r['model'][:25]:<26}{cls:<11}{cell(None if p is None else p / 1e9, '{:.1f}B'):>8}{r['weights_file_gb']:>8.2f}"
              f"{cell(r['kv']['kv_gb_at_ctx']):>9}{cell(r['computed_footprint_gb']):>9}"
              f"{r['loaded_footprint_gb']:>8.2f}{cell(r['measured_overhead_gb']):>9}"
              f"{r['resident_fraction_reference_machine'] * 100:>6.1f}{r['need_gb']:>7.2f}"
              f"{(f'{ex:.2f}' if ex is not None else 'unknown'):>9}  "
              f"{short(sc['cards'])} ({sc['tier_gb_stated']} GB): {r['verdict']['status']}")
        if r["verdict"]["status"] != "covered":
            notes.append(f"{r['model']}: {r['verdict']['status']}: {r['verdict']['note']}")
        notes += [f"{r['model']}: {r[k]['note']}" for k in SENSITIVITY if r[k].get("note")]
        if r["generation_excess"].get("caveat") and r["verdict"]["status"] == "covered":
            notes.append(f"{r['model']}: excess {r['generation_excess']['caveat']}")
    for n in notes:
        print(f"  {n}")
    for s in stretch:
        a = s["analytic_not_measured"]["a_smallest_single_card"]
        b = s["analytic_not_measured"]["b_reference_machine_with_more_memory"]
        o = s["observed_at_load"]
        print(f"{s['model']:<26}stretch: did not load. weights {s['weights_file_gb']} GB; GPU buffer "
              f"{o['gpu_model_buffer_gb']} GB, CPU buffer {o['cpu_model_buffer_gb']} GB")
        print(f"{'':<26}(a) NOT MEASURED: need {a['need_gb']} GB -> {short(a['smallest_card']['cards'])} "
              f"({a['smallest_card']['tier_gb_stated']} GB); generation compute buffer "
              f"{a['generation_compute_buffer']}; margin_covers_generation_excess="
              f"{a['smallest_card']['margin_covers_generation_excess']}")
        print(f"{'':<26}(b) NOT MEASURED: {UPGRADE_RAM_GB} GB system memory leaves {b['left_over_gb']} GB after the "
              f"host buffer: room={b['room_for_cpu_buffer']}")
    print(f"wrote {R3 / 'ops' / 'cards_03.json'}")


if __name__ == "__main__":
    main()
