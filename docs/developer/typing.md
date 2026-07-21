# Type Checking

The codebase uses type hints extensively and ships them to downstream users via
[`py.typed`](https://peps.python.org/pep-0561/) markers in every distributed package
(`core`, `api`, `analytics`, `file_processors`, `validators`, `eval`). CI runs
`mypy` on every pull request (the `typecheck` job) so type regressions are caught
before merge.

## Policy: pragmatic baseline, tighten incrementally

The [`[tool.mypy]`](../../pyproject.toml) configuration is intentionally
**non-strict**: `disallow_untyped_defs` is off, and `ignore_missing_imports` is on
so the many optional heavy dependencies (`gliner`, `spacy`, `faiss`, `pydantic_ai`,
`sentence_transformers`, `pytesseract`, …) don't need to be installed for the
type-check job to run. `check_untyped_defs`, `warn_redundant_casts`, and
`warn_unused_ignores` are on, so mypy still checks the bodies of functions that
lack full annotations and flags stale `# type: ignore` comments.

The intent is to catch real bugs — wrong argument names, undefined attributes,
inconsistent optionality — without requiring 100% annotation coverage up front.
Tighten a module (e.g. add `disallow_untyped_defs` via a
`[[tool.mypy.overrides]]` block scoped to that module) once its types are solid.

## Handling `# type: ignore`

- Always include an error code, e.g. `# type: ignore[union-attr]`, and a short
  comment explaining *why* the ignore is safe — not just that it's needed. A
  bare `# type: ignore` is flagged by `warn_unused_ignores` once the specific
  error it silenced is gone, which is a useful trip-wire against stale ignores
  drifting from the code they were written for.
- Prefer a real fix (narrowing the type, adding an `assert`, fixing a stale
  attribute reference) over an ignore when the fix is small. Several ignores in
  this codebase were replaced with actual bug fixes during the initial mypy
  rollout (a wrong class name, a nonexistent attribute, a mismatched keyword
  argument) — mypy is good at finding these.
- Some patterns are intentionally duck-typed and not worth threading through
  the type system, notably `FileProcessorRegistry.can_process`, which inspects
  each processor's actual signature via `inspect.signature` and calls it with
  only the parameters it declares (see `file_processors/base_processor.py`).
  Subclasses that implement a narrower signature carry
  `# type: ignore[override]` for this reason.

## Known follow-up: `Config.logger` optionality

`Config.logger` (and the loggers threaded through the detection engines) are
typed `logging.Logger | None`, but `core/config.py`, `core/scanner.py`,
`core/processor.py`, and the `pydantic_ai_engine` / `vector_engine` /
`spacy_engine` modules call `self.config.logger.*` unconditionally at roughly
80 call sites, relying on the CLI and API always constructing a real logger.
Narrowing every call site (or resolving a guaranteed non-`None` logger once and
threading it through) is real follow-up work, not a one-line fix, so these
modules currently carry a `[[tool.mypy.overrides]]` entry that disables
`union-attr` checking. Removing that override — by fixing the call sites — is
the next tightening pass for this configuration.

## Verifying `py.typed` ships in the wheel

```bash
python -m build --wheel
python -c "
import zipfile
z = zipfile.ZipFile('dist/pbd_toolkit-*.whl')
print([n for n in z.namelist() if n.endswith('py.typed')])
"
```
