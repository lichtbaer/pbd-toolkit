# LLM Integration Analysis

## Current State

### Overview
The project currently implements three separate LLM engines:

1. **OllamaEngine** (`core/engines/ollama_engine.py`)
   - Direct HTTP requests to Ollama API (`/api/generate`)
   - Supports local models (llama3.2, mistral, etc.)
   - Custom prompt formatting
   - Adaptive rate limiting with throttling
   - JSON response parsing with fallback handling

2. **OpenAICompatibleEngine** (`core/engines/openai_engine.py`)
   - Direct HTTP requests to OpenAI-compatible APIs (`/chat/completions`)
   - Supports OpenAI, Anthropic, local servers
   - Chat-based API format
   - JSON object response format
   - Basic error handling

3. **MultimodalEngine** (`core/engines/multimodal_engine.py`)
   - Direct HTTP requests to OpenAI-compatible APIs for images
   - Supports GPT-4 Vision, Claude 3, vLLM, LocalAI
   - Image base64 encoding
   - Multimodal message format
   - Similar structure to OpenAICompatibleEngine

### Common Patterns

All three engines share similar implementation patterns:

1. **HTTP Communication**: All use `requests` library directly
2. **Prompt Creation**: Each has a `_create_prompt()` method
3. **Response Parsing**: Each has a `_parse_response()` method
4. **Error Handling**: Similar try/except patterns
5. **Availability Checking**: `is_available()` method with caching
6. **Configuration**: Similar config attribute access patterns

### Code Duplication

**Identical/Similar Code:**
- HTTP request handling with `requests`
- JSON parsing and error handling
- API key/authentication handling
- Timeout configuration
- Availability checking patterns

**Differences:**
- Ollama uses `/api/generate` endpoint (completion-style)
- OpenAI/Multimodal use `/chat/completions` endpoint (chat-style)
- Ollama has adaptive rate limiting (unique feature)
- Multimodal has image encoding logic
- Response format differs (array vs object)

## Unified LLM Library Options

### Option 1: LiteLLM

**LiteLLM** is a unified library that supports:
- OpenAI, Anthropic, Cohere, HuggingFace, Ollama, and 100+ providers
- Unified interface for all providers
- Automatic retries, fallbacks, and rate limiting
- Streaming support
- Cost tracking

**Pros:**
- Single unified interface
- Built-in retry logic and rate limiting
- Supports all current providers (Ollama, OpenAI, Anthropic)
- Active maintenance and wide adoption
- Handles provider-specific quirks automatically
- Cost tracking capabilities

**Cons:**
- Additional dependency (~2MB)
- Slight abstraction overhead
- May hide provider-specific features

### Option 2: PydanticAI

**PydanticAI** is a type-safe AI framework built on Pydantic:
- Type-safe prompts and responses
- Built-in validation
- Supports multiple providers (OpenAI, Anthropic, Ollama via LiteLLM)
- Structured outputs with Pydantic models

**Pros:**
- Type safety and validation
- Clean, modern API
- Structured outputs (perfect for PII detection JSON)
- Built on Pydantic (already used in many projects)

**Cons:**
- Newer library (less mature than LiteLLM)
- Smaller community
- May require Pydantic v2
- Less provider support than LiteLLM directly

### Option 3: OpenAI SDK (with provider adapters)

Use OpenAI SDK with provider-specific adapters:
- OpenAI SDK for OpenAI/Anthropic
- Ollama Python SDK for Ollama
- Custom wrapper for unified interface

**Pros:**
- Official SDKs from providers
- Better type hints and IDE support
- Provider-specific optimizations

**Cons:**
- Multiple dependencies
- More code to maintain
- Less unified than LiteLLM

### Option 4: Custom Unified Wrapper

Create a custom wrapper that abstracts the differences:
- Keep current HTTP-based approach
- Add unified interface layer
- Consolidate common code

**Pros:**
- Full control
- No new dependencies
- Can preserve Ollama's adaptive rate limiting

**Cons:**
- More code to maintain
- Need to handle all provider quirks manually
- Reinventing the wheel

## Recommendation

### Should we migrate to a unified library?

**YES, with LiteLLM (or PydanticAI if type safety is priority)** - Here's why:

1. **Code Reduction**: ~300 lines of duplicated code could be reduced to ~100 lines
2. **Maintainability**: Single code path for all LLM providers
3. **Feature Parity**: LiteLLM supports all current providers
4. **Future-Proof**: Easy to add new providers (Anthropic, Cohere, etc.)
5. **Built-in Features**: Retry logic, rate limiting, cost tracking
6. **Community Support**: Well-maintained, widely used

### Migration Strategy

1. **Phase 1**: Create unified `LLMEngine` using LiteLLM
   - Replace OllamaEngine, OpenAICompatibleEngine, MultimodalEngine
   - Maintain same `DetectionEngine` protocol interface
   - Preserve adaptive rate limiting for Ollama

2. **Phase 2**: Configuration updates
   - Unified config structure for all LLM providers
   - Provider selection via model name or explicit provider

3. **Phase 3**: Testing and validation
   - Ensure same detection quality
   - Performance comparison
   - Backward compatibility

### Implementation Example

```python
from litellm import completion
from core.engines.base import DetectionEngine, DetectionResult

class UnifiedLLMEngine:
    """Unified LLM engine using LiteLLM."""
    
    name = "llm"
    
    def __init__(self, config: Config):
        self.config = config
        self.provider = getattr(config, 'llm_provider', 'ollama')  # ollama, openai, anthropic
        self.model = getattr(config, 'llm_model', None)
        self.api_key = getattr(config, 'llm_api_key', None)
        self.base_url = getattr(config, 'llm_base_url', None)
        
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        prompt = self._create_prompt(text, labels)
        
        response = completion(
            model=f"{self.provider}/{self.model}",
            messages=[{"role": "user", "content": prompt}],
            api_key=self.api_key,
            base_url=self.base_url,
            response_format={"type": "json_object"}
        )
        
        return self._parse_response(response.choices[0].message.content)
```

### Considerations

1. **Ollama Adaptive Rate Limiting**: This is a unique feature that should be preserved. Could be implemented as a LiteLLM callback or wrapper.

2. **Multimodal Support**: LiteLLM supports multimodal models, but needs verification for image handling.

3. **Backward Compatibility**: Maintain same config options and CLI flags during transition.

4. **Dependency Size**: LiteLLM adds ~2MB, but removes need for manual HTTP handling.

## Conclusion

**Recommendation: Migrate to LiteLLM (or PydanticAI for type safety)**

The current implementation has significant code duplication across three engines. A unified library would:
- Reduce code by ~60%
- Improve maintainability
- Add features (retries, rate limiting, cost tracking)
- Make adding new providers trivial
- Maintain same functionality

**Library Choice:**
- **LiteLLM**: Best for maximum provider support and maturity
- **PydanticAI**: Best if type safety and structured outputs are priorities (uses LiteLLM under the hood for providers)

The migration effort is moderate (~1-2 days) but provides long-term benefits.

**Note**: If "pydat ai Model" refers to a specific library not mentioned here, please clarify and we can evaluate it specifically.
