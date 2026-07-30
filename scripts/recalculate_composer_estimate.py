#!/usr/bin/env python3
"""Recalculate Composer estimate inputs from saved benchmark snapshots.

Usage:
  python3 scripts/recalculate_composer_estimate.py

This script reads:
  - data/benchmarks/artificial-analysis-composer-2.5.json
  - data/benchmarks/cursorbench-3.1.json
  - data/deepswe/model-summary.json
  - data/deepswe/trials.json

It writes:
  - data/benchmarks/composer-estimate.json

Refresh workflow:
  1. Open the Artificial Analysis Composer 2.5 article and update the values in
     data/benchmarks/artificial-analysis-composer-2.5.json.
  2. Open CursorBench and update the values in
     data/benchmarks/cursorbench-3.1.json.
  3. Refresh DeepSWE artifacts if needed with python3 scripts/scrape_deepswe.py.
  4. Run this script to regenerate data/benchmarks/composer-estimate.json.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AA_PATH = ROOT / "data/benchmarks/artificial-analysis-composer-2.5.json"
CURSORBENCH_PATH = ROOT / "data/benchmarks/cursorbench-3.1.json"
DEEPSWE_SUMMARY_PATH = ROOT / "data/deepswe/model-summary.json"
DEEPSWE_TRIALS_PATH = ROOT / "data/deepswe/trials.json"
OUT_PATH = ROOT / "data/benchmarks/composer-estimate.json"


def median(values):
    return statistics.median(sorted(values))


def mean(values):
    return statistics.fmean(values)


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def index_deepswe_rows(rows):
    indexed = {}
    for row in rows:
        indexed[(row["model"], row.get("reasoning_effort"))] = row
    return indexed


def deep_row(indexed, model, effort):
    row = indexed.get((model, effort))
    if row is None:
        raise KeyError(f"Missing DeepSWE mapping for {(model, effort)}")
    return row


def aa_implied_costs(aa_data, deep_index):
    composer_cost = aa_data["composer"]["standard_cost_usd"]
    implied = []
    for peer in aa_data["peer_rows"]:
        row = deep_row(deep_index, peer["deepswe_model"], peer.get("deepswe_reasoning_effort"))
        implied_cost = row["avg_cost_usd"] * (composer_cost / peer["cost_usd"])
        implied.append(
            {
                "benchmark": "Artificial Analysis",
                "model": peer["model"],
                "benchmark_cost_usd": peer["cost_usd"],
                "benchmark_score": peer["score"],
                "deepswe_cost_usd": row["avg_cost_usd"],
                "implied_deepswe_cost_usd": implied_cost,
            }
        )
    return implied


def cursorbench_implied_costs(cursorbench_data, deep_index):
    composer = cursorbench_data["composer"]
    max_gap = cursorbench_data["selection"]["max_score_gap_for_deepswe_mapping"]
    implied = []
    for row_data in cursorbench_data["rows"]:
        if not row_data.get("deepswe_model"):
            continue
        if abs(row_data["score"] - composer["score"]) > max_gap:
            continue
        row = deep_row(deep_index, row_data["deepswe_model"], row_data.get("deepswe_reasoning_effort"))
        implied_cost = row["avg_cost_usd"] * (composer["cost_usd"] / row_data["cost_usd"])
        implied.append(
            {
                "benchmark": "CursorBench",
                "model": row_data["model"],
                "benchmark_cost_usd": row_data["cost_usd"],
                "benchmark_score": row_data["score"],
                "deepswe_cost_usd": row["avg_cost_usd"],
                "implied_deepswe_cost_usd": implied_cost,
            }
        )
    return implied


def summarize_runtime_scenarios(trials_payload):
    rows = trials_payload["rows"] if isinstance(trials_payload, dict) else trials_payload
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row.get("source"), row.get("model"), row.get("reasoning_effort"), row.get("provider"))].append(row)

    shared_ratios = []
    shared_keys = {key[1:] for key in grouped if key[0] == "deep-swe"} & {key[1:] for key in grouped if key[0] == "swebenchpro"}
    for key in sorted(shared_keys):
        deep_rows = grouped[("deep-swe", *key)]
        sb_rows = grouped[("swebenchpro", *key)]
        deep_avg = mean([row.get("trial_duration_seconds", 0) for row in deep_rows])
        sb_avg = mean([row.get("trial_duration_seconds", 0) for row in sb_rows])
        if sb_avg:
            shared_ratios.append(deep_avg / sb_avg)

    sorted_ratios = sorted(shared_ratios)
    # DeepSWE v1.1 publishes only DeepSWE runs, so no cross-benchmark runtime
    # pairs remain. Keep the last measured ratios until a comparable source returns.
    if not sorted_ratios:
        return {
            "optimistic": 1.42862698123992,
            "base": 1.8513632105724407,
            "pessimistic": 3.782605983067886,
            "observed_ratios": [],
            "note": "Retained from the last DeepSWE/SWE-bench Pro overlap; DeepSWE v1.1 has no comparison rows.",
        }
    return {
        "optimistic": sorted_ratios[2],
        "base": median(sorted_ratios),
        "pessimistic": max(sorted_ratios),
        "observed_ratios": sorted_ratios,
    }


def main():
    aa_data = load_json(AA_PATH)
    cursorbench_data = load_json(CURSORBENCH_PATH)
    deepswe_rows = load_json(DEEPSWE_SUMMARY_PATH)
    trials_payload = load_json(DEEPSWE_TRIALS_PATH)
    deep_index = index_deepswe_rows(deepswe_rows)

    aa_costs = aa_implied_costs(aa_data, deep_index)
    cb_costs = cursorbench_implied_costs(cursorbench_data, deep_index)
    runtime = summarize_runtime_scenarios(trials_payload)

    aa_median = median([row["implied_deepswe_cost_usd"] for row in aa_costs])
    cb_median = median([row["implied_deepswe_cost_usd"] for row in cb_costs])
    cb_upper = max(row["implied_deepswe_cost_usd"] for row in cb_costs)

    standard_minutes = aa_data["composer"]["standard_minutes"]
    scenarios = {
        "optimistic": {
            "cost": round(aa_median, 3),
            "minutes": round(standard_minutes * runtime["optimistic"], 2),
            "timeMultiplier": round(runtime["optimistic"], 2),
            "costMethod": "AA near-peer median mapped onto DeepSWE peers",
        },
        "base": {
            "cost": round((aa_median + cb_median) / 2, 3),
            "minutes": round(standard_minutes * runtime["base"], 2),
            "timeMultiplier": round(runtime["base"], 2),
            "costMethod": "average of AA-implied and CursorBench-implied DeepSWE medians",
        },
        "pessimistic": {
            "cost": round(cb_upper, 3),
            "minutes": round(standard_minutes * runtime["pessimistic"], 2),
            "timeMultiplier": round(runtime["pessimistic"], 2),
            "costMethod": "CursorBench near-peer upper bound mapped onto DeepSWE peers",
        },
    }

    output = {
        "sourceLabel": "AA+CB->DeepSWE est.",
        "costNote": (
            "Artificial Analysis measured Composer 2.5 standard at $0.07 and 9.3 minutes per task, "
            "while CursorBench 3.2 reports Composer 2.5 at $0.44 per task. This report does not copy either "
            "dollar figure directly onto DeepSWE. Instead, it uses Composer-to-peer cost ratios within each "
            "benchmark and maps those ratios onto overlapping DeepSWE peers: optimistic uses the AA implied "
            f"median (~${scenarios['optimistic']['cost']:.2f}), base averages the AA and CursorBench implied medians "
            f"(~${scenarios['base']['cost']:.2f}), and pessimistic uses the CursorBench near-peer upper bound "
            f"(~${scenarios['pessimistic']['cost']:.2f}). Composer minutes remain estimated from DeepSWE-vs-SWE-bench Pro "
            "runtime ratios and are not observed DeepSWE v1.1 runs."
        ),
        "scenarios": scenarios,
        "methodology": {
            "summary": "Generated from benchmark source files and DeepSWE artifacts. Do not edit by hand; run scripts/recalculate_composer_estimate.py instead.",
            "aaMedianImpliedCost": round(aa_median, 3),
            "cursorbenchMedianImpliedCost": round(cb_median, 3),
            "cursorbenchUpperBoundImpliedCost": round(cb_upper, 3),
            "runtimeRatios": runtime,
            "aaAnchors": aa_costs,
            "cursorbenchAnchors": cb_costs,
        },
    }

    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
