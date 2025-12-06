# Privacy-Focused Statistics - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                             │
│                    (core/cli.py)                                 │
│                                                                   │
│  --statistics-mode                                                │
│  --statistics-output <path>                                      │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline                           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Scanner    │→ │   Processor  │→ │   Engines    │          │
│  │              │  │              │  │              │          │
│  │ FileScanner  │  │TextProcessor │  │ - regex      │          │
│  │              │  │              │  │ - gliner      │          │
│  └──────────────┘  └──────────────┘  │ - spacy-ner  │          │
│                                       │ - pydantic-ai│          │
│                                       └──────────────┘          │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         │ PII Matches
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PiiMatchContainer                              │
│                                                                   │
│  - Collects all PII matches                                      │
│  - Stores: text, file, type, score, engine                       │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         │ Match Data
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Statistics Aggregator                               │
│              (core/statistics_aggregator.py)                     │
│                                                                   │
│  ┌──────────────────────────────────────────────┐               │
│  │  Privacy Dimension Mapper                    │               │
│  │  (core/privacy_dimensions.py)                │               │
│  │                                               │               │
│  │  Maps: REGEX_EMAIL → contact_information     │               │
│  │        NER_PERSON → identity                 │               │
│  │        NER_HEALTH → health                   │               │
│  └──────────────────────────────────────────────┘               │
│                                                                   │
│  ┌──────────────────────────────────────────────┐               │
│  │  Aggregation Engine                          │               │
│  │                                               │               │
│  │  - By Dimension (identity, health, etc.)     │               │
│  │  - By Module (regex, gliner, etc.)           │               │
│  │  - By File Type (.pdf, .docx, etc.)          │               │
│  │  - Counts only (no PII text)                 │               │
│  │  - File counts (no paths)                    │               │
│  └──────────────────────────────────────────────┘               │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         │ Aggregated Statistics
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            Privacy Statistics Writer                             │
│            (core/writers.py - PrivacyStatisticsWriter)          │
│                                                                   │
│  - Generates JSON output                                         │
│  - No PII data included                                          │
│  - Only counts and aggregations                                  │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JSON Output File                             │
│                                                                   │
│  {                                                               │
│    "metadata": {...},                                            │
│    "statistics_by_dimension": {...},                            │
│    "statistics_by_module": {...},                               │
│    "statistics_by_file_type": {...},                            │
│    "summary": {...}                                              │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Normal Mode (Current)
```
Scan → Process → Detect PII → Store Matches → Write Detailed Output
                                              (CSV/JSON/XLSX with PII)
```

### Statistics Mode (New)
```
Scan → Process → Detect PII → Aggregate Statistics → Write Statistics JSON
                                                      (Counts only, no PII)
```

### Combined Mode
```
Scan → Process → Detect PII → Store Matches → Write Detailed Output
              │                              (CSV/JSON/XLSX with PII)
              │
              └→ Aggregate Statistics → Write Statistics JSON
                                        (Counts only, no PII)
```

## Component Interactions

### 1. Privacy Dimension Mapper

**File**: `core/privacy_dimensions.py`

**Responsibilities**:
- Map detection types to privacy dimensions
- Provide sensitivity levels
- Handle unknown/unmapped types

**Interface**:
```python
def get_dimension(detection_type: str) -> str:
    """Map detection type to privacy dimension."""
    pass

def get_sensitivity_level(dimension: str) -> str:
    """Get sensitivity level for dimension."""
    pass
```

### 2. Statistics Aggregator

**File**: `core/statistics_aggregator.py`

**Responsibilities**:
- Process matches and aggregate by dimension/module
- Calculate distributions and metrics
- Generate summary statistics
- Track file-level counts (without paths)

**Interface**:
```python
class StatisticsAggregator:
    def add_match(self, match: PiiMatch) -> None:
        """Add a match to aggregation."""
        pass
    
    def get_statistics(self) -> dict:
        """Get aggregated statistics."""
        pass
```

### 3. Privacy Statistics Writer

**File**: `core/writers.py`

**Responsibilities**:
- Generate JSON output with aggregated statistics
- Ensure no PII data is included
- Format output according to schema

**Interface**:
```python
class PrivacyStatisticsWriter(OutputWriter):
    def write_statistics(self, statistics: dict, metadata: dict) -> None:
        """Write statistics to JSON file."""
        pass
```

## Privacy Protection Mechanisms

### 1. Data Minimization
- **No PII Text**: Only counts are stored, never actual PII content
- **No File Paths**: File paths are not included, only counts of affected files
- **Aggregation Only**: All data is aggregated at dimension/module level

### 2. Anonymization
- **No Identifiers**: No way to link statistics back to individuals
- **Grouped Data**: Data is grouped into privacy dimensions
- **Summary Level**: Only summary statistics, no individual records

### 3. Optional Mode
- **Separate Output**: Statistics mode is separate from detailed findings
- **User Choice**: Users can choose to use statistics mode only
- **Compliance Support**: Enables GDPR-compliant analysis workflows

## Integration Points

### 1. CLI Integration
- Add `--statistics-mode` flag to `core/cli.py`
- Add `--statistics-output` option for custom output path
- Integrate with existing output format system

### 2. Statistics Integration
- Extend `core/statistics.py` with aggregation methods
- Integrate with existing statistics tracking
- Maintain backward compatibility

### 3. Writer Integration
- Add `PrivacyStatisticsWriter` to `core/writers.py`
- Update factory function to support "statistics" format
- Ensure compatibility with existing writer system

## File Structure

```
core/
├── privacy_dimensions.py          # NEW: Dimension mapping
├── statistics_aggregator.py       # NEW: Aggregation logic
├── statistics.py                  # MODIFIED: Add aggregation methods
├── writers.py                     # MODIFIED: Add PrivacyStatisticsWriter
└── cli.py                         # MODIFIED: Add statistics mode options
```

## Example Usage Flow

1. **User runs scan with statistics mode**:
   ```bash
   pii-toolkit scan /data --regex --ner --statistics-mode
   ```

2. **System processes files**:
   - Scanner finds files
   - Processor extracts text
   - Engines detect PII
   - Matches collected in PiiMatchContainer

3. **Statistics aggregation**:
   - StatisticsAggregator processes matches
   - PrivacyDimensionMapper maps types to dimensions
   - Statistics aggregated by dimension/module/file type

4. **Output generation**:
   - PrivacyStatisticsWriter generates JSON
   - No PII data included
   - Only counts and aggregations

5. **Result**:
   - JSON file with privacy-focused statistics
   - No person-related data exposed
   - Suitable for compliance reporting

## Benefits

1. **Privacy**: No PII data in statistics output
2. **Compliance**: Supports GDPR/privacy compliance
3. **Analysis**: Enables statistical analysis without data exposure
4. **Flexibility**: Can be used alongside or instead of detailed output
5. **Performance**: Lighter output, faster processing
6. **Scalability**: Works with large datasets without storage concerns
