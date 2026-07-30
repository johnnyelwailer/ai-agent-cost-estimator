# AI Agent Cost Estimator

Static HTML report for estimating monthly AI coding-agent cost by model.

## Local development

Run a local static server from the repository root:

```sh
./scripts/dev.sh
```

Then open `http://127.0.0.1:4173/` in your browser.

Optional: pass a custom port.

```sh
./scripts/dev.sh 8080
```

## Files

- `index.html` - publishable report
- `scripts/scrape_deepswe.py` - refresh DeepSWE source data
- `scripts/recalculate_composer_estimate.py` - regenerate Composer estimate from saved AA / CursorBench snapshots plus DeepSWE data
- `data/deepswe/model-summary.json` - compact generated DeepSWE summary
- `data/deepswe/release.json` - artifact URL patterns for trial-level logs, patches, and verifier output
- `data/benchmarks/artificial-analysis-composer-2.5.json` - manual snapshot of the AA Composer 2.5 article values used by the report
- `data/benchmarks/cursorbench-3.1.json` - manual snapshot of CursorBench rows used by the report
- `data/benchmarks/composer-estimate.json` - generated Composer estimate consumed by the report

## Refresh DeepSWE data

```sh
python3 scripts/scrape_deepswe.py
```

Large raw artifacts (`trials.json`, `tasks.json`) are ignored by git. Commit `model-summary.json` and `release.json` when source data changes.

## Refresh Composer benchmark data

There is no public machine-readable feed for the Composer 2.5 article or CursorBench, so these are refreshed manually.

1. Open the Artificial Analysis Composer 2.5 article and update `data/benchmarks/artificial-analysis-composer-2.5.json`.
2. Open CursorBench and update `data/benchmarks/cursorbench-3.1.json`.
3. Refresh DeepSWE artifacts if needed:

```sh
python3 scripts/scrape_deepswe.py
```

4. Recalculate the Composer estimate consumed by the report:

```sh
python3 scripts/recalculate_composer_estimate.py
```

5. Review and commit the updated benchmark source snapshots and generated output.
