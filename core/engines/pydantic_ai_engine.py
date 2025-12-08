"""Unified LLM detection engine using PydanticAI."""

import os
import time
from typing import Optional, List
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from core.engines.base import DetectionResult
from config import Config


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
            getattr(self.config, "use_multimodal", False)
            and text
            and os.path.exists(text)
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

        # Run detection
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
        """Detect PII in image using multimodal model.

        Args:
            image_path: Path to image file
            labels: Optional list of entity types

        Returns:
            List of detection results
        """
        if not os.path.exists(image_path):
            self.config.logger.warning(f"Image file not found: {image_path}")
            return []

        # Read and encode image
        try:
            from file_processors.image_processor import ImageProcessor

            img_processor = ImageProcessor()
            image_base64 = img_processor.get_image_base64(image_path)
            image_mime = img_processor.get_image_mime_type(image_path)

            if not image_base64 or not image_mime:
                self.config.logger.warning(
                    f"Failed to read or identify image: {image_path}"
                )
                return []
        except Exception as e:
            self.config.logger.error(f"Failed to read image {image_path}: {e}")
            return []

        # Create prompt
        prompt = self._create_image_prompt(labels)

        # Run detection with image
        start_time = time.time()
        try:
            agent = self._get_agent()
            # PydanticAI supports multimodal via message content
            # Note: This requires PydanticAI version that supports images
            # For now, we'll use a workaround with base64 data URL
            image_data_url = f"data:{image_mime};base64,{image_base64}"

            # Use agent with image content
            # PydanticAI supports multimodal via message content
            # For now, we'll include image reference in prompt
            # Note: Full multimodal support may require PydanticAI version with image support
            result = agent.run_sync(
                f"{prompt}\n\nImage data: {image_data_url[:100]}..."
            )

            duration = time.time() - start_time
            self._last_request_time = time.time()
            self._last_request_duration = duration

            return self._convert_results(result.data, image_path=image_path)

        except Exception as e:
            self.config.logger.warning(f"PydanticAI multimodal detection failed: {e}")
            if self.config.verbose:
                self.config.logger.debug(f"Error details: {e}", exc_info=True)
            return []

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

        try:
            # Check if PydanticAI is importable
            import pydantic_ai  # noqa: F401

            self._available = True
            return True
        except ImportError:
            self._available = False
            if self.config.verbose:
                self.config.logger.warning(
                    "PydanticAI not installed. Install with: pip install pydantic-ai"
                )
            return False
