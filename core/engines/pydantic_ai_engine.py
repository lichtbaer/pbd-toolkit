"""Unified LLM detection engine.

Text detection uses PydanticAI (optional dependency).
Multimodal image detection uses an OpenAI-compatible HTTP API (works with OpenAI,
vLLM, LocalAI) and does NOT require PydanticAI.
"""

import os
import time
import json
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from core.engines.base import DetectionResult
from config import Config

try:
    # Optional dependency: used for text-only LLM detection.
    from pydantic_ai import Agent  # type: ignore

    _PYDANTIC_AI_AVAILABLE = True
except Exception:  # pragma: no cover
    Agent = None  # type: ignore
    _PYDANTIC_AI_AVAILABLE = False


class PIIDetectionEntity(BaseModel):
    """Single PII entity detected by LLM."""

    text: str = Field(description="The detected text")
    type: str = Field(description="The entity type (e.g., PERSON, EMAIL, PHONE)")
    confidence: Optional[float] = Field(
        None, description="Confidence score between 0.0 and 1.0"
    )
    location: Optional[str] = Field(
        None, description="Location description (for images)"
    )


class PIIDetectionResponse(BaseModel):
    """Response model for PII detection."""

    entities: List[PIIDetectionEntity] = Field(
        default_factory=list, description="List of detected PII entities"
    )


class PydanticAIEngine:
    """Unified LLM detection engine using PydanticAI.

    Supports:
    - Ollama (local models)
    - OpenAI (GPT-3.5, GPT-4, GPT-4 Vision)
    - Anthropic (Claude)
    - Any LiteLLM-compatible provider

    Replaces OllamaEngine, OpenAICompatibleEngine, and MultimodalEngine.
    """

    name = "pydantic-ai"
    # LLM calls may be rate-limited and often rely on shared client/env state; keep serialized by default.
    thread_safe = False

    def __init__(self, config: Config):
        """Initialize PydanticAI engine.

        Args:
            config: Configuration object with LLM settings
        """
        self.config = config
        self.enabled = (
            getattr(config, "use_ollama", False)
            or getattr(config, "use_openai_compatible", False)
            or getattr(config, "use_multimodal", False)
            or getattr(config, "use_pydantic_ai", False)
        )

        # Determine provider and model
        self.provider = self._determine_provider()
        self.model = self._determine_model()
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        self.timeout = self._get_timeout()

        # Initialize agent
        self._agent: Optional[Agent] = None
        self._available = None  # Cache availability check

        # Adaptive rate limiting (preserved from OllamaEngine)
        self._last_request_time = 0
        self._last_request_duration = 0
        self._consecutive_slow_requests = 0
        self._slow_threshold = 5.0  # Seconds considered "slow"

    def _determine_provider(self) -> str:
        """Determine which provider to use based on config.

        Returns:
            Provider identifier (ollama, openai, anthropic, etc.)
        """
        if getattr(self.config, "use_ollama", False):
            return "ollama"
        elif getattr(self.config, "use_multimodal", False):
            # Multimodal typically uses OpenAI-compatible APIs
            return "openai"
        elif getattr(self.config, "use_openai_compatible", False):
            return "openai"
        elif getattr(self.config, "use_pydantic_ai", False):
            # Explicit PydanticAI config
            return getattr(self.config, "pydantic_ai_provider", "openai")
        return "openai"  # Default

    def _determine_model(self) -> str:
        """Determine which model to use based on provider.

        Returns:
            Model identifier
        """
        if self.provider == "ollama":
            return getattr(self.config, "ollama_model", "llama3.2")
        elif getattr(self.config, "use_multimodal", False):
            return getattr(self.config, "multimodal_model", "gpt-4-vision-preview")
        elif self.provider == "openai":
            return getattr(self.config, "openai_model", "gpt-3.5-turbo")
        return getattr(self.config, "pydantic_ai_model", "gpt-3.5-turbo")

    def _get_api_key(self) -> Optional[str]:
        """Get API key for the provider.

        Returns:
            API key or None
        """
        if self.provider == "ollama":
            return None  # Ollama doesn't need API key
        elif getattr(self.config, "use_multimodal", False):
            return (
                getattr(self.config, "multimodal_api_key", None)
                or getattr(self.config, "openai_api_key", None)
                or os.getenv("OPENAI_API_KEY")
            )
        elif self.provider == "openai":
            return getattr(self.config, "openai_api_key", None) or os.getenv(
                "OPENAI_API_KEY"
            )
        elif self.provider == "anthropic":
            return getattr(self.config, "anthropic_api_key", None) or os.getenv(
                "ANTHROPIC_API_KEY"
            )
        return getattr(self.config, "pydantic_ai_api_key", None)

    def _get_base_url(self) -> Optional[str]:
        """Get base URL for the provider.

        Returns:
            Base URL or None (uses default)
        """
        if self.provider == "ollama":
            return getattr(self.config, "ollama_base_url", "http://localhost:11434")
        elif getattr(self.config, "use_multimodal", False):
            return getattr(self.config, "multimodal_api_base", None) or getattr(
                self.config, "openai_api_base", "https://api.openai.com/v1"
            )
        elif self.provider == "openai":
            return getattr(self.config, "openai_api_base", "https://api.openai.com/v1")
        return getattr(self.config, "pydantic_ai_base_url", None)

    def _get_timeout(self) -> int:
        """Get timeout for requests.

        Returns:
            Timeout in seconds
        """
        if getattr(self.config, "use_multimodal", False):
            return getattr(self.config, "multimodal_timeout", 60)
        elif self.provider == "ollama":
            return getattr(self.config, "ollama_timeout", 30)
        return getattr(self.config, "openai_timeout", 30)

    def _get_agent(self) -> Agent:
        """Get or create PydanticAI agent.

        Returns:
            Initialized Agent instance
        """
        if not _PYDANTIC_AI_AVAILABLE:
            raise RuntimeError(
                "PydanticAI is not installed. Install with: pip install pydantic-ai"
            )

        if self._agent is None:
            # Build model string for PydanticAI
            # PydanticAI uses LiteLLM format: provider/model
            if self.provider == "ollama":
                # For Ollama, use litellm format
                model_str = f"ollama/{self.model}"
            elif self.provider == "anthropic":
                model_str = f"anthropic/{self.model}"
            else:
                model_str = f"openai/{self.model}"

            # Set API key if needed (PydanticAI uses environment variables)
            if self.api_key:
                if self.provider == "openai":
                    os.environ["OPENAI_API_KEY"] = self.api_key
                elif self.provider == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = self.api_key

            # Set base URL for custom endpoints (e.g., Ollama, local servers)
            if self.base_url:
                if self.provider == "ollama":
                    # LiteLLM uses OLLAMA_API_BASE for custom Ollama endpoints
                    os.environ["OLLAMA_API_BASE"] = self.base_url
                elif self.provider == "openai":
                    # For OpenAI-compatible APIs, use OPENAI_API_BASE
                    os.environ["OPENAI_API_BASE"] = self.base_url

            # Configure agent with system prompt and result type
            self._agent = Agent(
                model_str,
                result_type=PIIDetectionResponse,
                system_prompt=(
                    "You are a PII detection expert. Analyze text and extract "
                    "personally identifiable information. Always return valid structured data."
                ),
            )

        return self._agent

    def detect(
        self,
        text: str,
        labels: list[str] | None = None,
        image_path: Optional[str] = None,
    ) -> list[DetectionResult]:
        """Detect PII using PydanticAI.

        Args:
            text: Text content to analyze (or image path for multimodal)
            labels: Optional list of entity types to detect
            image_path: Optional path to image file (for multimodal detection)

        Returns:
            List of detection results
        """
        if not self.enabled:
            return []

        # Handle multimodal image detection
        if image_path or (
            getattr(self.config, "use_multimodal", False) and text and os.path.exists(text)
        ):
            return self._detect_image(image_path or text, labels)

        # Adaptive throttling (preserved from OllamaEngine)
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if self._last_request_duration > self._slow_threshold:
            wait_time = min(5.0, self._last_request_duration * 0.5)
            wait_time = wait_time * (1 + (self._consecutive_slow_requests * 0.5))

            if time_since_last < wait_time:
                sleep_time = wait_time - time_since_last
                if self.config.verbose:
                    self.config.logger.debug(
                        f"Throttling {self.provider} request: sleeping {sleep_time:.2f}s due to high load"
                    )
                time.sleep(sleep_time)

        # Create prompt
        prompt = self._create_prompt(text, labels)

        # Run detection (text)
        start_time = time.time()
        try:
            agent = self._get_agent()
            # PydanticAI uses run() for async or run_sync() for sync
            # result.data contains the PIIDetectionResponse
            result = agent.run_sync(prompt)

            # Update metrics
            duration = time.time() - start_time
            self._last_request_time = time.time()
            self._last_request_duration = duration

            if duration > self._slow_threshold:
                self._consecutive_slow_requests += 1
            else:
                self._consecutive_slow_requests = max(
                    0, self._consecutive_slow_requests - 1
                )

            # Convert to DetectionResult list
            # result.data should be a PIIDetectionResponse instance
            if hasattr(result, "data"):
                return self._convert_results(result.data)
            else:
                # Fallback if result structure is different
                self.config.logger.warning("Unexpected PydanticAI result structure")
                return []

        except Exception as e:
            duration = time.time() - start_time
            self._last_request_time = time.time()
            self._last_request_duration = duration
            self._consecutive_slow_requests += 1

            self.config.logger.warning(f"PydanticAI detection failed: {e}")
            if self.config.verbose:
                self.config.logger.debug(f"Error details: {e}", exc_info=True)
            return []

    def _detect_image(
        self, image_path: str, labels: Optional[List[str]]
    ) -> List[DetectionResult]:
        """Detect PII in image using an OpenAI-compatible multimodal endpoint.

        This path is "real" multimodal: it sends the image to the configured
        OpenAI-compatible endpoint (OpenAI, vLLM, LocalAI) using the standard
        `chat/completions` schema with `image_url`.

        Args:
            image_path: Path to image file
            labels: Optional list of entity types

        Returns:
            List of detection results
        """
        if not os.path.exists(image_path):
            self.config.logger.warning(f"Image file not found: {image_path}")
            return []

        # Ollama doesn't (currently) support vision via this toolkit.
        if self.provider == "ollama":
            self.config.logger.warning(
                "Multimodal image detection is not supported with provider 'ollama'. "
                "Use an OpenAI-compatible provider (OpenAI, vLLM, LocalAI) with a vision-capable model."
            )
            return []

        # Read and encode image
        try:
            from file_processors.image_processor import ImageProcessor

            img_processor = ImageProcessor()
            image_base64 = img_processor.get_image_base64(image_path)
            image_mime = img_processor.get_image_mime_type(image_path)
        except Exception as e:
            self.config.logger.error(f"Failed to read image {image_path}: {e}")
            return []

        if not image_base64 or not image_mime:
            self.config.logger.warning(f"Failed to read or identify image: {image_path}")
            return []

        image_data_url = f"data:{image_mime};base64,{image_base64}"

        prompt = self._create_image_prompt(labels)
        system_prompt = (
            "You are a PII detection expert. You MUST respond with ONLY valid JSON "
            "matching this schema: {\"entities\": [{\"text\": str, \"type\": str, "
            "\"confidence\": number|null, \"location\": str|null}]} . "
            "No markdown, no extra text."
        )

        start_time = time.time()
        try:
            # Hardened path: first try strict structured outputs (where supported),
            # then fall back to best-effort parsing without response_format.
            try:
                response_data = self._openai_chat_completions_with_image(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    image_data_url=image_data_url,
                    use_response_format=True,
                )
            except Exception:
                # Endpoint rejected strict response_format or failed in a way where a
                # retry without response_format might still work (OpenAI-compatible variance).
                response_data = self._openai_chat_completions_with_image(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    image_data_url=image_data_url,
                    use_response_format=False,
                )

            duration = time.time() - start_time
            self._last_request_time = time.time()
            self._last_request_duration = duration

            parsed = self._parse_openai_response_as_pii_detection(response_data)
            if not parsed:
                # Fallback: retry without strict response_format (some providers ignore/alter)
                response_data = self._openai_chat_completions_with_image(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    image_data_url=image_data_url,
                    use_response_format=False,
                )
                parsed = self._parse_openai_response_as_pii_detection(response_data)
                if not parsed:
                    return []
            return self._convert_results(parsed, image_path=image_path)
        except Exception as e:
            duration = time.time() - start_time
            self._last_request_time = time.time()
            self._last_request_duration = duration
            self.config.logger.warning(f"Multimodal detection failed: {e}")
            if self.config.verbose:
                self.config.logger.debug("Error details", exc_info=True)
            return []

    def _openai_chat_completions_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_url: str,
        use_response_format: bool,
    ) -> dict[str, Any]:
        """Call an OpenAI-compatible /chat/completions endpoint with an image."""
        try:
            import requests  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("requests is required for multimodal detection") from e

        base_url = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }

        if use_response_format:
            # OpenAI-compatible structured output (not supported everywhere).
            # We prefer json_schema when accepted, otherwise the request may fail and we fall back.
            payload["response_format"] = self._build_response_format()

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            # If strict mode is not supported by the endpoint, callers will retry without it.
            if use_response_format and getattr(self.config, "verbose", False):
                self.config.logger.debug(
                    f"Multimodal strict response_format request failed, will fall back: {e}"
                )
            raise

    @staticmethod
    def _build_response_format() -> dict[str, Any]:
        """Build a minimal JSON schema response_format payload for OpenAI-compatible APIs."""
        # Keep the schema small and broadly compatible with OpenAI-compatible servers.
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "pii_detection",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string"},
                                    "type": {"type": "string"},
                                    "confidence": {"type": ["number", "null"]},
                                    "location": {"type": ["string", "null"]},
                                },
                                "required": ["text", "type"],
                            },
                        }
                    },
                    "required": ["entities"],
                },
                # Some providers want strict=true for schema adherence.
                "strict": True,
            },
        }

    def _parse_openai_response_as_pii_detection(
        self, response_data: dict[str, Any]
    ) -> Optional[PIIDetectionResponse]:
        """Extract and validate PIIDetectionResponse from OpenAI-compatible response."""
        try:
            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        except Exception:
            content = ""

        if not isinstance(content, str) or not content.strip():
            if self.config.verbose:
                self.config.logger.warning(
                    "Multimodal response did not contain message.content"
                )
            return None

        json_text = self._extract_first_json_object(content)
        if not json_text:
            if self.config.verbose:
                self.config.logger.warning(
                    f"Failed to extract JSON from multimodal response: {content[:200]!r}"
                )
            return None

        try:
            payload = json.loads(json_text)
        except Exception as e:
            if self.config.verbose:
                self.config.logger.warning(f"Failed to parse JSON: {e}")
            return None

        try:
            return PIIDetectionResponse.model_validate(payload)
        except Exception as e:
            if self.config.verbose:
                self.config.logger.warning(f"Response validation failed: {e}")
            return None

    @staticmethod
    def _extract_first_json_object(text: str) -> Optional[str]:
        """Best-effort extraction of the first complete JSON object from a string.

        This is a fallback for providers/models that prepend/append natural language.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None

    def _create_prompt(self, text: str, labels: Optional[List[str]]) -> str:
        """Create prompt for text analysis.

        Args:
            text: Text to analyze
            labels: Optional list of entity types

        Returns:
            Formatted prompt string
        """
        # Use configured labels if available
        if hasattr(self.config, "ollama_labels") and self.config.ollama_labels:
            labels_config = self.config.ollama_labels
            label_desc_list = []
            for label_config in labels_config:
                term = label_config.get("term", "")
                desc = label_config.get("description", "")
                if desc and desc != term:
                    label_desc_list.append(f"- {term}: {desc}")
                else:
                    label_desc_list.append(f"- {term}")
            labels_str = "\n".join(label_desc_list)
        elif labels:
            labels_str = ", ".join(labels)
        else:
            labels_str = "all PII types"

        return f"""Analyze the following text and extract all personally identifiable information (PII).

Entity types to detect:
{labels_str}

Text:
{text}

Extract all PII entities and return them in the structured format."""

    def _create_image_prompt(self, labels: Optional[List[str]]) -> str:
        """Create prompt for image analysis.

        Args:
            labels: Optional list of entity types

        Returns:
            Prompt string
        """
        label_list = ", ".join(labels) if labels else "all PII types"

        return f"""Analyze this image and extract all personally identifiable information (PII).

Entity types to detect: {label_list}

Look for:
- Names (on documents, badges, screens)
- Email addresses
- Phone numbers
- Addresses
- ID numbers (passport, driver's license, etc.)
- Credit card numbers
- Social security numbers
- Any other personally identifiable information

Extract all PII entities and return them in the structured format."""

    def _convert_results(
        self, response: PIIDetectionResponse, image_path: Optional[str] = None
    ) -> List[DetectionResult]:
        """Convert PydanticAI response to DetectionResult list.

        Args:
            response: PIIDetectionResponse from agent
            image_path: Optional image path for metadata

        Returns:
            List of DetectionResult objects
        """
        results = []
        for entity in response.entities:
            metadata = {"provider": self.provider, "model": self.model}
            if image_path:
                metadata["image_path"] = image_path
                if entity.location:
                    metadata["location"] = entity.location

            results.append(
                DetectionResult(
                    text=entity.text,
                    entity_type=entity.type,
                    confidence=entity.confidence,
                    engine_name="pydantic-ai",
                    metadata=metadata,
                )
            )

        return results

    def is_available(self) -> bool:
        """Check if PydanticAI engine is available.

        Returns:
            True if enabled and dependencies are available
        """
        if not self.enabled:
            return False

        # Cache availability check
        if self._available is not None:
            return self._available

        # Availability rules:
        # - Text LLM detection requires pydantic-ai.
        # - Multimodal image detection requires requests + OpenAI-compatible provider.
        if getattr(self.config, "use_multimodal", False):
            try:
                import requests  # noqa: F401

                self._available = True
                return True
            except ImportError:
                self._available = False
                if self.config.verbose:
                    self.config.logger.warning(
                        "requests is required for multimodal detection. Install with: pip install requests"
                    )
                return False

        if _PYDANTIC_AI_AVAILABLE:
            self._available = True
            return True

        self._available = False
        if self.config.verbose:
            self.config.logger.warning(
                "PydanticAI not installed. Install with: pip install pydantic-ai"
            )
        return False
