# PII Detection Methods

The PII Toolkit supports two complementary detection methods that can be used independently or together.

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

AI-powered detection using the GLiNER (Generalist and Lightweight model for Named Entity Recognition) model.

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

## Combined Usage

Use both methods together for comprehensive detection:

```bash
python main.py --path /data --regex --ner
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

| Method | Speed | Memory | CPU/GPU | Accuracy (Structured) | Accuracy (Unstructured) |
|--------|-------|--------|---------|----------------------|------------------------|
| Regex | Very Fast | Low | Low | High | Low |
| NER | Slow | High | High | Medium | High |
| Both | Slow | High | High | High | High |

## Best Practices

1. **Start with regex** for quick scans of structured data
2. **Add NER** when you need to find names and locations
3. **Use whitelist** to filter known false positives
4. **Test threshold** for NER if you get too many/too few results
5. **Monitor performance** - NER can be slow on large datasets
6. **Combine methods** for maximum coverage in critical scans
