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

The regex-only baseline now scores **precision = 1.0 and micro F1 ≈ 0.81** on the curated
dataset (the remaining recall gap is `PERSON`/`LOCATION`/`HEALTH`, which require an NER or
LLM engine and are intentionally out of regex scope). Earlier the harness surfaced several
regex gaps that have since been fixed and are guarded by the CI quality gate
(`--fail-under 0.80`) and `tests/test_eval.py`:

- **Grouped credit-card numbers** (`4111 1111 1111 1111`) are now matched: the pattern
  allows space/dash separators and is Luhn-validated, so false positives are filtered.
- **`REGEX_PHONE`** was tightened to require an international (`+`/`00`) or national (`0…`)
  prefix, so it no longer shadows the 4-digit groups of a spaced card or matches arbitrary
  multi-digit runs.
- **`REGEX_BIC`** is compiled case-sensitively (`(?-i:…)`) and is checksum-validated. Because
  uppercase dictionary words can still satisfy the weak BIC shape *and* a valid ISO country
  code (e.g. `DEUTSCHLAND` → `SC`), a **context gate** additionally requires a banking
  keyword (`BIC`, `SWIFT`, `IBAN`, …) near the match. Disable with
  `PiiMatchContainer(require_context_for_ambiguous=False)`.
- **`REGEX_IBAN` / `REGEX_TAX_ID`** now carry explicit checksum validators at the regex
  stage as well, not only via cross-engine validation.

Remaining and future work is tracked in `docs/about/roadmap.md`.

## Extraction-quality harness

Detection metrics assume the text was already extracted correctly.  A separate harness
measures **extraction recall** — whether the file processors actually pull the expected
text out of a document (a missed DOCX table cell or fused paragraph silently caps recall
before any engine runs):

```bash
pbd-toolkit eval-extraction eval/datasets/extraction/manifest.json
pbd-toolkit eval-extraction eval/datasets/extraction/manifest.json --fail-under 1.0 --format json
```

The manifest lists source files with `expected` (and optional `forbidden`) snippets;
extraction runs through the real `FileProcessorRegistry`.  Shipped fixtures are
plain-text formats so the gate is hermetic and CI-friendly.
