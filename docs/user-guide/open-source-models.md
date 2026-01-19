# Open-Source Models for Multimodal Detection

The PII Toolkit supports open-source multimodal models that can be run on your own infrastructure, providing complete privacy and control over your data.

## Overview

Instead of using commercial APIs like OpenAI, you can run multimodal models locally using:
- **vLLM**: High-performance inference server for LLMs
- **LocalAI**: OpenAI-compatible API server for local models

Both solutions provide OpenAI-compatible APIs, so they work seamlessly with the PII Toolkit's multimodal detection engine.
The toolkit sends images using the OpenAI-compatible `POST /chat/completions` schema with an `image_url` data URL payload, so your endpoint must support vision-capable chat completions.

## Why Use Open-Source Models?

**Privacy**: Your images never leave your infrastructure
**Cost**: No per-request API costs
**Control**: Full control over models and configuration
**Compliance**: Easier to meet data protection requirements
**Offline**: Works without internet connection

## vLLM Setup

vLLM is a high-performance inference server optimized for large language models.

### Installation

```bash
# Install vLLM
pip install vllm

# Or with CUDA support (recommended for GPU)
pip install vllm[all]
```

### Starting the Server

```bash
# Start vLLM server with a multimodal model
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.6-vicuna-7b \
    --port 8000 \
    --host 0.0.0.0
```

**Recommended Models**:
- `Qwen2.5-VL-7B-Instruct` - Strong 7B vision model, multilingual (incl. German), good speed on RTX 4090
- `Phi-3.5-Vision-Instruct` - Compact 4B model, excellent visual reasoning, fits in <8GB VRAM when quantized
- `LLaVA-OneVision-Qwen2-0.5B` - Tiny 0.5B model, surprisingly capable for documents/videos, good for real-time
- `VILA-1.5` (7B variants) - NVIDIA-optimized, multi-image/video, works well with 4-bit on RTX 4090
- `Gemma-3-Vision` (4B/9B) - Strong multimodal family; larger variants benefit from quantization
- `microsoft/llava-1.6-vicuna-7b` - Solid baseline for compatibility

### Using with PII Toolkit

```bash
python main.py scan /data/images \
    --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model microsoft/llava-1.6-vicuna-7b
```

### Configuration Options

vLLM supports many configuration options:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.6-vicuna-7b \
    --port 8000 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 4096
```

**Important Parameters**:
- `--tensor-parallel-size`: Number of GPUs to use (for multi-GPU)
- `--gpu-memory-utilization`: GPU memory usage (0.0-1.0)
- `--max-model-len`: Maximum sequence length

### System Requirements

**Minimum**:
- 16GB RAM
- 8GB VRAM (GPU)
- CUDA 11.8+ (for GPU)

**Recommended**:
- 32GB+ RAM
- 16GB+ VRAM (GPU)
- Modern GPU (RTX 3090, A100, etc.)

## LocalAI Setup

LocalAI is a drop-in replacement for OpenAI API that runs locally.

### Installation (Docker)

```bash
# Pull LocalAI image
docker pull localai/localai:latest-aio-cuda

# Run LocalAI
docker run -p 8080:8080 \
    -v $PWD/models:/models \
    localai/localai:latest-aio-cuda
```

### Installation (From Source)

```bash
# Clone repository
git clone https://github.com/mudler/LocalAI.git
cd LocalAI

# Build (requires Go)
make build
```

### Model Setup

1. Download a multimodal model (e.g., LLaVA)
2. Place it in the models directory
3. Create a model configuration file

**Example model configuration** (`models/llava.yaml`):

```yaml
name: llava
backend: llama
parameters:
  model: llava-model.gguf
  f16: true
context_size: 4096
```

### Using with PII Toolkit

```bash
python main.py scan /data/images \
    --multimodal \
    --multimodal-api-base http://localhost:8080/v1 \
    --multimodal-model llava
```

## Model Recommendations (Current)

### High-Quality, General Purpose

- **Qwen2.5-VL-7B-Instruct**: Strong 7B model for images and videos, multilingual, fast on modern GPUs
- **VILA-1.5 (7B)**: Optimized for multi-image and video; good balance of quality and throughput
- **Gemma-3-Vision (9B)**: Higher-quality option when you can afford more VRAM

### Compact / Low VRAM

- **Phi-3.5-Vision-Instruct (4B)**: Excellent reasoning in a small footprint; fits <8GB VRAM quantized
- **Gemma-3-Vision (4B)**: Efficient for mid-tier GPUs

### Ultra-Light / Real-Time

- **LLaVA-OneVision-Qwen2-0.5B**: Very small but strong for documents and short videos

### Legacy / Compatibility

- **LLaVA 1.6 (7B/13B)**: Stable baseline for OpenAI-compatible endpoints
  - Use when you need a well-tested model that is widely supported

**Note**: Exact repository names and supported formats vary by provider (vLLM, LocalAI, Ollama). Always check the model card and required tokenizer/vision configs.

## Performance Optimization

### GPU Acceleration

Always use GPU if available:
```bash
# vLLM automatically uses GPU
# LocalAI: Use CUDA-enabled image
docker run --gpus all localai/localai:latest-aio-cuda
```

### Model Quantization

Use quantized models to reduce memory:
- 4-bit quantization: ~4x memory reduction
- 8-bit quantization: ~2x memory reduction
 - Prefer AWQ or GGUF formats for efficient local inference where supported

### Hardware Fit (RTX 4090 and Similar)

- RTX 4090 comfortably runs up to ~30B parameters with Q4/Q5 quantization and full GPU offload for ~8k context
- Larger models (e.g., Qwen2.5-VL-72B) require aggressive quantization or multi-GPU and are slower (~20 tokens/s)
- If latency matters, favor 7B and smaller models with high-quality quantization

### Batch Processing

Process multiple images in parallel (if your model supports it):
- Increase `--multimodal-timeout` for batch processing
- Use multiple workers if processing many images

## Troubleshooting

### Out of Memory Errors

**Solution**: Use a smaller model or enable quantization:
```bash
# vLLM with lower memory usage
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.5-7b \
    --gpu-memory-utilization 0.7
```

### Slow Processing

**Solutions**:
- Use GPU acceleration
- Use a smaller/faster model
- Reduce image resolution before processing
- Use batch processing if supported

### Connection Errors

**Check**:
- Server is running: `curl http://localhost:8000/v1/models`
- Correct API base URL
- Firewall settings
- Port availability

### Model Not Found

**Solutions**:
- Download model first: `huggingface-cli download microsoft/llava-1.6-vicuna-7b`
- Check model path in configuration
- Verify model format is supported

## Example Workflows

### Complete Local Setup

```bash
# Terminal 1: Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.6-vicuna-7b \
    --port 8000

# Terminal 2: Run PII detection
python main.py scan /data/images \
    --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model microsoft/llava-1.6-vicuna-7b \
    --regex  # Also use regex for text files
```

### Docker Setup

```bash
# Start LocalAI
docker run -d -p 8080:8080 \
    -v $PWD/models:/models \
    --name localai \
    localai/localai:latest-aio-cuda

# Run PII detection
python main.py scan /data/images \
    --multimodal \
    --multimodal-api-base http://localhost:8080/v1 \
    --multimodal-model llava
```

## Security Considerations

- **Network**: Run servers on localhost or secure network
- **Authentication**: Add API key authentication if exposing to network
- **Data**: Images are processed in memory, ensure secure storage
- **Logs**: Review server logs for any data leakage

## Cost Comparison

| Solution | Setup Cost | Per-Request Cost | Infrastructure |
|----------|-----------|------------------|----------------|
| OpenAI API | Free | ~$0.01-0.10/image | Cloud |
| vLLM | Free | Free | Your hardware |
| LocalAI | Free | Free | Your hardware |

**Note**: Local solutions require hardware investment but have no per-request costs.

## Further Reading

- [vLLM Documentation](https://docs.vllm.ai/)
- [LocalAI Documentation](https://localai.io/)
- [LLaVA Model Card](https://huggingface.co/microsoft/llava-1.6-vicuna-7b)
- [Multimodal Detection Guide](../user-guide/detection-methods.md#multimodal-image-detection-engine)
