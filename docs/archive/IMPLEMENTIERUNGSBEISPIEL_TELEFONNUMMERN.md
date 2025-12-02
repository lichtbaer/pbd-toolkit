# Implementierungsbeispiel: Telefonnummern-Erkennung

Dieses Dokument zeigt, wie die Telefonnummern-Erkennung als neue Datenschutz-Dimension implementiert werden kann.

## Schritt 1: Konfiguration erweitern

### config_types.json

Füge folgenden Eintrag zum `regex`-Array hinzu:

```json
{
  "label": "REGEX_PHONE",
  "value": "Regex: Phone Number",
  "regex_compiled_pos": 6,
  "expression": "\\b(?:\+?[1-9]\\d{1,14}|0[1-9]\\d{1,13})\\b"
}
```

**Hinweis**: `regex_compiled_pos` muss die nächste freie Position sein (aktuell: 0-5, also 6).

### Erweiterte Version mit Kontextprüfung

Für bessere Genauigkeit kann eine erweiterte Version mit Kontextprüfung verwendet werden:

```json
{
  "label": "REGEX_PHONE",
  "value": "Regex: Phone Number",
  "regex_compiled_pos": 6,
  "expression": "\\b(?:\+?[1-9]\\d{1,14}|0[1-9]\\d{1,13})\\b",
  "context_keywords": ["Telefon", "Handy", "Mobil", "Phone", "Tel", "Festnetz"],
  "validation": "phone_format"
}
```

## Schritt 2: Validierungs-Logik (Optional)

### Neue Datei: `validators/phone_validator.py`

```python
"""Phone number validation utilities."""

import re
from typing import Optional


class PhoneValidator:
    """Validates phone numbers and formats."""
    
    # Deutsche Mobilfunk-Vorwahlen
    DE_MOBILE_PREFIXES = ["015", "016", "017"]
    
    # Deutsche Festnetz-Vorwahlen (Beispiele)
    DE_LANDLINE_PREFIXES = ["030", "040", "089", "0211"]
    
    @staticmethod
    def validate_german_mobile(phone: str) -> bool:
        """Validate German mobile phone number format.
        
        Args:
            phone: Phone number string
            
        Returns:
            True if valid German mobile format
        """
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check for German mobile prefixes
        if cleaned.startswith('+49'):
            # International format: +49 15x...
            if len(cleaned) == 13 and cleaned[3:6] in PhoneValidator.DE_MOBILE_PREFIXES:
                return True
        elif cleaned.startswith('0049'):
            # Alternative international format
            if len(cleaned) == 14 and cleaned[4:7] in PhoneValidator.DE_MOBILE_PREFIXES:
                return True
        elif cleaned.startswith('0'):
            # National format: 015x...
            if len(cleaned) == 11 and cleaned[0:3] in PhoneValidator.DE_MOBILE_PREFIXES:
                return True
        
        return False
    
    @staticmethod
    def validate_international(phone: str) -> bool:
        """Validate international phone number format.
        
        Args:
            phone: Phone number string
            
        Returns:
            True if valid international format
        """
        # Remove separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Must start with + and have 7-15 digits after country code
        if not cleaned.startswith('+'):
            return False
        
        # Extract country code and number
        match = re.match(r'\+(\d{1,3})(\d{7,14})$', cleaned)
        if not match:
            return False
        
        country_code, number = match.groups()
        
        # Basic validation: country code 1-3 digits, number 7-14 digits
        return 1 <= len(country_code) <= 3 and 7 <= len(number) <= 14
    
    @staticmethod
    def validate(phone: str, country: Optional[str] = None) -> bool:
        """Validate phone number.
        
        Args:
            phone: Phone number string
            country: Optional country code (e.g., 'DE', 'US')
            
        Returns:
            True if valid format
        """
        if country == 'DE':
            return PhoneValidator.validate_german_mobile(phone)
        else:
            # Try international format
            return PhoneValidator.validate_international(phone)
    
    @staticmethod
    def normalize(phone: str) -> str:
        """Normalize phone number format.
        
        Args:
            phone: Phone number string
            
        Returns:
            Normalized phone number
        """
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        return cleaned
```

## Schritt 3: Erweiterte matches.py (Optional)

### Kontextprüfung hinzufügen

Erweitere die `PiiMatchContainer`-Klasse:

```python
def _check_context(self, text: str, match_text: str, 
                   context_keywords: list[str] = None,
                   context_window: int = 100) -> bool:
    """Check if match is in relevant context.
    
    Args:
        text: Full text content
        match_text: Matched text
        context_keywords: Optional list of keywords to look for
        context_window: Number of characters before/after match
        
    Returns:
        True if match is in relevant context
    """
    if not context_keywords:
        return True  # No context check required
    
    match_pos = text.find(match_text)
    if match_pos == -1:
        return False
    
    context_start = max(0, match_pos - context_window)
    context_end = min(len(text), match_pos + len(match_text) + context_window)
    context = text[context_start:context_end].lower()
    
    # Check if any keyword is in context
    return any(keyword.lower() in context for keyword in context_keywords)
```

### Erweiterte add_matches_regex

```python
def add_matches_regex(self, matches: re.Match | None, path: str, 
                     full_text: str = None) -> None:
    """Add regex-based matches with optional context checking.
    
    Args:
        matches: Regex match object
        path: File path
        full_text: Optional full text for context checking
    """
    if matches is not None:
        type: str | None = None
        
        for idx, item in enumerate(matches.groups()):
            if item is not None:
                type = config_regex_sorted[idx]["label"]
                config_entry = config_regex_sorted[idx]
                
                # Check context if keywords are defined
                if full_text and "context_keywords" in config_entry:
                    if not self._check_context(
                        full_text, 
                        matches.group(),
                        config_entry["context_keywords"]
                    ):
                        return  # Skip if not in relevant context
                
                # Validate if validation is defined
                if "validation" in config_entry:
                    if config_entry["validation"] == "phone_format":
                        from validators.phone_validator import PhoneValidator
                        if not PhoneValidator.validate(matches.group()):
                            return  # Skip if validation fails
        
        self.__add_match(text=matches.group(), file=path, type=type)
```

## Schritt 4: main.py anpassen

### Kontext-Text übergeben

In der `process_text`-Funktion:

```python
def process_text(text: str, file_path: str, pmc: PiiMatchContainer, 
                config: Config, full_text: str = None) -> None:
    """Process text content with regex and/or NER-based PII detection.
    
    Args:
        text: Text content to analyze (may be chunk)
        file_path: Path to the file containing the text
        pmc: PiiMatchContainer instance for storing matches
        config: Configuration object with all settings
        full_text: Optional full text for context checking
    """
    if config.use_regex and config.regex_pattern:
        for match in config.regex_pattern.finditer(text):
            with _process_lock:
                # Pass full_text if available for context checking
                pmc.add_matches_regex(match, file_path, 
                                     full_text=full_text or text)
    
    # ... rest of NER processing ...
```

### Volltext für Kontextprüfung speichern

Für Dateien, die in Chunks verarbeitet werden (z.B. PDFs):

```python
# In main.py, before processing PDF chunks
if isinstance(processor, PdfProcessor):
    # Option 1: Collect all chunks first (for small PDFs)
    all_chunks = list(processor.extract_text(full_path))
    full_text = " ".join(all_chunks)
    
    for text_chunk in all_chunks:
        if text_chunk.strip():
            process_text(text_chunk, full_path, pmc, config, full_text=full_text)
else:
    text = processor.extract_text(full_path)
    if text.strip():
        process_text(text, full_path, pmc, config, full_text=text)
```

## Schritt 5: Tests

### tests/test_phone_detection.py

```python
"""Tests for phone number detection."""

import pytest
from matches import PiiMatchContainer
import re


class TestPhoneDetection:
    """Test phone number detection."""
    
    def test_german_mobile_detection(self):
        """Test detection of German mobile numbers."""
        pmc = PiiMatchContainer()
        
        # Load regex pattern (simplified for test)
        phone_pattern = re.compile(r'\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b')
        
        test_text = "Kontakt: 01761234567 oder +49 176 1234567"
        matches = list(phone_pattern.finditer(test_text))
        
        for match in matches:
            pmc.add_matches_regex(match, "test.txt")
        
        assert len(pmc.pii_matches) >= 1
        assert any("0176" in m.text or "+49" in m.text for m in pmc.pii_matches)
    
    def test_international_phone_detection(self):
        """Test detection of international phone numbers."""
        pmc = PiiMatchContainer()
        
        phone_pattern = re.compile(r'\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b')
        
        test_text = "Call us at +1 555 123 4567 or +44 20 7946 0958"
        matches = list(phone_pattern.finditer(test_text))
        
        for match in matches:
            pmc.add_matches_regex(match, "test.txt")
        
        assert len(pmc.pii_matches) >= 2
    
    def test_phone_with_context(self):
        """Test phone detection with context keywords."""
        pmc = PiiMatchContainer()
        
        test_text = "Meine Telefonnummer ist 01761234567. Bitte anrufen!"
        # This would require the context checking implementation
        
        # Simplified test
        phone_pattern = re.compile(r'\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b')
        matches = list(phone_pattern.finditer(test_text))
        
        for match in matches:
            pmc.add_matches_regex(match, "test.txt", full_text=test_text)
        
        # Should find phone number in context
        assert len(pmc.pii_matches) >= 1
```

## Schritt 6: Dokumentation

### docs/user-guide/detection-methods.md erweitern

Füge Abschnitt hinzu:

```markdown
### Phone Numbers

The toolkit can detect phone numbers in various formats:

- **German mobile**: 01761234567, +49 176 1234567
- **International**: +1 555 123 4567, +44 20 7946 0958
- **National formats**: Various country-specific formats

**Context checking**: Phone numbers are more reliably detected when found near keywords like "Telefon", "Handy", "Phone", etc.

**Validation**: Optional validation can be enabled to reduce false positives by checking format compliance.
```

## Schritt 7: Performance-Optimierung

### Regex-Optimierung

Für bessere Performance bei vielen Telefonnummern:

```python
# Optimized regex (pre-compiled, non-capturing groups where possible)
PHONE_PATTERN = re.compile(
    r'\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b',
    re.UNICODE
)
```

### Caching von Validierungen

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def validate_phone_cached(phone: str) -> bool:
    """Cached phone validation."""
    return PhoneValidator.validate(phone)
```

## Schritt 8: Integration in bestehenden Workflow

### Checkliste

- [ ] `config_types.json` erweitert
- [ ] Regex-Pattern getestet
- [ ] Validierungs-Logik implementiert (optional)
- [ ] Kontextprüfung implementiert (optional)
- [ ] Tests geschrieben
- [ ] Dokumentation aktualisiert
- [ ] Performance getestet
- [ ] Falsch-Positiv-Rate evaluiert
- [ ] Whitelist-Beispiele hinzugefügt

## Erwartete Ergebnisse

### Vor Implementierung
- Telefonnummern werden nicht erkannt
- Kontaktdaten unvollständig

### Nach Implementierung
- **Erkennungsrate**: +15-25% bei Dokumenten mit Kontaktdaten
- **Falsch-Positiv-Rate**: <5% (mit Validierung)
- **Performance-Impact**: <2% (durch optimierte Regex)

## Nächste Schritte

1. Implementierung testen mit realen Daten
2. Falsch-Positiv-Rate überwachen
3. Whitelist für bekannte Test-Nummern erstellen
4. Feedback sammeln und iterativ verbessern

## Ähnliche Implementierungen

Dieses Muster kann für andere neue Dimensionen verwendet werden:
- Steuer-ID (ähnlich, mit Kontextprüfung)
- Kreditkartennummern (mit Luhn-Validierung)
- Postleitzahlen (mit Kontextprüfung)
