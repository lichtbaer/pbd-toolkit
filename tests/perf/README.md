# Performance E2E Runner

This directory provides an end-to-end performance runner for the CLI using
the `Testdaten/synthetic_data_collection` dataset. It produces JSON reports
per scenario and an aggregate summary.

## Quick Start

List scenarios:

```
python tests/perf/runner.py --list
```

Run a single scenario:

```
python tests/perf/runner.py --scenario regex_smoke
```

Run all scenarios:

```
python tests/perf/runner.py --all
```

Reports are written to `tests/perf/reports/` (ignored by git).

## Scenario Configuration

Scenarios live in `tests/perf/scenarios.json`:

- `name`: Scenario identifier.
- `path`: Dataset path to scan.
- `args`: CLI flags for `main.py` (e.g. `["--regex"]`).
- `stop_count`: Optional limit to keep runs short.
- `runs`: Number of repeated runs for the same scenario.
- `exclude_extensions`: Optional list of file extensions to skip.

The runner ensures `--summary-format json` and writes output files to
`tests/perf/reports/output` by default.

## Notes

- The dataset path already excludes `Testdaten/Review` and `Testdaten/_meta`.
- NER scenarios require the relevant models to be installed locally.
- For reproducible results, keep hardware and environment stable.
