# File Format Implementation Priorities

## Quick Reference: Top 5 Recommendations

| Format | Priority | Effort | Impact | Library | Notes |
|--------|----------|--------|--------|---------|-------|
| **CSV** | 🔴 Critical | ⭐ Very Low | ⭐⭐⭐⭐⭐ Very High | Built-in `csv` | Extremely common in data leaks |
| **JSON** | 🔴 Critical | ⭐ Very Low | ⭐⭐⭐⭐⭐ Very High | Built-in `json` | Very common in modern leaks/APIs |
| **XLSX/XLS** | 🔴 Critical | ⭐⭐⭐ Medium | ⭐⭐⭐⭐⭐ Very High | `openpyxl`, `xlrd` | Extremely high PII content |
| **RTF** | 🟡 High | ⭐⭐ Low | ⭐⭐⭐⭐ High | `striprtf` | Common document format |
| **EML** | 🟡 High | ⭐⭐ Low | ⭐⭐⭐⭐⭐ Very High | Built-in `email` | Standard email format |

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 days each)
- ✅ **CSV** - Use built-in `csv` module, handle different delimiters/encodings
- ✅ **JSON** - Use built-in `json` module, extract all string values recursively

### Phase 2: High Value (2-3 days each)
- ✅ **XLSX** - Use `openpyxl`, extract all cells from all sheets
- ✅ **RTF** - Use `striprtf`, extract plain text
- ✅ **EML** - Use built-in `email` module, extract headers and body

### Phase 3: Specialized (3-5 days each)
- ⚠️ **MSG** - Use `extract-msg`, handle Outlook-specific format
- ⚠️ **ODT** - Use `odfpy`, similar to DOCX structure
- ⚠️ **XML** - Use `xml.etree.ElementTree`, handle large files with streaming

### Phase 4: Completeness (2-4 days each)
- ⚠️ **ODS** - Use `odfpy`, similar to Excel
- ⚠️ **PPTX** - Use `python-pptx`, extract slides/notes
- ⚠️ **YAML** - Use `PyYAML`, extract string values

## Estimated Total Impact

**Phase 1 + 2** (5 formats):
- Coverage increase: ~40-50% of additional file types in typical data leaks
- Implementation time: ~10-15 days
- Dependencies: +3 packages (openpyxl, striprtf, xlrd)

**All Phases** (10 formats):
- Coverage increase: ~60-70% of additional file types
- Implementation time: ~25-35 days
- Dependencies: +7 packages

## Recommended Starting Point

Start with **CSV** and **JSON** as they:
1. Are extremely common in data leaks
2. Require minimal implementation effort
3. Have no external dependencies (use built-in modules)
4. Provide immediate high value

Then proceed with **XLSX** for maximum PII detection coverage.
