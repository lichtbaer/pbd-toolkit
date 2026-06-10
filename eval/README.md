# Detection-quality evaluation harness

This package measures **precision / recall / F1** of the detection engines against an
annotated ground-truth dataset, grouped by *canonical* entity type
(`core.entity_types`). It turns "good precision/recall balance" from a code comment into
a number you can track and gate on.

## Quick start

```bash
# Regex only (offline, deterministic, no model downloads)
pbd-toolkit evaluate eval/datasets/synthetic_de.json

# JSON output for tooling / dashboards
pbd-toolkit evaluate eval/datasets/synthetic_de.json --format json

# Evaluate a combination of engines (requires the relevant extras installed)
pbd-toolkit evaluate eval/datasets/synthetic_de.json --engines regex,gliner,vector-search

# Use as a CI quality gate (non-zero exit if micro F1 drops below the threshold)
pbd-toolkit evaluate eval/datasets/synthetic_de.json --engines regex --fail-under 0.30
```

Predictions are produced through the **real** detection pipeline
(`PiiMatchContainer`), including canonical-type normalisation and cross-engine checksum
validation, so the numbers reflect what the tool would actually report.

## Dataset format

A dataset is a JSON list of documents. All PII **must be synthetic**.

```json
[
  {
    "id": "doc-001",
    "text": "Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
    "annotations": [
      {"type": "PERSON", "start": 0,  "end": 14, "text": "Max Mustermann"},
      {"type": "IBAN",   "start": 21, "end": 48, "text": "DE89 3704 0044 0532 0130 00"}
    ]
  }
]
```

- `type` should be a canonical type (see `core/entity_types.py`); raw engine labels are
  also accepted and normalised on load.
- `start` / `end` are optional but recommended — when present they are validated against
  `text` on load, so a drifting offset fails fast.

## Matching model

A prediction is a true positive for a gold annotation when their **canonical** types are
equal *and* their spans overlap. When offsets are missing (e.g. some vector findings
report whole chunks), a case-insensitive text-containment fallback is used. Matching is
greedy and one-to-one.

Reported figures: per-type precision/recall/F1, plus `micro` (pooled) and `macro_f1`
(unweighted mean over gold types).

## Findings surfaced by the bundled `synthetic_de.json`

The regex-only baseline scores **F1 = 1.0 for IBAN, EMAIL and IP_ADDRESS** but reveals
several genuine engine gaps that the harness now makes visible and trackable:

- **Grouped credit-card numbers are missed.** `REGEX_CREDIT_CARD` only matches digits
  with no separators, and the very broad `REGEX_PHONE` pattern shadows the 4-digit
  groups of a spaced card (`4111 1111 1111 1111`).
- **`REGEX_PHONE` is over-broad** (`\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b`), matching
  almost any multi-digit run and inflating false positives.
- **`REGEX_BIC` is compiled case-insensitively** and matches ordinary German words. The
  new cross-engine checksum validation (`--structured-validation`, on by default) now
  filters roughly half of these — a measurable precision win — but a tighter pattern
  would be better.

These are tracked in `docs/about/roadmap.md`.
