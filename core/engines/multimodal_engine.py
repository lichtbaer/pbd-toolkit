"""Multimodal detection engine for image analysis.

DEPRECATED: This engine is deprecated in favor of PydanticAIEngine.
Use --pydantic-ai --pydantic-ai-provider openai instead of --multimodal.
This file is kept for backward compatibility only.
"""

import base64
import json
import os
import warnings
from typing import Optional, List
from core.engines.base import DetectionEngine, DetectionResult
from config import Config


class MultimodalEngine:
    """Multimodal detection engine for images using OpenAI-compatible APIs.
    
    Supports:
    - OpenAI GPT-4 Vision
    - Anthropic Claude 3
    - Local models via vLLM
    - LocalAI compatible endpoints
    """
    
    name = "multimodal"
    
    def __init__(self, config: Config):
        """Initialize multimodal engine.
        
        Args:
            config: Configuration object with API settings
        """
        warnings.warn(
            "MultimodalEngine is deprecated. Use PydanticAIEngine with --pydantic-ai --pydantic-ai-provider openai instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.config = config
        self.enabled = getattr(config, 'use_multimodal', False)
        self.api_base = getattr(config, 'multimodal_api_base', None) or \
                       getattr(config, 'openai_api_base', 'https://api.openai.com/v1')
        self.api_key = getattr(config, 'multimodal_api_key', None) or \
                      getattr(config, 'openai_api_key', None) or \
                      os.getenv('OPENAI_API_KEY')
        self.model = getattr(config, 'multimodal_model', 'gpt-4-vision-preview')
        self.timeout = getattr(config, 'multimodal_timeout', 60)
        self._available = None
    
    def detect(self, text: str, labels: Optional[List[str]] = None, 
               image_path: Optional[str] = None) -> List[DetectionResult]:
        """Detect PII in image.
        
        Args:
            text: Not used for images (kept for interface compatibility).
                  If text contains a file path (for backward compatibility), it will be used.
            labels: Optional list of entity types to detect
            image_path: Path to image file (required for image processing).
                       Can also be passed via text parameter for Protocol compatibility.
        
        Returns:
            List of detection results
        """
        if not self.enabled:
            return []
        
        # If image_path not provided, try to get it from text (for Protocol compatibility)
        if not image_path and text and os.path.exists(text):
            image_path = text
        
        if not image_path:
            return []
        
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
                self.config.logger.warning(f"Failed to read or identify image: {image_path}")
                return []
        except Exception as e:
            self.config.logger.error(f"Failed to read image {image_path}: {e}")
            return []
        
        # Create prompt
        prompt = self._create_prompt(labels)
        
        # Call API
        try:
            import requests
            
            # Prepare messages with image
            messages = [
                {
                    "role": "system",
                    "content": "You are a PII detection expert. Analyze images and extract personally identifiable information. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_mime};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            return self._parse_response(content, image_path)
            
        except ImportError:
            self.config.logger.warning("requests library not installed")
            return []
        except Exception as e:
            self.config.logger.warning(f"Multimodal detection failed: {e}")
            return []
    
    def _create_prompt(self, labels: Optional[List[str]]) -> str:
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

Return a JSON object with this exact structure:
{{
  "entities": [
    {{"text": "found text", "type": "entity_type", "confidence": 0.95, "location": "description of where in image"}}
  ]
}}"""
    
    def _parse_response(self, content: str, image_path: str) -> List[DetectionResult]:
        """Parse API response.
        
        Args:
            content: JSON response content
            image_path: Path to analyzed image
            
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
                        engine_name="multimodal",
                        metadata={
                            "model": self.model,
                            "image_path": image_path,
                            "location": entity.get("location", "")
                        }
                    ))
            
            return results
        except json.JSONDecodeError as e:
            self.config.logger.debug(f"Failed to parse multimodal JSON response: {e}")
            return []
        except Exception as e:
            self.config.logger.warning(f"Error parsing multimodal response: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if multimodal engine is available.
        
        Returns:
            True if enabled and API is accessible
        """
        if not self.enabled:
            return False
        
        if not self.api_key:
            return False
        
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
