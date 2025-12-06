# Privacy-Focused Statistics Output Mode - Integration Plan

## Overview

This document outlines the plan for integrating a privacy-focused statistics output mode that generates JSON files with statistical evaluations of scan results. The goal is to minimize processing of person-related data by aggregating statistics on privacy dimensions and detection modules rather than storing individual PII matches.

## Objectives

1. **Privacy Protection**: Aggregate data at dimension/module level to avoid storing individual PII instances
2. **Statistical Insights**: Provide meaningful statistics for analysis without exposing sensitive data
3. **Modular Design**: Integrate seamlessly with existing architecture
4. **Compliance**: Support GDPR/privacy compliance by minimizing data retention

## Architecture

### Components

1. **Privacy Dimension Mapper** (`core/privacy_dimensions.py`)
   - Maps detection types (labels) to privacy dimensions
   - Provides categorization logic for all supported PII types

2. **Statistics Aggregator** (`core/statistics_aggregator.py`)
   - Aggregates matches by privacy dimension and module
   - Tracks counts, distributions, and metadata without storing PII text

3. **Privacy Statistics Writer** (`core/writers.py` - extension)
   - New writer class: `PrivacyStatisticsWriter`
   - Generates JSON output with aggregated statistics

4. **CLI Integration** (`core/cli.py`)
   - New option: `--statistics-mode` or `--stats-only`
   - Output format: `statistics` (generates JSON statistics file)

## Privacy Dimensions

Based on GDPR Article 9 and data protection principles, the following dimensions are defined:

### 1. Identity
- **Types**: Names, IDs, Passport Numbers, Personalausweis, SSN, RVNR
- **Sensitivity**: High
- **Examples**: `NER_PERSON`, `REGEX_PASSPORT`, `REGEX_PERSONALAUSWEIS`, `REGEX_SSN_*`, `REGEX_RVNR`

### 2. Contact Information
- **Types**: Email, Phone, Postal Codes, IP Addresses
- **Sensitivity**: Medium
- **Examples**: `REGEX_EMAIL`, `REGEX_PHONE`, `REGEX_POSTAL_CODE`, `REGEX_IPV4`, `NER_LOCATION`

### 3. Financial
- **Types**: IBAN, BIC, Credit Cards, Tax IDs, Financial Information
- **Sensitivity**: High
- **Examples**: `REGEX_IBAN`, `REGEX_BIC`, `REGEX_CREDIT_CARD`, `REGEX_TAX_ID`, `NER_FINANCIAL`

### 4. Health
- **Types**: Health Data, Medical Conditions, Medications
- **Sensitivity**: Very High (GDPR Article 9)
- **Examples**: `NER_HEALTH`, `NER_MEDICAL_CONDITION`, `NER_MEDICATION`, `REGEX_MRN`

### 5. Biometric
- **Types**: Biometric Data
- **Sensitivity**: Very High (GDPR Article 9)
- **Examples**: `NER_BIOMETRIC`

### 6. Sensitive Personal Data (GDPR Article 9)
- **Types**: Political Affiliation, Religious Belief, Sexual Orientation, Ethnic Origin, Criminal Conviction
- **Sensitivity**: Very High
- **Examples**: `NER_POLITICAL`, `NER_RELIGIOUS`, `NER_SEXUAL_ORIENTATION`, `NER_ETHNIC_ORIGIN`, `NER_CRIMINAL_CONVICTION`

### 7. Location
- **Types**: Physical Locations, Addresses
- **Sensitivity**: Medium
- **Examples**: `NER_LOCATION`, `OLLAMA_LOCATION`

### 8. Credentials & Security
- **Types**: Passwords, PGP Keys
- **Sensitivity**: Very High
- **Examples**: `NER_PASSWORD`, `REGEX_PGPPRV`

### 9. Organizational
- **Types**: Organizations, Dates, Money
- **Sensitivity**: Low
- **Examples**: `OLLAMA_ORGANIZATION`, `OLLAMA_DATE`, `OLLAMA_MONEY`

### 10. Signal Words
- **Types**: Contextual indicators of sensitive data
- **Sensitivity**: Medium (indicates presence of sensitive data)
- **Examples**: `REGEX_WORDS`, `REGEX_SIGNAL_WORDS_EXTENDED`

### 11. Other
- **Types**: Unclassified or unknown types
- **Sensitivity**: Variable
- **Examples**: Any unmatched types

## JSON Output Structure

```json
{
  "metadata": {
    "scan_id": "2024-01-15 10-30-45",
    "start_time": "2024-01-15T10:30:45.123456",
    "end_time": "2024-01-15T11:45:30.654321",
    "duration_seconds": 4485.53,
    "scan_path": "/path/to/scanned/directory",
    "detection_methods": {
      "regex": true,
      "ner": true,
      "spacy_ner": false,
      "pydantic_ai": false
    },
    "total_files_scanned": 1250,
    "total_files_analyzed": 1150,
    "total_matches_found": 3420
  },
  "statistics_by_dimension": {
    "identity": {
      "total_count": 450,
      "by_module": {
        "regex": 320,
        "gliner": 120,
        "spacy-ner": 10
      },
      "by_type": {
        "REGEX_PASSPORT": 45,
        "REGEX_PERSONALAUSWEIS": 78,
        "REGEX_SSN_US": 12,
        "NER_PERSON": 315
      },
      "files_affected": 234,
      "sensitivity_level": "high"
    },
    "contact_information": {
      "total_count": 890,
      "by_module": {
        "regex": 850,
        "gliner": 40
      },
      "by_type": {
        "REGEX_EMAIL": 450,
        "REGEX_PHONE": 320,
        "REGEX_POSTAL_CODE": 80,
        "NER_LOCATION": 40
      },
      "files_affected": 567,
      "sensitivity_level": "medium"
    },
    "financial": {
      "total_count": 234,
      "by_module": {
        "regex": 220,
        "gliner": 14
      },
      "by_type": {
        "REGEX_IBAN": 120,
        "REGEX_BIC": 45,
        "REGEX_CREDIT_CARD": 55,
        "NER_FINANCIAL": 14
      },
      "files_affected": 123,
      "sensitivity_level": "high"
    },
    "health": {
      "total_count": 45,
      "by_module": {
        "gliner": 30,
        "pydantic-ai": 15
      },
      "by_type": {
        "NER_HEALTH": 20,
        "NER_MEDICAL_CONDITION": 15,
        "NER_MEDICATION": 10
      },
      "files_affected": 23,
      "sensitivity_level": "very_high"
    },
    "sensitive_personal_data": {
      "total_count": 12,
      "by_module": {
        "gliner": 8,
        "pydantic-ai": 4
      },
      "by_type": {
        "NER_POLITICAL": 3,
        "NER_RELIGIOUS": 4,
        "NER_SEXUAL_ORIENTATION": 2,
        "NER_ETHNIC_ORIGIN": 2,
        "NER_CRIMINAL_CONVICTION": 1
      },
      "files_affected": 8,
      "sensitivity_level": "very_high"
    }
  },
  "statistics_by_module": {
    "regex": {
      "total_matches": 1434,
      "types_detected": 15,
      "files_processed": 1150,
      "files_with_matches": 890
    },
    "gliner": {
      "total_matches": 1986,
      "types_detected": 12,
      "files_processed": 1150,
      "files_with_matches": 567,
      "avg_confidence": 0.78,
      "confidence_distribution": {
        "0.0-0.5": 120,
        "0.5-0.7": 450,
        "0.7-0.9": 890,
        "0.9-1.0": 526
      }
    }
  },
  "statistics_by_file_type": {
    ".pdf": {
      "files_scanned": 450,
      "files_analyzed": 420,
      "matches_found": 1234,
      "top_dimensions": ["financial", "identity", "contact_information"]
    },
    ".docx": {
      "files_scanned": 320,
      "files_analyzed": 310,
      "matches_found": 890,
      "top_dimensions": ["identity", "contact_information"]
    }
  },
  "summary": {
    "total_matches": 3420,
    "unique_files_with_matches": 890,
    "dimensions_detected": 8,
    "modules_used": 2,
    "highest_risk_dimension": "health",
    "risk_assessment": {
      "very_high_risk_count": 57,
      "high_risk_count": 684,
      "medium_risk_count": 890,
      "low_risk_count": 1789
    }
  },
  "performance_metrics": {
    "files_per_second": 0.26,
    "matches_per_second": 0.76,
    "processing_time_seconds": 4485.53,
    "ner_statistics": {
      "chunks_processed": 3450,
      "entities_found": 1986,
      "avg_time_per_chunk": 0.15,
      "errors": 2
    }
  }
}
```

## Implementation Steps

### Phase 1: Core Infrastructure

1. **Create Privacy Dimension Mapper** (`core/privacy_dimensions.py`)
   - Define dimension mapping dictionary
   - Create function to map detection type to dimension
   - Handle edge cases and unknown types

2. **Extend Statistics Class** (`core/statistics.py`)
   - Add methods for privacy-focused aggregation
   - Track statistics by dimension and module
   - Maintain file-level counts without storing paths

3. **Create Statistics Aggregator** (`core/statistics_aggregator.py`)
   - Process matches and aggregate by dimension/module
   - Calculate distributions and metrics
   - Generate summary statistics

### Phase 2: Output Writer

4. **Create Privacy Statistics Writer** (`core/writers.py`)
   - Implement `PrivacyStatisticsWriter` class
   - Generate JSON output with proper structure
   - Ensure no PII data is included in output

5. **Update Writer Factory** (`core/writers.py`)
   - Add "statistics" format to factory function
   - Integrate with existing writer system

### Phase 3: CLI Integration

6. **Add CLI Options** (`core/cli.py`)
   - Add `--statistics-mode` flag
   - Add `--statistics-output` for custom output path
   - Update help text and documentation

7. **Integrate with Processing Pipeline** (`core/cli.py`)
   - Collect statistics during processing
   - Generate statistics file after scan completion
   - Ensure compatibility with existing output formats

### Phase 4: Testing & Documentation

8. **Unit Tests**
   - Test dimension mapping
   - Test aggregation logic
   - Test JSON output format

9. **Integration Tests**
   - Test end-to-end statistics generation
   - Test with various detection methods
   - Test with different file types

10. **Documentation**
    - Update user guide
    - Add examples
    - Document privacy considerations

## Privacy Considerations

1. **No PII Storage**: Statistics output contains only counts and aggregations, no actual PII text
2. **No File Paths**: File paths are not included in statistics (only counts of affected files)
3. **Anonymized Data**: All data is aggregated and anonymized
4. **Optional Mode**: Statistics mode is optional and separate from detailed findings output
5. **Compliance**: Supports GDPR compliance by minimizing data retention

## Configuration

The statistics mode can be enabled via:

```bash
# Statistics-only mode (no detailed findings)
pii-toolkit scan /path --regex --ner --statistics-mode

# Statistics + detailed findings
pii-toolkit scan /path --regex --ner --format statistics --format csv

# Custom statistics output path
pii-toolkit scan /path --regex --ner --statistics-mode --statistics-output ./stats.json
```

## Future Enhancements

1. **Risk Scoring**: Add risk scoring based on dimension sensitivity
2. **Trend Analysis**: Support for comparing statistics across multiple scans
3. **Visualization**: Generate charts/graphs from statistics
4. **Export Formats**: Support for additional export formats (CSV, Excel)
5. **Filtering**: Allow filtering statistics by dimension or module
6. **Compliance Reports**: Generate GDPR compliance reports from statistics

## Dependencies

- No new external dependencies required
- Uses existing JSON handling from standard library
- Leverages existing statistics infrastructure

## Migration Path

- Backward compatible: Existing functionality unchanged
- Statistics mode is additive feature
- Can be used alongside existing output formats
- No breaking changes to existing APIs
