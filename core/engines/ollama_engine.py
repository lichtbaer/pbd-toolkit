"""Ollama-based LLM detection engine.

DEPRECATED: This engine is deprecated in favor of PydanticAIEngine.
Use --pydantic-ai --pydantic-ai-provider ollama instead of --ollama.
This file is kept for backward compatibility only.
"""

import json
import re
import warnings
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
        warnings.warn(
            "OllamaEngine is deprecated. Use PydanticAIEngine with --pydantic-ai --pydantic-ai-provider ollama instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.config = config
        self.enabled = getattr(config, 'use_ollama', False)
        self.base_url = getattr(config, 'ollama_base_url', 'http://localhost:11434')
        self.model_name = getattr(config, 'ollama_model', 'llama3.2')
        self.timeout = getattr(config, 'ollama_timeout', 30)
        self._available = None  # Cache availability check
        
        # Adaptive rate limiting
        self._last_request_time = 0
        self._last_request_duration = 0
        self._consecutive_slow_requests = 0
        self._slow_threshold = 5.0  # Seconds considered "slow"
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII using Ollama LLM.
        
        Args:
            text: Text content to analyze
            labels: Optional list of entity types to detect. If None, uses configured Ollama labels.
        
        Returns:
            List of detection results
        """
        if not self.enabled:
            return []
            
        # Use configured Ollama labels if not overridden
        # labels arg is usually passed from text_processor, which passes ner_labels.
        # We ignore passed labels if we have specific ollama configuration
        if hasattr(self.config, 'ollama_labels') and self.config.ollama_labels:
            labels_config = self.config.ollama_labels
        else:
            # Fallback to whatever was passed or generic
            labels_config = [{"term": l, "description": l} for l in (labels or [])]
            
        # Adaptive throttling
        import time
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        # If last request was slow, wait a bit
        if self._last_request_duration > self._slow_threshold:
            # Wait up to 5 seconds based on how slow it was
            wait_time = min(5.0, self._last_request_duration * 0.5)
            # If we had multiple slow requests, wait longer
            wait_time = wait_time * (1 + (self._consecutive_slow_requests * 0.5))
            
            if time_since_last < wait_time:
                sleep_time = wait_time - time_since_last
                if self.config.verbose:
                    self.config.logger.debug(f"Throttling Ollama request: sleeping {sleep_time:.2f}s due to high load")
                time.sleep(sleep_time)
        
        # Create prompt for PII detection
        prompt = self._create_prompt(text, labels_config)
        
        # Simple retry mechanism with backoff
        max_retries = 3
        retry_delay = 2  # seconds
        
        import requests
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
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
                
                # Update metrics
                duration = time.time() - start_time
                self._last_request_time = time.time()
                self._last_request_duration = duration
                
                if duration > self._slow_threshold:
                    self._consecutive_slow_requests += 1
                else:
                    self._consecutive_slow_requests = max(0, self._consecutive_slow_requests - 1)
                
                response.raise_for_status()
                
                result = response.json()
                response_text = result.get("response", "")
                
                return self._parse_response(response_text)
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Update metrics even on failure
                self._last_request_time = time.time()
                self._last_request_duration = time.time() - start_time
                self._consecutive_slow_requests += 1 # Failures count as "very slow"
                
                if attempt < max_retries - 1:
                    self.config.logger.warning(f"Ollama request failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.config.logger.warning(f"Ollama detection failed after {max_retries} attempts: {e}")
                    return []
            except ImportError:
                self.config.logger.warning(
                    "requests library not installed. Install with: pip install requests"
                )
                return []
            except Exception as e:
                self.config.logger.warning(f"Ollama detection failed: {e}")
                return []
        return []
    
    def _create_prompt(self, text: str, labels_config: list[dict]) -> str:
        """Create prompt for LLM.
        
        Args:
            text: Text to analyze
            labels_config: List of dicts with 'term' and 'description'
        
        Returns:
            Formatted prompt string
        """
        # Format labels with descriptions
        label_desc_list = []
        for l in labels_config:
            term = l.get("term", "")
            desc = l.get("description", "")
            if desc and desc != term:
                label_desc_list.append(f"- {term}: {desc}")
            else:
                label_desc_list.append(f"- {term}")
        
        labels_str = "\n".join(label_desc_list)
        
        prompt = f"""Analyze the following text and extract all personally identifiable information (PII).

Entity types to detect:
{labels_str}

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
            # Try to extract JSON from response using regex
            # Look for a JSON array [ ... ]
            match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if match:
                response_text = match.group(0)
            else:
                # If no array found, try to clean up markdown code blocks as fallback
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    # Remove first line (```json or ```) and last line (```)
                    if len(lines) >= 2:
                        response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
            
            entities = json.loads(response_text)
            if not isinstance(entities, list):
                # If it's a dict with "entities" key
                if isinstance(entities, dict):
                    entities = entities.get("entities", [])
                else:
                    self.config.logger.debug(f"Ollama response is valid JSON but not a list/dict: {type(entities)}")
                    return []
            
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
            self.config.logger.warning(f"Failed to parse Ollama JSON response: {e}")
            if self.config.verbose:
                self.config.logger.debug(f"Raw response: {response_text}")
            return []
        except Exception as e:
            self.config.logger.warning(f"Error parsing Ollama response: {e}")
            if self.config.verbose:
                self.config.logger.debug(f"Raw response: {response_text}")
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
