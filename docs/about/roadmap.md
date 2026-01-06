# Roadmap

This roadmap reflects the current direction of this fork. Items are grouped by timeframe and may change based on feedback and contributions.

## Recently completed

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

