# Roadmap

This roadmap reflects the current direction of this fork. Items are grouped by timeframe and may change based on feedback and contributions.

## Recently completed

- Typer-based CLI with config file support (YAML/JSON) and structured summary output
- Unified LLM engine with PydanticAI for text detection
- **Real OpenAI-compatible multimodal image detection** (OpenAI / vLLM / LocalAI via `POST /chat/completions`)
- Privacy-focused statistics output (aggregated, no individual PII instances)
- Expanded file format coverage and improved robustness/security hardening

## Next (short-term)

- **Documentation consolidation**
  - Align detection docs to reflect the current multimodal pipeline and limitations
  - Remove remaining legacy references and keep examples consistent (`python` vs `python3`, install paths)
- **CI / quality gates**
  - Add GitHub Actions for tests + basic security checks (Bandit) + lint (if adopted)
- **Packaging polish**
  - Make optional extras explicit in docs (e.g. `.[office]`, `.[magic]`, `.[llm]`)
  - Ensure MkDocs metadata and repository links are correct everywhere

## Later (mid-term)

- **Better multimodal UX**
  - Support OpenAI “Responses API” where available (while keeping `chat/completions` compatibility)
  - Improve JSON robustness (function-calling / JSON schema constraints where supported by provider)
- **Performance**
  - Parallel scanning/processing with safe per-engine throttling and resource limits
- **Governance**
  - Issue templates, contribution automation, release notes and versioning strategy

## How to help

If you want to contribute, pick an item from **Next** and open a PR with:
- what changed
- how it was tested
- any documentation updates

