# Quality Improvement Plan

Status: proposal (2026-09-05). This document is the result of a multi-perspective
review of the code base (architecture, security & data protection, tests, docs /
packaging / governance) plus a measured baseline. It lists concrete findings with
file references and turns them into a phased plan with verifiable exit criteria.

Everything below was measured or read in the code; nothing is assumed.

## 1. Measured baseline

| Metric | Value | Source |
|---|---|---|
| Source LOC (excl. tests) | ~24k Python across `core/`, `file_processors/`, `api/`, `analytics/`, `validators/`, `eval/` | `wc -l` |
| Tests | 687 collected, 680 pass, **1 fail**, 6 skip (5× faiss, 1× hard-coded `skipif(True)`) | `pytest` with `.[dev,office,images,magic,llm,api]` |
| Suite runtime | ~13 s | same |
| Coverage | **73.0 %** measured, gate `fail_under = 65` | `pytest --cov` |
| Ruff (current rule set `E4,E7,E9,F,W,I,UP`) | clean, 141 files formatted | `ruff check` / `ruff format --check` |
| Ruff with extended rules (`B,S,C90,N,SIM,RET,PL,PTH,ARG,D`) | ~1 000 findings; largest: 204× E501, 136× import-outside-top-level, 33× B904, 30× C901 | `ruff check --select …` |
| mypy (current config) | clean | `mypy` |
| mypy `--disallow-untyped-defs` | 22 errors / 16 files | `mypy` |
| mypy `--strict` | 114 errors / 39 files | `mypy` |
| Bandit (medium+/medium+) | clean; 7× B608 suppressed via `# nosec` (verified false positives) | `bandit` |
| pip-audit | no known vulnerabilities | `pip-audit` |
| Cyclomatic complexity ≥ E (radon) | `cli.scan` **F(77)**, `FileScanner.scan` F(52), `PiiMatchContainer.__add_match` E(39), `TextProcessor.process_file` E(38), `run_doctor` E(37), `ScanRunner.run` E(33) | `radon cc` |
| Maintainability index | only `core/cli.py` rated C (6.8) | `radon mi` |
| Git tags / releases | **none** (222 commits, 130+ PRs) | `git tag` |

Modules with the weakest coverage: `core/scan_cache.py` 0 %, `core/globals.py` 0 %,
`core/scan_reporting.py` 29 %, `core/cli_setup.py` 35 %, `core/severity.py` 38 %,
`core/engines/vector_engine.py` 39 %, `core/profiles.py` 40 %,
`core/indexer/document_indexer.py` 42 %, `core/doctor.py` 52 %,
`file_processors/msg_processor.py` 25 %, `mbox_processor.py` 55 %, `zip_processor.py` 58 %.
`validators/*` have **no dedicated test file** at all. `scripts/*` (617 LOC, one of them a CI
gate) are not measured.

## 2. Findings

Severity: **P0** = wrong behaviour or legal/data-protection exposure today;
**P1** = real risk or structural debt that blocks other work; **P2** = hygiene.

### 2.1 Correctness bugs (P0)

1. **Scan profiles silently drop keys.** `ConfigLoader.merge_with_args`
   (`core/config_loader.py:173-218`) is an explicit allow-list of ~77 keys. It lacks
   `deduplicate`, `fail_on_severity`, `min_severity`, `min_confidence`, `text_chunk_size`,
   `text_chunk_overlap`, `context_chars`, `exclude`, `incremental`, `cache_path`,
   `redact*`, `pseudonymize*`, `analytics*`, `webhook_url`, `confidence_fusion`,
   `structured_validation`, `statistics_strict` and every `vector_*` key. Profiles are
   applied through the same function (`core/cli.py:537-542`). Verified empirically:
   `--profile ci` does **not** set `fail_on_severity=HIGH`, `--profile medical` does not set
   `min_severity=MEDIUM`, `--profile deep` does not set `text_chunk_size=2000`. Config files
   documented in `docs/getting-started/configuration.md` have the same silent no-op.
2. **`--profile` is never recorded.** `core/cli.py:778` reads `getattr(args, "profile")`, but
   `profile` is never put into the argparse shim (`core/cli.py:450-516`), so analytics always
   store `None`. `api/scanner_service.py:93-122` accepts `profile` and only stores it.
3. **`--format` has no validation.** `core/writers.py:628-650` falls back to CSV for unknown
   values; `--format bogus` silently produces CSV. The extension map is duplicated three
   times (`cli.py:625-633`, `cli_setup.py:489`, `writers.py`) with 6 / 3 / 8 formats.
4. **`export-config` writes API keys to disk.** `core/cli.py:1961-1972` serialises every
   `str` field of `EngineConfig`, including `openai_api_key` and the pydantic-ai keys.
5. **One test fails when the `api` extra is installed** (`tests/test_cli.py:417`): the auth
   guard now fires before the import error. CI only passes because it never installs `api`.
6. **`skipif(True)`** at `tests/test_engines.py:414` can never run.

### 2.2 Security and data protection

| Sev | Finding | Location |
|---|---|---|
| P0 | **License metadata is wrong.** `LICENSE` is EUPL v1.2; `pyproject.toml:12-16` declares MIT (text and classifier). Any wheel ships mislabelled. | `pyproject.toml`, `docs/about/license.md` |
| P0 | **Pseudonymizer is unsalted.** Seed is `md5(text)` (`core/pseudonymizer.py:117-122`). Pseudonyms are globally deterministic and confirmable by dictionary attack; that is not pseudonymisation in the GDPR sense. | `core/pseudonymizer.py` |
| P1 | **FAISS `.meta` stores raw chunk text** (`core/indexer/document_indexer.py:536`) in plaintext JSON with default permissions. The `query` command needs it for previews (`cli.py:1098`), so it is by design, but it is undocumented, unwarned and unprotected. | `core/indexer/document_indexer.py` |
| P1 | **ZIP bomb guard trusts attacker metadata.** Limits are computed from `ZipInfo.file_size`/`compress_size` (`file_processors/zip_processor.py:69-92`) and then `read()` is unbounded (`:106`). | `file_processors/zip_processor.py` |
| P1 | **API scan-path TOCTOU.** `_validate_scan_path` returns the resolved realpath but the caller discards it and scans the original string (`api/scanner_service.py:101-120`). | `api/scanner_service.py` |
| P1 | **Statistics "no file paths" mode leaks `scan_path`** (`core/scan_reporting.py:426` → `writers.py:394`). | `core/scan_reporting.py` |
| P1 | **MBOX has no per-message / message-count cap** (`file_processors/mbox_processor.py:34-56`), unlike EML. | `file_processors/mbox_processor.py` |
| P1 | **Error detail leakage in API**: raw exception text and `allowed_roots` absolute paths returned to clients (`api/routes/scans.py:51-53`, `scanner_service.py:83`). | `api/` |
| P1 | **CI has no `permissions:` block**; actions pinned to mutable major tags; `uv.lock` exists but CI installs unpinned via `pip install -e .`. | `.github/workflows/ci.yml` |
| P2 | `/docs`, `/openapi.json`, `/redoc` are unauthenticated; API key accepted as CLI argument (visible in `ps`); rate limiter keyed on socket IP without proxy-header support. | `api/middleware.py`, `api/server.py` |
| P2 | `install-hook` interpolates `--engines` / `--hook-type` unquoted into a generated shell script (`core/cli.py:1706-1724`). | `core/cli.py` |
| P2 | Unbounded recursion in XML element walk (`file_processors/xml_processor.py:84`). | `file_processors/xml_processor.py` |
| P2 | No `SECURITY.md`; Dependabot lacks a `docker` ecosystem; Docker base image and `vllm` image unpinned; `vllm` published on `0.0.0.0:8000`. | root, `.github/`, `Dockerfile`, `docker-compose.yml` |

Verified non-issues: XML parsing is defusedxml-only with no fallback; SQL in `analytics/` and
`sqlite_processor.py` is parameter-bound or allow-listed (the B608 hits are false
positives); API auth is fail-closed with `hmac.compare_digest`; CORS handling is correct;
API keys are never logged; `os.walk` does not follow symlinks and files are realpath-checked.

### 2.3 Architecture (P1)

- **`core/cli.py` is 2 013 lines; `scan()` alone is 870 lines with 103 Typer options**
  (`core/cli.py:75-945`) and mixes option parsing, env overrides, deprecations, path
  validation, output naming, logger setup, config construction, post-hoc config patching,
  analytics bootstrap, worker math, runner invocation, post-scan hooks and exit codes.
- **argparse `Namespace` shim inside a Typer CLI.** `cli.py:60-71,450-518` rebuilds a
  60-key Namespace so `Config.from_args` and `ConfigLoader` keep working; the API
  hand-builds a 30-field Namespace (`api/scanner_service.py:166-209`); even
  `core/scan_runner.py:410-415` constructs one. Every option is therefore defined in
  **four** places: Typer option, `_TYPER_DEFAULTS`, `config_mapping`, `Config` field
  (plus sub-config mirrors). Finding 2.1.1 is the direct consequence.
- **Layering violations.** `core/scan_reporting.py` and `core/scan_runner.py` import
  `typer` and use `typer.Exit` for control flow; `cli.py:1622-1645` re-serialises typed
  options into `argv` for a second argparse parse in `api/server.py` (and `--reload` is
  silently dropped there).
- **Dead code (~450 LOC):** `core/globals.py` (zero importers, docstring claims otherwise),
  `core/cli_setup.py:35-333` argparse mirror + `setup()`, `Config.load_extended_config`,
  the unreachable root-`config_types.json` branch in `core/doctor.py:420-448` ending in
  `except Exception: pass`.
- **Duplicated definitions:** `NerStats` twice (`core/config.py:45`, `core/statistics.py:8`);
  engine-flag lists in five places; path validation in three; outname sanitisation twice.
- **Two unrelated exception hierarchies.** `core/exceptions.py` defines six classes, only
  `OutputError` is used; `file_processors/base_processor.py:28` defines a parallel tree on
  plain `Exception`; `config.py:797-815` raises bare `RuntimeError` which `cli.py:666` then
  special-cases to detect NER failures.
- **`Config.logger` is `Logger | None`** but dereferenced unguarded at ~80 call sites;
  mypy `union-attr` is disabled for six modules to hide this (`pyproject.toml`, issue #94).
- **Silent engine disablement:** `core/engines/registry.py:70-83` swallows every
  construction failure and returns `None`; a bad API key yields a zero-finding scan.
- **Legacy LLM flags** (`--ollama`, `--openai-compatible`, `--multimodal`) are deprecated
  but fully wired through `Config`, `processor.py` and ~15 branches in
  `pydantic_ai_engine.py`; `--multimodal` emits no warning at all.
- **Import-time side effects:** `core/matches.py:72-90` parses `config_types.json` at
  import; 134 function-level imports work around cycles.

### 2.4 Packaging and release (P1)

- The distribution installs **`analytics`, `api`, `core`, `docs`, `eval`, `examples`,
  `file_processors`, `locales`, `output`, `scripts`, `validators`** flat into
  `site-packages` (`[tool.setuptools.packages.find]` only excludes `tests`). `core`, `api`,
  `eval` are collision-prone names; `docs`/`examples`/`output`/`scripts` must not be installed.
- Version is hard-coded in three places (`pyproject.toml`, `core/constants.py`,
  `api/models.py`/`api/app.py`), no tags, no CHANGELOG, no release or docs-deploy workflow.
- Three dependency sources of truth (`requirements*.txt`, extras, `uv.lock`) that already
  disagree: `requirements-dev.txt` has `gliner`/`spacy` but not `ruff`/`babel`; the `all`
  extra is a hand-copied union; `vector` lacks `faiss-cpu` although `query` needs it; no
  `docs` extra although `mkdocs.yml` needs a plugin the README does not mention.
- CI runs only Python 3.12 although `requires-python = ">=3.10"` and mypy targets 3.10.
  CI never installs `api`, `vector`, `gliner`, `spacy`, `ocr`, so `serve`, `query`, `--ner`
  paths are never executed in CI.

### 2.5 Tests (P1)

- Gate slack of 8 points (73 % vs 65 %) means regressions go unnoticed.
- `slow` / `integration` markers are declared and documented but used zero times; the
  documented `-m "not slow"` workflow is a no-op.
- Only 3 `parametrize` in 664 tests; no Hypothesis; validators (IBAN mod-97, Luhn, BIC,
  tax-ID) have no dedicated tests; ZIP bomb guards are 100 % unexercised;
  `core/scan_cache.py` is 0 %.
- `tests/conftest.py:63-129` uses `Mock(spec=Config)` with ~30 hand-wired attributes that
  drift from the real 856-line `Config`; `tests/test_integration.py` only pokes private
  regex compilation; 30+ tests assert only `is not None`.
- Real `time.sleep` and unmarked thread-interleaving tests; no `pytest-randomly`,
  `pytest-timeout`, `pytest-xdist`.
- `tests/perf/runner.py` is not collected, not in CI, and depends on an absent
  `Testdaten/` tree.
- **Eval harness is too small for its thresholds:** DE 30 docs / 38 annotations
  (HEALTH, BIC, TAX_ID have one instance each); EN 8 docs / 8 annotations gated at
  F1 ≥ 0.95, i.e. "zero misses". Only the regex engine is gated; no per-type minimum, no
  FP budget on negatives, no calibration. The extraction manifest covers 5 files, none of
  PDF/DOCX/ODT/ZIP/MSG/MBOX.

### 2.6 Documentation, UX, governance (P2)

- 8 of 11 CLI commands are undocumented in `docs/user-guide/cli.md` (`diff`, `report`,
  `install-hook`, `test-pattern`, `export-config`, `evaluate`, `eval-extraction`, `serve`);
  ~20 `scan` flags and all 7 profiles are undocumented; `docs/EXIT_CODES.md` lacks exit
  code 5; wrong defaults for `--openai-model` and `multimodal_model` in docs; JSONL missing
  from format lists; `EXIT_CODES.md`, `engines.md` and the statistics docs are not in the
  MkDocs nav although linked.
- `docs/developer/architecture.md` references pre-`core/` paths, claims `globals.py` is
  both unused and eliminated, and lists engines that no longer exist.
- Four brand spellings (`pbD Toolkit`, `pbD-Toolkit`, `PII Toolkit`, `pbd-toolkit`);
  `site_author: Fork Maintainer`; upstream link is GitLab in README and GitHub elsewhere.
- No engine selected exits with a list that omits `--vector-search` and never suggests
  `--profile quick`. No default engine.
- i18n extracts from exactly two files (`babel.cfg`); everything else is English-only.
- Missing: root `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue / PR
  templates, `.pre-commit-config.yaml`.

## 3. Plan

Phases are ordered by risk reduction per effort. Each phase has an exit criterion that is
checkable in CI or by a one-line command. Effort is a rough size for one person.

### Phase 0: stop the bleeding (S, ~1-2 days)

1. Fix the license metadata to EUPL-1.2 (`pyproject.toml` `license`, classifier,
   `docs/about/license.md`, README). Add the EUPL notice line to `README.md`.
2. Add the missing keys to `config_mapping` / `_TYPER_DEFAULTS` and add
   `tests/test_config_sync.py` asserting: every `scan` Typer option name ∈ `config_mapping`
   ∧ every profile key ∈ `config_mapping`. This test is the permanent guard for 2.1.1.
3. Put `profile` into the shim so it is recorded; make `ScanRequest.profile` validated
   against `_VALID_PROFILES` and actually applied in `api/scanner_service._run_scan`.
4. Redact `*_api_key` / `*_token` fields in `export-config`; add a test.
5. Fix `tests/test_cli.py:417` (assert on the auth guard, or monkeypatch the import) and
   add `api` to the CI install extras; remove `skipif(True)`.
6. Add `permissions: contents: read` to `ci.yml`; add a Python matrix `[3.10, 3.11, 3.12]`
   for the `test` job.
7. Raise `fail_under` to 72 (measured 73).
8. Document exit code 5 and fix the two wrong model defaults in the docs.

Exit: CI green on 3 Python versions with `api` installed; `pytest tests/test_config_sync.py`
passes; `pip install . && pip show pbd-toolkit` reports EUPL.

### Phase 1: security and data protection (M, ~1 week)

1. **Pseudonymizer**: seed with `HMAC-SHA256(salt, type || text)`; salt is generated per run
   (or read from `--pseudonymize-key-file` for stable cross-run mappings); never written to
   output. Document the change as breaking for anyone relying on cross-run stability.
2. **ZIP**: read entries through `read(limit + 1)` and enforce the cumulative limit on actual
   bytes; add tests for oversize entry, ratio, cumulative stop, nested archive, path traversal.
3. **API**: use the resolved path returned by `_validate_scan_path`; return generic
   400/500 bodies and log detail server-side; exempt only `/api/v1/health` from auth (docs
   behind auth or off in production); accept the key via `PBD_API_KEY` only and deprecate
   `--api-key`; optional trusted-proxy header for the rate limiter.
4. **FAISS meta**: write `.meta` with mode 0600, emit a one-line warning on save that the
   file contains raw text, document it in `cli.md`, and add `--vector-index-no-text` (or
   store only hashes/offsets and re-read the source file for previews in `query`).
5. Remove `scan_path` from the strict statistics output (or hash it).
6. MBOX per-message and message-count caps mirroring `eml_processor`; XML depth guard;
   `shlex.quote` in `install-hook`.
7. Supply chain: install in CI from `uv.lock` (`uv sync --frozen --extra …`); pin actions
   to commit SHAs (Dependabot keeps them fresh); add a `docker` Dependabot block; pin the
   Docker base image by digest; bind `vllm` to `127.0.0.1`.
8. Add `SECURITY.md` (disclosure address, supported versions) and link it from the
   existing security-analysis page.

Exit: new tests for each item; Bandit/pip-audit still clean; `pytest -k "zip or pseudonym"`
covers the new guards; `SECURITY.md` present.

### Phase 2: test suite as a real safety net (M, ~1-2 weeks, parallelisable with Phase 1)

1. `tests/test_validators.py` with Hypothesis: generate valid IBAN/Luhn/BIC/tax-IDs → accept;
   mutate one character → reject. Add `hypothesis` to the `dev` extra.
2. `tests/test_scan_cache.py`: hit/miss, mtime/size invalidation, corrupt file, concurrency.
3. Unit tests for `core/scan_reporting.py`, `core/severity.py`, `core/profiles.py`,
   `core/doctor.py` (beyond exit code 0), the XLSX/streaming writer paths, and the thin
   processors (`msg`, `mbox`, `odt`, `yaml`, `properties`, `vcf`, `ical`) including
   negative inputs (corrupt, empty, wrong extension).
4. Replace `Mock(spec=Config)` in `conftest.py` with a `make_config(**overrides)` factory
   producing a real `Config`; migrate `test_engines.py` and `test_config.py` off the mock.
5. Apply the `slow` / `integration` markers to the files that are actually slow or
   integration-level; add `pytest-randomly`, `pytest-timeout`, `pytest-xdist`; monkeypatch
   `time.sleep` in `test_statistics.py`.
6. Move `--cov` out of `addopts` into the CI command so local single-test runs are cheap;
   omit `.venv`, `htmlcov`, `site`, `output` explicitly; include `scripts/` in coverage.
7. Raise `fail_under` to 80 once 1-3 land; target 85 by the end of Phase 3.

Exit: `fail_under ≥ 80`; `pytest -m "not slow"` runs in < 10 s; `pytest -p randomly` stable
over 5 seeds; every module in `core/` and `file_processors/` ≥ 60 %.

### Phase 3: architecture (L, ~2-3 weeks, sequential steps)

Order matters: each step removes a dependency the next one would otherwise fight.

1. **Delete dead code**: `core/globals.py`, `cli_setup.__setup_args`/`setup()`,
   `Config.load_extended_config`, the unreachable doctor branch, duplicate `NerStats`.
   Update `docs/developer/architecture.md` in the same PR.
2. **Remove `typer` from `core/`**: `scan_reporting` raises `OutputError`, `scan_runner`
   returns an exit code; `cli.py` maps to `typer.Exit`. Restores the runner contract.
3. **Introduce one option schema.** A `ScanOptions` dataclass (or pydantic model) generated
   *once* and consumed by the Typer command (via `typer` parameters built from the schema
   or a thin adapter), `ConfigLoader`, profiles, `Config.from_args` and the API. Delete
   the argparse shim in `cli.py`, `scanner_service.py` and `scan_runner.py`. With the
   schema in place, the sync test from Phase 0 becomes structural rather than a guard.
4. **Split `scan()`** into `resolve_options → build_outputs → build_config → run → present`;
   move analytics bootstrap and worker math into `ScanRunner`. Target: no function in
   `core/` above radon C, `cli.py` under 800 lines.
5. **Single output-format enum** in `core/writers.py` driving the Typer choice, the
   extension map and the factory; delete the CSV fallback.
6. **Exception hierarchy**: `FileProcessingError(PiiToolkitError)`; `config.py` raises
   `ModelError`/`ConfigurationError`; remove unused classes; delete the `RuntimeError`
   special-case in `cli.py`. Engine registry logs construction failures at WARNING
   unconditionally and the CLI exits non-zero if a *requested* engine could not be built.
7. **`Config.logger` non-optional** (default `logging.getLogger("pbd_toolkit")`); remove the
   six `union-attr` overrides in `pyproject.toml`.
8. **Legacy LLM flags**: emit `DeprecationWarning` for `--multimodal` now; announce removal
   in the CHANGELOG for the next minor; then delete the `use_ollama` /
   `use_openai_compatible` / `use_multimodal` branches from `Config`, `processor.py` and
   `pydantic_ai_engine.py`.
9. Tighten ruff incrementally: enable `B`, `SIM`, `RET`, `C90` (max-complexity 15), `PTH`
   with per-file ignores that are burned down PR by PR; enable `E501` last. Enable mypy
   `disallow_untyped_defs` (22 errors today) and `disallow_incomplete_defs`.

Exit: `radon cc -n D` returns nothing in `core/`; `grep -r "argparse" core api` is empty;
`mypy --disallow-untyped-defs` clean; `pyproject.toml` has no `union-attr` override.

### Phase 4: packaging, release, docs (M, ~1 week, after Phase 3 step 3 to avoid double churn)

1. **Single package**: move everything under `pbd_toolkit/` (`pbd_toolkit.core`, `.api`,
   `.file_processors`, …), ship `locales/` and `config_types.json` as package data, fix
   `core/i18n.py`'s path resolution, entry point `pbd_toolkit.cli:cli`. Keep thin
   `core/…` shims for one release only if external users import them; otherwise a clean
   break with a CHANGELOG note.
2. **One version**: `importlib.metadata.version("pbd-toolkit")` everywhere; delete the
   constants; tag `v1.0.0` on `main` now and adopt SemVer.
3. **One dependency source**: extras in `pyproject.toml` are canonical; delete
   `requirements*.txt` or generate them (`uv export`); build `all` programmatically or via
   self-references (`pbd-toolkit[office,images,…]`); add `faiss-cpu` to `vector`; add a
   `docs` extra.
4. Workflows: `release.yml` (build sdist/wheel on tag, publish to PyPI via trusted
   publishing, attach to GitHub release), `docs.yml` (`mkdocs gh-deploy`), Docker image
   build on tag; `.pre-commit-config.yaml` mirroring ruff, ruff-format, mypy,
   `update_catalog.py check`.
5. Governance files: root `CONTRIBUTING.md` (link to docs), `CODE_OF_CONDUCT.md`,
   `.github/ISSUE_TEMPLATE/{bug,feature}.yml`, `pull_request_template.md`, `CHANGELOG.md`
   (Keep a Changelog format, backfilled from the last ~20 PRs).
6. Docs: document all 11 commands and every `scan` flag from the option schema (generate
   the reference table from the schema so it cannot drift); document profiles; add
   `EXIT_CODES.md`, `engines.md`, statistics docs to the nav; fix `architecture.md`; one
   brand name and one upstream link; make the "no engine" error mention `--vector-search`
   and `--profile quick`; consider defaulting to `--regex` when nothing is selected.
7. Widen i18n extraction to `core/doctor.py`, `core/scan_runner.py` and processors (or
   explicitly decide that only CLI-facing modules are translated and document that).

Exit: `pip install pbd-toolkit` from PyPI works with no top-level `core` package;
`mkdocs build --strict` passes in CI; docs site is deployed; `git tag` non-empty.

### Phase 5: detection quality and performance (L, ongoing)

1. Grow `eval/datasets/` to ≥ 150 DE and ≥ 100 EN annotations with ≥ 10 instances per
   gated type and a dedicated adversarial-negatives set; add per-type minimum F1 and a
   false-positive budget on negatives; only then raise `--fail-under`.
2. Gate GLiNER (and spaCy) in a separate CI job with a cached model download, with a
   baseline recorded in `eval/README.md`.
3. Add calibration output (reliability diagram / ECE) to `evaluate`, needed to make the
   Noisy-OR fusion weights defensible.
4. Extend the extraction manifest with PDF, DOCX, ODT, ZIP, MSG, MBOX fixtures (synthetic).
5. Perf smoke gate: make `tests/perf/runner.py` run one hermetic regex scenario against a
   committed synthetic corpus in CI and fail on > 30 % regression against a stored baseline.

Exit: per-type gates in CI; NER gate in CI; perf job in CI.

## 4. Suggested order and dependencies

```
Phase 0 ──► Phase 1 ──┐
        └─► Phase 2 ──┼──► Phase 3 (steps 1-9 sequential) ──► Phase 4 ──► Phase 5 (ongoing)
```

Phases 1 and 2 are independent and can run in parallel. Phase 4 step 1 (package
relayout) must come after Phase 3 step 3 (shim removal); doing the relayout first would
mean touching every import twice. Phase 5 can start any time but its gates only become
meaningful once Phase 2 makes the test suite trustworthy.

## 5. Targets

| Metric | Today | After Phase 2 | After Phase 4 |
|---|---|---|---|
| Coverage gate | 65 (measured 73) | 80 | 85 |
| Functions with radon ≥ D | 8 | 8 | 0 |
| `core/cli.py` LOC | 2 013 | 2 013 | < 800 |
| Option definitions per flag | 4 | 4 | 1 |
| mypy strictness | `check_untyped_defs` | same | `disallow_untyped_defs` + no overrides |
| Python versions in CI | 1 | 3 | 3 |
| Extras exercised in CI | 4 | 5 (+api) | all except `ocr` |
| Eval annotations DE / EN | 38 / 8 | 38 / 8 | ≥ 150 / ≥ 100 |
| Tags / CHANGELOG / SECURITY.md | none | none | present |

## 6. Things deliberately not proposed

- **Rewriting the engines or the processor pipeline.** Detection logic is where the value
  is and it is comparatively well tested; the debt is around it, not in it.
- **Switching build backend or CLI framework.** setuptools and Typer are fine; the
  problem is the argparse shim, not Typer.
- **Full `mypy --strict`** (114 errors). `disallow_untyped_defs` gets most of the value.
- **Enabling all ruff rules at once.** ~1 000 findings; do it rule-family by rule-family
  with per-file ignores so each PR stays reviewable.
