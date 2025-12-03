"""spaCy-based NER detection engine."""

from typing import Optional
from core.engines.base import DetectionEngine, DetectionResult
from config import Config


class SpacyNEREngine:
    """spaCy-based NER detection engine for German models.
    
    Supports German spaCy models:
    - de_core_news_sm (small)
    - de_core_news_md (medium)
    - de_core_news_lg (large)
    """
    
    name = "spacy-ner"
    
    def __init__(self, config: Config):
        """Initialize spaCy NER engine.
        
        Args:
            config: Configuration object with spaCy settings
        """
        self.config = config
        self.enabled = getattr(config, 'use_spacy_ner', False)
        self.model_name = getattr(config, 'spacy_model_name', 'de_core_news_lg')
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Lazy load spaCy model."""
        if not self.enabled:
            return
        
        try:
            import spacy
            self.config.logger.info(f"Loading spaCy model: {self.model_name}")
            self.model = spacy.load(self.model_name)
            self.config.logger.info(f"spaCy model '{self.model_name}' loaded successfully")
        except OSError as e:
            self.config.logger.warning(
                f"spaCy model '{self.model_name}' not found. "
                f"Install with: python -m spacy download {self.model_name}"
            )
            self.model = None
        except ImportError:
            self.config.logger.warning(
                "spaCy not installed. Install with: pip install spacy"
            )
            self.model = None
        except Exception as e:
            self.config.logger.error(f"Failed to load spaCy model: {e}")
            self.model = None
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII using spaCy NER model.
        
        Args:
            text: Text content to analyze
            labels: Ignored for spaCy (uses model's built-in entity types)
        
        Returns:
            List of detection results
        """
        if not self.enabled or not self.model:
            return []
        
        try:
            doc = self.model(text)
            results = []
            
            # Map spaCy labels to internal entity types
            label_mapping = {
                "PER": "NER_PERSON",
                "LOC": "NER_LOCATION",
                "ORG": "NER_ORGANIZATION",
                "MISC": "NER_MISC",
            }
            
            for ent in doc.ents:
                # Map spaCy label to internal type
                entity_type = label_mapping.get(ent.label_, f"SPACY_{ent.label_}")
                
                # Get confidence if available (spaCy doesn't provide confidence by default)
                confidence = None
                if hasattr(ent, 'score'):
                    confidence = ent.score
                elif hasattr(ent, '_'):
                    # Try to get confidence from token attributes
                    confidence = getattr(ent._, 'score', None)
                
                results.append(DetectionResult(
                    text=ent.text,
                    entity_type=entity_type,
                    confidence=confidence,
                    engine_name="spacy-ner",
                    metadata={
                        "spacy_label": ent.label_,
                        "spacy_label_id": ent.label,
                        "start_char": ent.start_char,
                        "end_char": ent.end_char
                    }
                ))
            
            return results
        except Exception as e:
            self.config.logger.warning(f"spaCy detection error: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if spaCy engine is available.
        
        Returns:
            True if enabled and model is loaded
        """
        return self.enabled and self.model is not None
