# Integrationsplan - Zusammenfassung

## Übersicht

Dieses Dokument fasst den Integrationsplan für zwei neue Features zusammen:
1. **Dateityp-Erkennung via Magic Numbers** - Optionale Erkennung von Dateitypen anhand von Dateiköpfen (Magic Numbers)
2. **Bilderkennung via Multimodale Modelle** - PII-Erkennung in Bildern über OpenAI-kompatible multimodale Modelle

## Feature 1: Magic Number Dateityp-Erkennung

### Ziel
Ergänzung der Dateityp-Erkennung um Magic Numbers (Dateiköpfe), um Dateitypen genauer zu identifizieren als nur über Dateiendungen.

### Aktueller Stand
- Dateityp-Erkennung basiert derzeit nur auf Dateiendungen (`.pdf`, `.docx`, etc.)
- `FileScanner` extrahiert Endungen über `os.path.splitext()`
- `FileProcessorRegistry` matcht Prozessoren basierend auf Endungen

### Geplante Implementierung

#### Technische Komponenten
1. **Neue Bibliothek**: `python-magic` oder `filetype` (Fallback)
2. **Neues Modul**: `core/file_type_detector.py` - Magic Number Detector
3. **Integration**: 
   - In `FileScanner` für optionale Magic-Number-Erkennung
   - In `FileProcessorRegistry` für MIME-Type-basierte Prozessorauswahl
4. **Konfiguration**: 
   - `--use-magic-detection`: Aktiviert Magic-Number-Erkennung
   - `--magic-fallback`: Nutzt Magic Numbers als Fallback bei fehlender Endung

#### Vorteile
- Erkennung von Dateien ohne oder mit falscher Endung
- Genauere Dateityp-Identifikation
- Unterstützung für Dateien, die nicht über Endung identifizierbar sind

### Abhängigkeiten
- `python-magic>=0.4.27` (oder `python-magic-bin` für Windows)
- `filetype>=1.2.0` (optionaler Fallback)

---

## Feature 2: Bilderkennung via Multimodale Modelle

### Ziel
PII-Erkennung in Bildern über OpenAI-kompatible multimodale Modelle (z.B. GPT-4 Vision, Claude 3, oder Open-Source-Alternativen via vLLM/LocalAI).

### Aktueller Stand
- Detektions-Engines arbeiten nur mit Text
- Keine Bildverarbeitung vorhanden
- OpenAI-kompatible Engine existiert, aber nur für Text

### Geplante Implementierung

#### Technische Komponenten
1. **Neuer Bildprozessor**: `file_processors/image_processor.py`
   - Unterstützt: JPEG, PNG, GIF, BMP, TIFF, WebP
   - Bereitet Bilder für multimodale Verarbeitung vor (Base64-Kodierung)

2. **Neue Multimodale Engine**: `core/engines/multimodal_engine.py`
   - Unterstützt OpenAI-kompatible APIs
   - Verarbeitet Bilder und extrahiert PII
   - Unterstützt lokale Modelle via vLLM/LocalAI

3. **Integration**:
   - Registrierung in `FileProcessorRegistry` und `EngineRegistry`
   - Anpassung von `TextProcessor` für Bildverarbeitung
   - Neue Konfigurationsoptionen

4. **Konfiguration**:
   - `--multimodal`: Aktiviert Bilderkennung
   - `--multimodal-api-base`: API-URL (Standard: OpenAI)
   - `--multimodal-model`: Modellname
   - `--multimodal-api-key`: API-Key

#### Unterstützte Modelle/APIs
- **OpenAI**: GPT-4 Vision
- **Anthropic**: Claude 3
- **vLLM**: Lokale Open-Source-Modelle (z.B. LLaVA)
- **LocalAI**: Lokale OpenAI-kompatible API

#### Beispiel-Konfiguration für lokale Modelle
```bash
# vLLM Server starten
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.5-7b \
    --port 8000

# PII Toolkit nutzen
python main.py \
    --path /pfad/zu/bildern \
    --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model llava-v1.6-vicuna-7b
```

### Dokumentation
- Aktualisierung der Detektionsmethoden-Dokumentation
- Neuer Guide für Open-Source-Modelle (`docs/user-guide/open-source-models.md`)
- Hinweise auf vLLM und LocalAI in der Installation-Dokumentation
- Aktualisierung der README mit neuen Features

### Abhängigkeiten
- `requests>=2.31.0` (bereits vorhanden)
- `Pillow>=10.0.0` (optional, für Bildvalidierung)

---

## Implementierungsreihenfolge

### Phase 1: Magic Number Detection
1. Dependencies hinzufügen
2. `FileTypeDetector` Klasse erstellen
3. Integration in `FileScanner` und `FileProcessorRegistry`
4. Konfiguration und CLI-Argumente
5. Tests und Dokumentation

### Phase 2: Multimodale Bilderkennung
1. `ImageProcessor` und `MultimodalEngine` erstellen
2. Registrierung und Integration
3. Konfiguration und CLI-Argumente
4. Tests und Dokumentation
5. Open-Source-Modelle Guide

---

## Wichtige Hinweise

### Magic Number Detection
- Sollte optional sein, um Performance-Impact bei großen Scans zu vermeiden
- Fallback-Verhalten bei fehlgeschlagener Erkennung

### Bilderkennung
- Kann langsamer sein als Textverarbeitung - ggf. Async/Batch-Processing
- API-Kosten können hoch sein - Kostenhinweise in Dokumentation
- **Datenschutz**: Bilder werden an externe APIs gesendet - Datenschutzhinweise erforderlich
- Rate Limiting für API-Calls implementieren
- Robuste Fehlerbehandlung für API-Fehler

### Open-Source-Modelle
- vLLM und LocalAI ermöglichen lokale Ausführung
- Keine Datenübertragung an externe Dienste
- Eigene Infrastruktur erforderlich
- Dokumentation für Setup und Konfiguration

---

## Zukünftige Erweiterungen

1. **OCR-Integration**: Tesseract/EasyOCR für Text-Extraktion aus Bildern
2. **Batch-Processing**: Mehrere Bilder in einem API-Call verarbeiten
3. **Bildvorverarbeitung**: Bilder vor API-Versand optimieren/resizen
4. **Caching**: Analyseergebnisse cachen
5. **Lokale Modelle**: Direkte Integration ohne API-Schicht

---

## Detaillierter Plan

Für technische Details siehe: `docs/developer/FEATURE_INTEGRATION_PLAN.md`
