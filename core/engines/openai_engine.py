"""OpenAI-compatible API detection engine."""

import json
import os
from typing import Optional
from core.engines.base import DetectionEngine, DetectionResult
from config import Config


class OpenAICompatibleEngine:
    """OpenAI-compatible API detection engine.
    
    Supports OpenAI API and compatible endpoints (e.g., Anthropic, local servers).
    """
    
    name = "openai-compatible"
    
    def __init__(self, config: Config):
        """Initialize OpenAI-compatible engine.
        
        Args:
            config: Configuration object with API settings
        """
        self.config = config
        self.enabled = getattr(config, 'use_openai_compatible', False)
        self.api_base = getattr(config, 'openai_api_base', 'https://api.openai.com/v1')
        # Get API key from config or environment variable
        self.api_key = getattr(config, 'openai_api_key', None) or os.getenv('OPENAI_API_KEY')
        self.model = getattr(config, 'openai_model', 'gpt-3.5-turbo')
        self.timeout = getattr(config, 'openai_timeout', 30)
        self._available = None  # Cache availability check
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII using OpenAI-compatible API.
        
        Args:
            text: Text content to analyze
            labels: Optional list of entity types to detect
        
        Returns:
            List of detection results
        """
        if not self.enabled:
            return []
        
        if not self.api_key:
            self.config.logger.warning(
                "OpenAI API key not configured. Set openai_api_key in config or OPENAI_API_KEY env var."
            )
            return []
        
        prompt = self._create_prompt(text, labels)
        
        try:
            import requests
            
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a PII detection expert. Analyze text and extract personally identifiable information. Always return valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            return self._parse_response(content)
        except ImportError:
            self.config.logger.warning(
                "requests library not installed. Install with: pip install requests"
            )
            return []
        except Exception as e:
            self.config.logger.warning(f"OpenAI-compatible detection failed: {e}")
            return []
    
    def _create_prompt(self, text: str, labels: list[str] | None) -> str:
        """Create prompt for OpenAI API.
        
        Args:
            text: Text to analyze
            labels: Optional list of entity types
        
        Returns:
            Formatted prompt string
        """
        label_list = ", ".join(labels) if labels else "all PII types"
        
        prompt = f"""Analyze the following text and extract all personally identifiable information (PII).

Entity types to detect: {label_list}

Text:
{text}

Return a JSON object with this exact structure:
{{
  "entities": [
    {{"text": "found text", "type": "entity_type", "confidence": 0.95}}
  ]
}}"""
        
        return prompt
    
    def _parse_response(self, content: str) -> list[DetectionResult]:
        """Parse OpenAI JSON response.
        
        Args:
            content: JSON response content
        
        Returns:
            List of detection results
        """
        try:
            data = json.loads(content)
            entities = data.get("entities", [])
            
            results = []
            for entity in entities:
                if isinstance(entity, dict) and "text" in entity:
                    results.append(DetectionResult(
                        text=entity.get("text", ""),
                        entity_type=entity.get("type", "UNKNOWN"),
                        confidence=entity.get("confidence"),
                        engine_name="openai-compatible",
                        metadata={"openai_model": self.model}
                    ))
            
            return results
        except json.JSONDecodeError as e:
            self.config.logger.debug(f"Failed to parse OpenAI JSON response: {e}")
            return []
        except Exception as e:
            self.config.logger.warning(f"Error parsing OpenAI response: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if OpenAI-compatible engine is available.
        
        Returns:
            True if enabled and API is accessible
        """
        if not self.enabled:
            return False
        
        if not self.api_key:
            return False
        
        # Cache availability check
        if self._available is not None:
            return self._available
        
        try:
            import requests
            response = requests.get(
                f"{self.api_base}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False
