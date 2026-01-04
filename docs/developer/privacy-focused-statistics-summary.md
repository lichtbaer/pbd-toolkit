# Privacy-Focused Statistics Mode - Quick Reference

## Overview

An output mode that generates JSON statistics files with aggregated data by privacy dimensions and detection modules, without storing individual PII matches.

## Key Features

- **Privacy-first**: no PII text or file paths in the statistics output
- **Aggregated data**: statistics by dimension, module, and file type
- **Optional mode**: can be used alongside detailed findings
- **Strict mode**: `--statistics-strict` avoids keeping file paths in memory (some unique-file metrics become `null`)

## Privacy Dimensions

| Dimension | Sensitivity | Examples |
|-----------|-------------|----------|
| Identity | High | Names, Passports, IDs, SSN |
| Contact Information | Medium | Email, Phone, Postal Codes |
| Financial | High | IBAN, BIC, Credit Cards |
| Health | Very High | Health Data, Medical Conditions |
| Biometric | Very High | Biometric Data |
| Sensitive Personal Data | Very High | Political, Religious, Sexual Orientation |
| Location | Medium | Physical Locations, Addresses |
| Credentials & Security | Very High | Passwords, PGP Keys |
| Organizational | Low | Organizations, Dates, Money |
| Signal Words | Medium | Contextual Indicators |
| Other | Variable | Unclassified Types |

## Implementation Components

1. **Privacy Dimension Mapper** (`core/privacy_dimensions.py`)
2. **Statistics Aggregator** (`core/statistics_aggregator.py`)
3. **Privacy Statistics Writer** (`core/writers.py`)
4. **CLI Integration** (`core/cli.py`)
   - `--statistics-mode` flag
   - `--statistics-output` option

## Usage Examples

```bash
# Statistics-only mode (still writes the normal findings output file)
pii-toolkit scan /path --regex --ner --statistics-mode

# Strict privacy statistics (no file paths kept in memory)
pii-toolkit scan /path --regex --ner --statistics-mode --statistics-strict

# Statistics + detailed findings
pii-toolkit scan /path --regex --ner --statistics-mode --format csv

# Custom output path for the statistics JSON
pii-toolkit scan /path --regex --ner --statistics-mode --statistics-output ./stats.json
```

## Output Structure

```json
{
  "metadata": { "...": "..." },
  "statistics_by_dimension": { "...": "..." },
  "statistics_by_module": { "...": "..." },
  "statistics_by_file_type": { "...": "..." },
  "summary": { "...": "..." }
}
```

## Related Documents

- [Architecture Overview](./privacy-focused-statistics-architecture.md)
