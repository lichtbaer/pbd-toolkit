# Roadmap

This roadmap reflects the current direction of this fork. Items are grouped by timeframe and may change based on feedback and contributions.

## Recently completed

- **Detection quality: cross-engine corroboration & validation**:
  - **Canonical entity-type taxonomy** (`core/entity_types.py`): every engine's raw label
    (`REGEX_*`, `NER_*`, `VECTOR_*`, `OLLAMA_*`) maps to a shared canonical type so that
    deduplication and confidence fusion actually group the *same* real-world PII found by
    different engines (e.g. `REGEX_CREDIT_CARD` + `VECTOR_CREDITCARD`). Toggle with
    `--no-` paths on dedup/fusion; raw labels are preserved in output.
  - **Cross-engine checksum validation** (`--structured-validation`, default on): IBAN,
    credit-card, tax-ID and BIC findings from *any* engine (LLM, vector, NER) are
    checksum-validated and dropped if invalid — previously only the regex engine did this.
    A length guard avoids penalising coarse chunk-level findings.
- **Detection-quality evaluation harness** (`pbd-toolkit evaluate`, `eval/`):
  - Precision / recall / F1 per canonical entity type, plus micro/macro averages, measured
    through the real detection pipeline against an annotated, fully synthetic ground-truth
    dataset (`eval/datasets/synthetic_de.json`).
  - `--engines` to compare engine combinations, `--format json`, and `--fail-under` for use
    as a CI quality gate. A hermetic regex-only regression test guards the structured types.
- **Vector Search Extensions**:
  - **Post-scan `query` CLI** (`pii-toolkit query <index> <text>`): interactive FAISS index queries after a scan, with `--top-k`, `--threshold`, and `--format json` support
  - **Custom exemplars** (`--vector-custom-exemplars`): extend or override built-in PII categories with domain-specific YAML/JSON exemplar files
  - **File hash tracking**: SHA-256 hashes stored per chunk in the FAISS `.meta` file; foundation for future incremental index updates
  - **FAISS query bug fix**: disk-loaded FAISS indices now correctly use FAISS for similarity search instead of falling back to a broken brute-force path
- **Vector-based PII detection engine** (`--vector-search`):
  - Semantic similarity via sentence-transformers (fully local, no API)
  - 13 PII categories, 90 bilingual (DE/EN) exemplar texts
  - Triage mode (`--vector-triage`): pre-filter for LLM engines to reduce API costs
  - Optional FAISS index persistence for cross-document analysis
  - `pip install "pii-toolkit[vector]"`
- Typer-based CLI with config file support (YAML/JSON) and structured summary output
- Unified LLM engine with PydanticAI for text detection
- **Real OpenAI-compatible multimodal image detection** (OpenAI / vLLM / LocalAI via `POST /chat/completions`)
- Local-first multimodal UX improvements (vLLM/LocalAI for images; supports combined runs with Ollama for text)
- Privacy-focused statistics output (aggregated, no individual PII instances)
- Documentation updated to match the current Typer CLI (`scan <path>`) and current output schemas
- Expanded file format coverage and improved robustness/security hardening
- GitHub Actions CI (tests + lint + security checks, blocking)
- `--version` / `-V` CLI support
- Packaging/docs consistency: Python 3.10+ baseline (code/packaging/docs aligned)
- Performance hardening:
  - Bounded pending futures during scanning (avoid unbounded memory growth on large trees)
  - Per-engine concurrency limits (avoid overwhelming local LLM servers)
  - Image detection uses the same engine synchronization as text detection

## Next (short-term)

- **Documentation consistency**
  - Keep CLI docs aligned with implemented flags (incl. `--pydantic-ai`, `doctor`, `--format jsonl`)
  - Keep installation guidance consistent with packaging/extras
  - Ensure MkDocs navigation links to all relevant guides (e.g. open-source multimodal models)
- **Packaging polish**
  - Make optional extras explicit and discoverable (feature → extra mapping)
- **Deprecation story**
  - Clearly mark legacy LLM flags and guide users to `--pydantic-ai`
  - Add a sunset timeline and/or warnings for legacy LLM flags

## Later (mid-term)

- **Regex pattern quality** (surfaced by the evaluation harness):
  - ✅ `REGEX_CREDIT_CARD` now matches space/dash-separated card numbers (Luhn-validated),
    and `REGEX_PHONE` was constrained to international/national prefixes so it no longer
    shadows spaced-card digit groups or matches arbitrary digit runs.
  - ✅ `REGEX_BIC` is compiled case-sensitively and checksum-validated; a context gate
    (`require_context_for_ambiguous`) drops BIC-shaped dictionary words that lack a nearby
    banking keyword. `REGEX_IBAN`/`REGEX_TAX_ID` also validate at the regex stage.
  - ✅ A hermetic per-run quality gate (`evaluate --fail-under 0.80`) guards regex F1 in CI.
  - Grow `eval/datasets/` with more languages/domains and add per-engine accuracy gates.
- **Extraction quality**:
  - ✅ DOCX now extracts tables and section headers/footers, and joins paragraphs with
    newlines so entities no longer fuse across paragraph boundaries.
  - ✅ XLSX/XLS/CSV preserve column-header context (`Header: value`, one record per line).
  - ✅ Email attachments are recursively extracted by routing each attachment through the
    file-processor registry (size/count/depth limited).
  - ✅ PDF text is accumulated per page (short standalone values are no longer dropped),
    with an optional OCR fallback for scanned pages (`pip install ".[ocr]"`, auto-enabled
    when installed).
  - ✅ A hermetic extraction-recall gate (`eval-extraction --fail-under`) guards this in CI.
  - Remaining: OCR for standalone image files; recursive extraction of non-text files
    nested inside ZIP archives (currently decoded as text only).
- **Detection quality (engines)**:
  - ✅ Confidence fusion uses weighted Noisy-OR (calibratable per-engine weights) instead
    of a flat corroboration bonus.
  - ✅ GLiNER supports per-label confidence thresholds (`ner_label_thresholds`).
  - ✅ Engine offsets are translated to document-global positions across chunk boundaries
    (correct context windows / gating / redaction).
  - Remaining: span-localised vector findings (return the matching sentence, not the whole
    chunk); confidence-calibration report (reliability/ECE) in the eval harness.
- **Performance**:
  - spaCy `nlp.pipe` batching, incremental scanning/caching, and async I/O.
- **Better multimodal UX**
  - Support OpenAI “Responses API” where available (while keeping `chat/completions` compatibility)
  - Improve JSON robustness (function-calling / JSON schema constraints where supported by provider)
- **Performance**
  - More granular resource limits (timeouts/bytes/chunking) and batching where applicable (e.g. spaCy `nlp.pipe`)
- **Governance**
  - Issue templates, contribution automation, release notes and versioning strategy

## How to help

If you want to contribute, pick an item from **Next** and open a PR with:
- what changed
- how it was tested
- any documentation updates

