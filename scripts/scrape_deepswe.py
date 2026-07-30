#!/usr/bin/env python3
"""Fetch DeepSWE public artifacts and write a compact model summary.

Usage:
  python3 scripts/scrape_deepswe.py
  python3 scripts/scrape_deepswe.py --out data/deepswe --source deep-swe

Outputs:
  data/deepswe/trials.json
  data/deepswe/tasks.json
  data/deepswe/release.json
  data/deepswe/model-summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.request
from collections import defaultdict
from pathlib import Path


BASE = "https://deepswe.datacurve.ai/artifacts/v1.1"


def fetch_json(name: str):
    with urllib.request.urlopen(f"{BASE}/{name}.json", timeout=60) as response:
        return json.load(response)


def mean(values):
    values = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.fmean(values) if values else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE, help="Artifact base URL.")
    parser.add_argument("--out", default="data/deepswe", help="Output directory.")
    parser.add_argument("--source", default="deep-swe", help="Trial source filter.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    global BASE
    BASE = args.base.rstrip("/")

    trials_payload = fetch_json("trials")
    tasks_payload = fetch_json("tasks")
    release_payload = fetch_json("release")
    trials = trials_payload["rows"] if isinstance(trials_payload, dict) else trials_payload

    (out / "trials.json").write_text(json.dumps(trials_payload, indent=2), encoding="utf-8")
    (out / "tasks.json").write_text(json.dumps(tasks_payload, indent=2), encoding="utf-8")
    (out / "release.json").write_text(json.dumps(release_payload, indent=2), encoding="utf-8")

    grouped = defaultdict(list)
    for row in trials:
        if row.get("source") != args.source:
            continue
        grouped[(row.get("model"), row.get("reasoning_effort"), row.get("provider"))].append(row)

    summary = []
    for (model, effort, provider), rows in sorted(grouped.items()):
        non_error = [r for r in rows if not r.get("errored")]
        denom = len(non_error)
        passed = sum(1 for r in non_error if r.get("passed"))
        summary.append(
            {
                "model": model,
                "reasoning_effort": effort,
                "provider": provider,
                "n_trials": len(rows),
                "n_non_error": denom,
                "pass_rate": passed / denom if denom else None,
                "avg_cost_usd": mean([r.get("cost_usd") for r in rows]),
                "avg_duration_seconds": mean([r.get("trial_duration_seconds") for r in rows]),
                "avg_agent_duration_seconds": mean([r.get("agent_duration_seconds") for r in rows]),
                "avg_input_tokens": mean([r.get("n_input_tokens") for r in rows]),
                "avg_output_tokens": mean([r.get("n_output_tokens") for r in rows]),
                "avg_peak_context_tokens": mean([r.get("peak_context_tokens") for r in rows]),
                "source": args.source,
                "source_artifacts": {
                    "trials": f"{BASE}/trials.json",
                    "tasks": f"{BASE}/tasks.json",
                    "release": f"{BASE}/release.json",
                },
            }
        )

    (out / "model-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(summary)} model rows to {out / 'model-summary.json'}")


if __name__ == "__main__":
    main()
