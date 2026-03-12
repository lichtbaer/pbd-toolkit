# Docker / Compose

The PII Toolkit is a CLI tool, so the recommended workflow is to run it as a one-off
container job and mount your input/output directories.

## Directory layout

The default compose file expects these local folders:

- `./data` (read-only input)
- `./output` (results)
- `./config` (optional config files)
- `./.cache/huggingface` (model cache)

## Build variants

The `Dockerfile` accepts a `PIP_EXTRAS` build arg to enable optional features:

- Minimal: no extras (regex + basic text/pdf/html)
- Features: `office,images,magic,llm`
- NER: `gliner,spacy`
- Full: `office,images,magic,llm,gliner,spacy`

## Compose profiles

Use profiles to pick the variant:

```bash
# Minimal
docker compose --profile min run --rm toolkit-min scan /data --regex

# Features (office/images/magic/llm)
docker compose --profile features run --rm toolkit-features scan /data --regex --ner

# NER engines (GLiNER + spaCy)
docker compose --profile ner run --rm toolkit-ner scan /data --ner

# Full feature set
docker compose --profile full run --rm toolkit-full scan /data --regex --ner
```

## vLLM (optional second container)

Start a local OpenAI-compatible server with vLLM:

```bash
docker compose --profile vllm up -d vllm
```

Then use it for multimodal image detection:

```bash
docker compose --profile full run --rm toolkit-full scan /data/images \
  --multimodal \
  --multimodal-api-base http://vllm:8000/v1 \
  --multimodal-model microsoft/llava-1.6-vicuna-7b \
  --output-dir /output
```

## Notes

- For GPU support, ensure the NVIDIA container runtime is installed.
- `libmagic` is installed in the image to enable `--use-magic-detection`.
