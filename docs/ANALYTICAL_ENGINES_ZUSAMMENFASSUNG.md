# Zusammenfassung: Analytische Engines Erweiterung

## Kurzübersicht

Diese Analyse untersucht die Möglichkeiten, weitere analytische Engines zum PII Toolkit hinzuzufügen, ohne bestehende Ansätze zu ersetzen.

**Vollständige Analyse**: Siehe `ANALYTICAL_ENGINES_EXTENSION_ANALYSIS.md`

---

## Aktuelle Situation

### Bestehende Engines
1. **Regex-basiert** (`--regex`): Schnelle, deterministische Mustererkennung
2. **GLiNER NER** (`--ner`): AI-basierte Named Entity Recognition mit `urchade/gliner_medium-v2.1`

### Architektur-Stärken
- ✅ Modulares Design mit klarer Trennung
- ✅ Dependency Injection über Config-Objekt
- ✅ Thread-safe Implementierung
- ✅ Parallele Ausführung möglich

### Aktuelle Limitationen
- ⚠️ Nur zwei Engine-Typen unterstützt
- ⚠️ Keine Abstraktion für Engines
- ⚠️ Kein Plugin-System

---

## Vorgeschlagene Erweiterungen

### 1. Weitere NER-Modelle

#### spaCy German Models
- **ner-german** (`de_core_news_sm`, `de_core_news_md`, `de_core_news_lg`)
- Vorteile: Speziell für Deutsch optimiert, schnell, lokal ausführbar
- Integration: Neue `SpacyNEREngine` Klasse

**Beispiel-Nutzung**:
```bash
python main.py --path /data --spacy-ner --spacy-model de_core_news_lg
```

### 2. LLM-Integration

#### Ollama
- Lokale LLM-Ausführung
- Unterstützt verschiedene Modelle (llama3.2, mistral, etc.)
- Keine API-Kosten

**Beispiel-Nutzung**:
```bash
python main.py --path /data --ollama --ollama-model llama3.2
```

#### OpenAI-kompatible APIs
- Unterstützt OpenAI API und kompatible Endpunkte
- Flexibel für verschiedene Provider (OpenAI, Anthropic, lokale Server)
- Konfigurierbar über API-Key und Base-URL

**Beispiel-Nutzung**:
```bash
python main.py --path /data --openai-compatible \
    --openai-api-base https://api.example.com/v1 \
    --openai-model gpt-3.5-turbo
```

---

## Architektur-Vorschlag

### Engine-Abstraktion

Alle Engines implementieren ein gemeinsames Interface:

```python
class DetectionEngine(Protocol):
    name: str
    enabled: bool
    
    def detect(text: str, labels: list[str] | None) -> list[DetectionResult]:
        """Erkennt PII im Text."""
        pass
    
    def is_available() -> bool:
        """Prüft ob Engine verfügbar ist."""
        pass
```

### Engine Registry

Ähnlich wie `FileProcessorRegistry`:

```python
EngineRegistry.register("regex", RegexEngine)
EngineRegistry.register("gliner", GLiNEREngine)
EngineRegistry.register("spacy-ner", SpacyNEREngine)
EngineRegistry.register("ollama", OllamaEngine)
EngineRegistry.register("openai-compatible", OpenAICompatibleEngine)
```

### Parallele Ausführung

Mehrere Engines können gleichzeitig laufen:

```python
# Alle Engines parallel ausführen
for engine in enabled_engines:
    results = engine.detect(text)
    all_results.extend(results)
```

---

## Implementierungs-Plan

### Phase 1: Abstraktion (Woche 1)
- Engine-Interface definieren
- Registry erstellen
- Bestehende Engines refactoren

### Phase 2: spaCy Integration (Woche 2)
- `SpacyNEREngine` implementieren
- CLI-Argumente hinzufügen
- Tests und Dokumentation

### Phase 3: LLM Integration (Woche 3-4)
- `OllamaEngine` implementieren
- `OpenAICompatibleEngine` implementieren
- Error Handling und Retry-Logik
- Tests und Dokumentation

### Phase 4: Erweiterte Features (Woche 5)
- Engine-spezifische Statistiken
- Engine-Vergleich im Output
- Performance-Optimierung

---

## Vorteile

### ✅ Erweiterbarkeit
- Einfach neue Engines hinzufügen (Interface implementieren)
- Keine Änderungen an Core-Logik nötig

### ✅ Flexibilität
- Benutzer wählen Engines aus
- Engines können kombiniert werden
- Engine-spezifische Einstellungen

### ✅ Rückwärtskompatibilität
- Bestehende `--regex` und `--ner` Flags funktionieren weiter
- Bestehende Output-Formate unverändert
- Graduelle Migration möglich

### ✅ Parallelität
- Mehrere Engines laufen gleichzeitig
- Jede Engine hat eigenen Thread-Lock
- Ergebnisse werden automatisch aggregiert

---

## Beispiel-Nutzung

### Alle Engines kombinieren

```bash
python main.py --path /data \
    --regex \
    --ner \
    --spacy-ner --spacy-model de_core_news_lg \
    --ollama --ollama-model llama3.2 \
    --openai-compatible --openai-model gpt-3.5-turbo
```

### Nur deutsche NER-Modelle

```bash
python main.py --path /data \
    --spacy-ner --spacy-model de_core_news_lg \
    --ner  # GLiNER als Vergleich
```

### Nur LLM-basiert

```bash
python main.py --path /data \
    --ollama --ollama-model mistral
```

---

## Abhängigkeiten

### Neue Dependencies

```txt
spacy>=3.7.0          # Für spaCy NER
requests>=2.31.0       # Für Ollama/OpenAI APIs
```

### Model-Downloads

```bash
# spaCy deutsche Modelle
python -m spacy download de_core_news_sm
python -m spacy download de_core_news_md
python -m spacy download de_core_news_lg

# Ollama Modelle (via Ollama CLI)
ollama pull llama3.2
ollama pull mistral
```

---

## Output-Erweiterungen

### Erweiterte CSV-Spalten

```csv
match,file,type,confidence,engine,metadata
John Doe,/path/file.txt,AI-NER: Person,0.95,gliner,
John Doe,/path/file.txt,AI-NER: Person,0.92,spacy-ner,"{""spacy_label"": ""PER""}"
```

### Engine-Statistiken

- Anzahl Matches pro Engine
- Durchschnittliche Confidence pro Engine
- Verarbeitungszeit pro Engine

---

## Offene Fragen

1. **Deduplizierung**: Sollen Ergebnisse verschiedener Engines dedupliziert werden?
2. **Confidence-Aggregation**: Wie werden Confidences kombiniert, wenn mehrere Engines dasselbe finden?
3. **Performance**: Sollen Engines parallel oder sequenziell laufen?
4. **Fehlerbehandlung**: Soll ein Engine-Fehler alle Engines stoppen?
5. **Kosten-Management**: Für LLM-Engines: Rate Limiting oder Kosten-Tracking?

---

## Nächste Schritte

1. **Review**: Architektur-Vorschlag prüfen
2. **Prototyp**: Engine-Abstraktion implementieren
3. **spaCy Integration**: Erste neue Engine hinzufügen
4. **LLM Integration**: Ollama und OpenAI-kompatible Engines
5. **Testing**: Umfassende Tests für alle Engines
6. **Dokumentation**: Benutzer- und Entwickler-Dokumentation aktualisieren

---

**Status**: Vorschlag  
**Datum**: 2024  
**Vollständige Analyse**: `ANALYTICAL_ENGINES_EXTENSION_ANALYSIS.md`
