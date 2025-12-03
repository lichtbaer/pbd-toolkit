"""Ollama-based LLM detection engine."""

import json
from typing import Optional
from core.engines.base import DetectionEngine, DetectionResult
from config import Config


class OllamaEngine:
    """Ollama-based LLM detection engine.
    
    Uses Ollama API for local LLM-based PII detection.
    Supports various models: llama3.2, mistral, etc.
    """
    
    name = "ollama"
    
    def __init__(self, config: Config):
        """Initialize Ollama engine.
        
        Args:
            config: Configuration object with Ollama settings
        """
        self.config = config
        self.enabled = getattr(config, 'use_ollama', False)
        self.base_url = getattr(config, 'ollama_base_url', 'http://localhost:11434')
        self.model_name = getattr(config, 'ollama_model', 'llama3.2')
        self.timeout = getattr(config, 'ollama_timeout', 30)
        self._available = None  # Cache availability check
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII using Ollama LLM.
        
        Args:
            text: Text content to analyze
            labels: Optional list of entity types to detect
        
        Returns:
            List of detection results
        """
        if not self.enabled:
            return []
        
        # Create prompt for PII detection
        prompt = self._create_prompt(text, labels)
        
        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "")
            
            return self._parse_response(response_text)
        except ImportError:
            self.config.logger.warning(
                "requests library not installed. Install with: pip install requests"
            )
            return []
        except Exception as e:
            self.config.logger.warning(f"Ollama detection failed: {e}")
            return []
    
    def _create_prompt(self, text: str, labels: list[str] | None) -> str:
        """Create prompt for LLM.
        
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

Return a JSON array of detected entities in this exact format:
[
  {{"text": "found text", "type": "entity_type", "confidence": 0.95}}
]

Only return the JSON array, nothing else."""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> list[DetectionResult]:
        """Parse LLM JSON response.
        
        Args:
            response_text: JSON response from LLM
        
        Returns:
            List of detection results
        """
        try:
            # Try to extract JSON from response (might have markdown code blocks)
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Remove markdown code blocks
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            if response_text.startswith("```json"):
                response_text = response_text[7:].strip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
            
            entities = json.loads(response_text)
            if not isinstance(entities, list):
                # If it's a dict with "entities" key
                entities = entities.get("entities", [])
            
            results = []
            for entity in entities:
                if isinstance(entity, dict) and "text" in entity:
                    results.append(DetectionResult(
                        text=entity.get("text", ""),
                        entity_type=entity.get("type", "UNKNOWN"),
                        confidence=entity.get("confidence"),
                        engine_name="ollama",
                        metadata={"ollama_model": self.model_name}
                    ))
            
            return results
        except json.JSONDecodeError as e:
            self.config.logger.debug(f"Failed to parse Ollama JSON response: {e}")
            return []
        except Exception as e:
            self.config.logger.warning(f"Error parsing Ollama response: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Ollama engine is available.
        
        Returns:
            True if enabled and Ollama API is accessible
        """
        if not self.enabled:
            return False
        
        # Cache availability check
        if self._available is not None:
            return self._available
        
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False
