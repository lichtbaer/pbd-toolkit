# PII Detection Methods

The PII Toolkit supports multiple detection engines that can be used independently or in combination for comprehensive PII detection.

## Regular Expression-Based Detection

Regular expression (regex) pattern matching is a fast, rule-based approach for detecting structured PII.

### Usage

Enable regex detection:

```bash
python main.py --path /data --regex
```

### Supported Patterns

#### German Pension Insurance Numbers

**Pattern**: `REGEX_RVNR`

Detects German public pension insurance fund IDs (*Deutsche Rentenversicherungsnummern*).

Format:
- Two digits: Insurance provider (02-89)
- Two digits: Day of birth (01-31)
- Two digits: Month of birth (01-12)
- Three digits: Year of birth (last two digits + gender code)
- One letter: First letter of first name (A-Z)
- Three digits: Additional identifier

Example: `15070649C103`

#### IBAN (International Bank Account Numbers)

**Pattern**: `REGEX_IBAN`

Detects IBANs, optimized for German bank accounts.

Format:
- Two letters: Country code
- Two digits: Check digits
- Up to 30 alphanumeric characters (may include spaces)

Example: `DE11 2003 8978 4565 1232 00`

#### Email Addresses

**Pattern**: `REGEX_EMAIL`

Detects email addresses in common formats.

Format: `local-part@domain`

Example: `user@example.com`

**Note**: The pattern is simplified and may not match all valid RFC-compliant addresses, but covers the vast majority of real-world email addresses.

#### IPv4 Addresses

**Pattern**: `REGEX_IPV4`

Detects IPv4 addresses.

Format: Four octets (0-255) separated by dots

Example: `192.168.1.1`

#### Signal Words

**Pattern**: `REGEX_WORDS`

Detects German keywords commonly associated with personal data:
- Abmahnung (warning/cease and desist)
- Bewerbung (application)
- Zeugnis (certificate/reference)
- Entwicklungsbericht (development report)
- Gutachten (expert opinion)
- Krankmeldung (sick note)

#### Private PGP Keys

**Pattern**: `REGEX_PGPPRV`

Detects private PGP keys.

Format: Begins with `BEGIN PGP PRIVATE KEY`

#### Phone Numbers

**Pattern**: `REGEX_PHONE`

Detects phone numbers in various formats:
- German mobile: `01761234567`, `+49 176 1234567`
- International: `+1 555 123 4567`, `+44 20 7946 0958`
- National formats: Various country-specific formats

**Note**: The pattern is broad and may match some non-phone numbers. Consider using a whitelist to filter known false positives.

#### Tax ID (Steuer-ID)

**Pattern**: `REGEX_TAX_ID`

Detects German tax identification numbers (*Steueridentifikationsnummer*).

Format: 11 digits

Example: `12345678901`

**Note**: This pattern matches any 11-digit number. In practice, tax IDs are often found near keywords like "Steuer-ID", "TIN", or "IdNr". Consider context checking for better accuracy.

#### BIC (Bank Identifier Code)

**Pattern**: `REGEX_BIC`

Detects BIC codes (also known as SWIFT codes) used for international bank transfers.

Format:
- 4 letters: Bank code
- 2 letters: Country code
- 2 alphanumeric: Location code
- Optional 3 alphanumeric: Branch code

Example: `DEUTDEFF` or `DEUTDEFF500`

#### Postal Codes (Germany)

**Pattern**: `REGEX_POSTAL_CODE`

Detects German postal codes (*Postleitzahlen*).

Format: 5 digits (00000-99999)

Example: `10115` (Berlin)

**Note**: This pattern matches any 5-digit number. Postal codes are most relevant when found in combination with street addresses or city names. Consider context checking for better accuracy.

#### Extended Signal Words

**Pattern**: `REGEX_SIGNAL_WORDS_EXTENDED`

Detects extended German keywords commonly associated with personal data across multiple categories:

**Medical**: Diagnose, Therapie, Medikament, Krankheit, Behandlung, Arzt, Klinik, Krankenhaus, Patient, Symptom, Operation, Rezept

**Financial**: Gehalt, Lohn, Einkommen, Vermögen, Schulden, Kredit, Darlehen, Kontostand, Überweisung, Rechnung, Mahnung

**Legal**: Klage, Anwalt, Gericht, Urteil, Vertrag, Vereinbarung, Einverständniserklärung, Datenschutzerklärung

**Application/Employment**: Lebenslauf, CV, Bewerbung, Referenz, Arbeitszeugnis, Qualifikation, Erfahrung, Kompetenz

This extends the original signal words pattern (`REGEX_WORDS`) with additional categories.

#### Credit Card Numbers

**Pattern**: `REGEX_CREDIT_CARD`

Detects credit card numbers with automatic validation using the Luhn algorithm.

**Supported card types**:
- Visa: Starts with 4, 13 or 16 digits
- Mastercard: Starts with 51-55, 16 digits
- American Express: Starts with 34 or 37, 15 digits
- Discover: Starts with 6011 or 65, 16 digits
- Diners Club: Starts with 3, 14 digits

**Validation**: All detected numbers are validated using the Luhn algorithm. Only numbers that pass the Luhn check are reported, significantly reducing false positives.

**Example**: `4111111111111111` (test number)

**Security Note**: Credit card numbers are highly sensitive data. Ensure proper handling and storage of any detected numbers.

### Configuration

Regex patterns are defined in `config_types.json`. Each pattern includes:
- `label`: Internal identifier
- `value`: Display name in output
- `expression`: Regular expression pattern
- `regex_compiled_pos`: Position in compiled regex

### Advantages

- **Fast**: Pattern matching is very efficient
- **Deterministic**: Same input always produces same results
- **Low resource usage**: No model loading required
- **Customizable**: Easy to add new patterns

### Limitations

- **False positives**: May match non-PII that looks similar
- **Language-specific**: Some patterns are optimized for German data
- **Structured data only**: Works best with formatted data

## AI-Based Named Entity Recognition (NER)

AI-powered detection using multiple analytical engines. The toolkit supports several detection engines that can be used individually or in combination.

### Usage

Enable NER detection:

```bash
python main.py --path /data --ner
```

**Note**: Requires the GLiNER model to be downloaded (see [Installation](../getting-started/installation.md)).

### Supported Entity Types

#### Person Names

**Label**: `NER_PERSON`

Detects names of individuals.

Example: "Max Mustermann", "Dr. Jane Smith"

#### Locations

**Label**: `NER_LOCATION`

Detects geographical locations (cities, countries, addresses).

Example: "Berlin", "United States", "123 Main Street"

#### Health Data (Experimental)

**Label**: `NER_HEALTH`

Detects health-related information.

**Warning**: This is experimental and may have poor quality results.

#### Passwords (Experimental)

**Label**: `NER_PASSWORD`

Detects potential passwords.

**Warning**: This is experimental and may have poor quality results. Use with caution.

#### Biometric Data

**Label**: `NER_BIOMETRIC`

Detects biometric information such as:
- Fingerprints
- Facial recognition data
- Iris scans
- DNA information

**Relevance**: Very high - Biometric data is considered special category data under GDPR Article 9.

**Warning**: This is a new feature and detection quality may vary. Results should be reviewed carefully.

#### Political Affiliation

**Label**: `NER_POLITICAL`

Detects political affiliations, party memberships, and political opinions.

**Relevance**: Very high - Political opinions are considered special category data under GDPR Article 9.

**Warning**: This is a new feature and detection quality may vary. Results should be reviewed carefully.

#### Religious Belief

**Label**: `NER_RELIGIOUS`

Detects religious affiliations and beliefs.

**Relevance**: Very high - Religious beliefs are considered special category data under GDPR Article 9.

**Warning**: This is a new feature and detection quality may vary. Results should be reviewed carefully.

### Confidence Scores

NER detection provides confidence scores (0.0 to 1.0) indicating how certain the model is about each detection. The default threshold is 0.5, meaning only detections with confidence ≥ 0.5 are reported.

Adjust threshold in `config_types.json`:

```json
{
  "settings": {
    "ner_threshold": 0.5
  }
}
```

### Configuration

NER labels are defined in `config_types.json`. Each label includes:
- `label`: Internal identifier
- `value`: Display name in output
- `term`: Term used by the GLiNER model

### Advantages

- **Context-aware**: Understands context, not just patterns
- **Flexible**: Can detect unstructured PII
- **Confidence scores**: Provides reliability indicators
- **Language-agnostic**: Works with multiple languages

### Limitations

- **Slower**: Model inference takes time
- **Resource-intensive**: Requires significant memory and CPU/GPU
- **Model dependency**: Requires model download (~500MB)
- **False positives/negatives**: AI models are not perfect
- **Experimental features**: Some entity types have poor quality

## Additional Detection Engines

### spaCy NER Engine

German-specific Named Entity Recognition using spaCy models optimized for German text.

**Usage**:

```bash
python main.py --path /data --spacy-ner --spacy-model de_core_news_lg
```

**Available Models**:
- `de_core_news_sm` - Small model (fast, lower accuracy)
- `de_core_news_md` - Medium model (balanced)
- `de_core_news_lg` - Large model (slower, higher accuracy, default)

**Installation**:

```bash
pip install spacy
python -m spacy download de_core_news_lg
```

**Advantages**:
- Optimized for German text
- Fast inference
- Local execution (no API calls)
- Good accuracy for German names and locations

**Limitations**:
- German-focused (may not work well for other languages)
- Requires model download (~500MB for large model)

### Ollama LLM Engine

Local LLM-based detection using Ollama. Runs completely offline.

**Usage**:

```bash
python main.py --path /data --ollama --ollama-model llama3.2
```

**Configuration**:
- `--ollama-url`: Ollama API base URL (default: `http://localhost:11434`)
- `--ollama-model`: Model to use (default: `llama3.2`)

**Installation**:

1. Install Ollama: https://ollama.ai
2. Download a model:
   ```bash
   ollama pull llama3.2
   ollama pull mistral
   ```

**Features**:
- Completely local (no data leaves your system)
- No API costs
- Supports various models
- Good for complex PII detection
- **Robustness**: Includes automatic retries and adaptive rate limiting to prevent server overload

**Limitations**:
- Requires Ollama server running
- Slower than specialized NER models
- Requires significant local resources

### OpenAI-Compatible API Engine

Detection using OpenAI API or compatible endpoints (e.g., Anthropic, local servers).

**Usage**:

```bash
python main.py --path /data --openai-compatible \
    --openai-api-key YOUR_KEY \
    --openai-model gpt-3.5-turbo
```

**Configuration**:
- `--openai-api-base`: API base URL (default: `https://api.openai.com/v1`)
- `--openai-api-key`: API key (or set `OPENAI_API_KEY` environment variable)
- `--openai-model`: Model to use (default: `gpt-3.5-turbo`)

**Advantages**:
- High-quality detection
- Supports various providers
- Good for complex scenarios

**Limitations**:
- Requires API key and internet connection
- API costs apply
- Slower than local models
- Data sent to external service

### Multimodal Image Detection Engine

Detection of PII in images using multimodal AI models. Supports OpenAI GPT-4 Vision, Anthropic Claude 3, and open-source models via vLLM or LocalAI.

**Usage**:

```bash
# With OpenAI GPT-4 Vision
python main.py --path /data/images --multimodal \
    --multimodal-api-key YOUR_KEY \
    --multimodal-model gpt-4-vision-preview

# With local vLLM server
python main.py --path /data/images --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model llava-v1.6-vicuna-7b
```

**Supported Image Formats**:
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff, .tif)
- WebP (.webp)

**Configuration**:
- `--multimodal`: Enable multimodal image detection
- `--multimodal-api-base`: API base URL (defaults to `--openai-api-base` or `https://api.openai.com/v1`)
- `--multimodal-api-key`: API key (defaults to `--openai-api-key` or `OPENAI_API_KEY` env var)
- `--multimodal-model`: Model to use (default: `gpt-4-vision-preview`)
- `--multimodal-timeout`: API timeout in seconds (default: 60)

**What It Detects**:
- Names on documents, badges, screens
- Email addresses visible in images
- Phone numbers
- Addresses
- ID numbers (passport, driver's license, etc.)
- Credit card numbers
- Social security numbers
- Any other personally identifiable information visible in images

**Advantages**:
- Detects PII in images (not just text files)
- Works with scanned documents, screenshots, photos
- High accuracy with modern vision models
- Supports local models for privacy

**Limitations**:
- Requires API access (OpenAI, vLLM, or LocalAI)
- Slower than text-based detection
- API costs may apply (depending on provider)
- Images are sent to external service (unless using local models)
- Requires significant API timeout for large images

**Privacy Considerations**:
- Images are sent to external APIs unless using local models
- For sensitive data, use local models (vLLM/LocalAI)
- See [Open-Source Models Guide](open-source-models.md) for local setup

**Example Use Cases**:
- Scanning screenshots for PII
- Analyzing scanned documents
- Detecting PII in photos of documents
- Finding sensitive information in image files

## Combined Usage

Use multiple engines together for comprehensive detection:

```bash
# Basic combination
python main.py --path /data --regex --ner

# All engines (text-based)
python main.py --path /data \
    --regex \
    --ner \
    --spacy-ner --spacy-model de_core_news_lg \
    --ollama --ollama-model llama3.2

# German-focused
python main.py --path /data \
    --regex \
    --spacy-ner --spacy-model de_core_news_lg

# With image detection
python main.py --path /data \
    --regex \
    --ner \
    --multimodal --multimodal-api-key YOUR_KEY
```

### When to Use Each Method

**Use Regex when**:
- You need fast processing
- You're looking for structured data (emails, IBANs, etc.)
- You have limited computational resources
- You need deterministic results

**Use NER when**:
- You need to detect unstructured PII (names, locations)
- You're analyzing natural language text
- You can tolerate longer processing times
- You have sufficient computational resources

**Use Both when**:
- You want comprehensive coverage
- You're analyzing diverse data types
- You can afford the processing time
- You want to maximize detection rate

## Performance Comparison

| Engine | Speed | Memory | CPU/GPU | Accuracy (Structured) | Accuracy (Unstructured) | Local | Cost |
|--------|-------|--------|---------|----------------------|------------------------|-------|------|
| Regex | Very Fast | Low | Low | High | Low | Yes | Free |
| GLiNER | Slow | High | High | Medium | High | Yes | Free |
| spaCy | Medium | Medium | Medium | Medium | High (German) | Yes | Free |
| Ollama | Very Slow (Adaptive) | Very High | Very High | Medium | High | Yes | Free |
| OpenAI | Slow | Low | Low | Medium | Very High | No | Paid |
| Multimodal | Very Slow | Low | Low | Medium | High (Images) | Optional | Paid/Free |

## Engine Selection Guide

**For German text analysis**:
- Use `--spacy-ner` with `de_core_news_lg` for best German-specific results
- Combine with `--regex` for structured data

**For maximum privacy**:
- Use `--ollama` for completely local processing
- No data leaves your system

**For best accuracy**:
- Use `--openai-compatible` with GPT-4
- Combine with `--regex` for structured patterns

**For speed**:
- Use `--regex` only for fastest results
- Add `--spacy-ner` for German names/locations

**For comprehensive coverage**:
- Combine multiple engines: `--regex --ner --spacy-ner`

## Best Practices

1. **Start with regex** for quick scans of structured data
2. **Add NER** when you need to find names and locations
3. **Use whitelist** to filter known false positives
4. **Test threshold** for NER if you get too many/too few results
5. **Monitor performance** - NER can be slow on large datasets
6. **Combine methods** for maximum coverage in critical scans
