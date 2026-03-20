# Security and Privacy Analysis

This document summarizes the security and privacy posture of the PII Toolkit (fork) at a high level. It is not a substitute for a formal security review.

## Threat model (short)

- **Inputs are untrusted**: the toolkit scans arbitrary files and directories; file contents may be malformed or malicious.
- **Outputs may contain sensitive data**: findings include detected PII unless you use privacy-focused statistics mode.
- **Optional network use**: only enabled when you explicitly use cloud or networked model providers (OpenAI-compatible APIs).

## Privacy principles implemented

- **No telemetry by default**: the project does not intentionally collect or transmit usage telemetry.
- **Telemetry disabled in common ML deps**:
  - Sets `HF_HUB_DISABLE_TELEMETRY=1`
  - Sets `TORCH_DISABLE_TELEMETRY=1`
- **User-initiated network calls only**:
  - Regex / GLiNER / spaCy runs locally.
  - Multimodal detection sends images to an API endpoint only when `--multimodal` (or equivalent config) is enabled.
- **Privacy-focused statistics mode**:
  - `--statistics-mode` writes aggregated statistics without storing individual PII instances.

## Security controls (selected)

- **Secure XML parsing**: uses `defusedxml` to reduce XXE and related XML parser risks.
- **Path validation**: base-path checks are used to mitigate path traversal when processing scanned files.
- **Robust error handling**: extraction and detection failures are collected and reported without crashing the full scan.

## Multimodal detection (OpenAI-compatible)

When enabled, the toolkit sends image content to the configured `--multimodal-api-base` (or `--openai-api-base`) endpoint using the OpenAI-compatible `POST /chat/completions` schema with an `image_url` data URL payload.

### Privacy implications

- **Images may contain PII**; sending them to a third-party API is a data disclosure risk.
- Prefer **local OpenAI-compatible endpoints** (e.g. vLLM, LocalAI) for sensitive datasets.
- Restrict endpoint exposure to localhost or a secured network segment.

### Operational safeguards

- Use dedicated API keys with least privilege.
- Keep output directories protected; findings files are sensitive.
- Consider running scans in isolated environments and limiting logs in production.

## Known limitations / TODOs

- This is a best-effort analysis; the project should add:
  - CI security scanning (e.g. Bandit, dependency audit) and a documented disclosure process.
  - Clear data retention guidance for output artifacts.

