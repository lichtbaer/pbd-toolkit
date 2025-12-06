# Privacy-Focused Statistics Mode - Quick Reference

## Overview

A new output mode that generates JSON statistics files with aggregated data by privacy dimensions and detection modules, without storing individual PII matches.

## Key Features

- ✅ **Privacy-First**: No PII text or file paths in output
- ✅ **Aggregated Data**: Statistics by dimension, module, and file type
- ✅ **GDPR Compliant**: Minimizes data retention
- ✅ **Optional Mode**: Can be used alongside or instead of detailed findings

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
   - Maps detection types to privacy dimensions

2. **Statistics Aggregator** (`core/statistics_aggregator.py`)
   - Aggregates matches by dimension/module

3. **Privacy Statistics Writer** (`core/writers.py`)
   - Generates JSON output

4. **CLI Integration** (`core/cli.py`)
   - `--statistics-mode` flag
   - `--statistics-output` option

## Usage Examples

```bash
# Statistics-only mode
pii-toolkit scan /path --regex --ner --statistics-mode

# Statistics + detailed findings
pii-toolkit scan /path --regex --ner --format statistics --format csv

# Custom output path
pii-toolkit scan /path --regex --ner --statistics-mode --statistics-output ./stats.json
```

## Output Structure

```json
{
  "metadata": {...},
  "statistics_by_dimension": {
    "identity": {
      "total_count": 450,
      "by_module": {...},
      "by_type": {...},
      "files_affected": 234,
      "sensitivity_level": "high"
    }
  },
  "statistics_by_module": {...},
  "statistics_by_file_type": {...},
  "summary": {...}
}
```

## Implementation Phases

1. **Phase 1**: Core Infrastructure (Dimension Mapper, Statistics Extensions)
2. **Phase 2**: Output Writer (PrivacyStatisticsWriter)
3. **Phase 3**: CLI Integration (Options, Pipeline Integration)
4. **Phase 4**: Testing & Documentation

## Privacy Guarantees

- ✅ No PII text stored
- ✅ No file paths included
- ✅ Only aggregated counts
- ✅ Anonymized data
- ✅ Optional mode

## Related Documents

- [Detailed Plan](./privacy-focused-statistics-plan.md)
- [German Plan](./privacy-focused-statistics-plan-de.md)
- [Architecture Overview](./privacy-focused-statistics-architecture.md)
