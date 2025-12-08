# Bandit Security Analysis Report

**Date:** 2025-12-08  
**Tool:** Bandit 1.9.2  
**Total Issues Found:** 518

## Summary

- **High Severity:** 0
- **Medium Severity:** 3
- **Low Severity:** 515

## Critical Issues (Medium Severity)

### 1. B310: Unsafe URL Open (check_licenses.py:72)
**Severity:** Medium | **Confidence:** High | **CWE:** CWE-22

**Location:** `./check_licenses.py:72:13`

```python
url = f"https://pypi.org/pypi/{package_name}/json"
with urllib.request.urlopen(url, timeout=10) as response:
    data = json.loads(response.read())
```

**Issue:** `urllib.request.urlopen` allows file:/ or custom schemes which can be unexpected and potentially dangerous.

**Recommendation:** Validate the URL scheme before opening, or use a whitelist of allowed schemes.

---

### 2. B608: Potential SQL Injection (sqlite_processor.py:66)
**Severity:** Medium | **Confidence:** Medium | **CWE:** CWE-89

**Location:** `./file_processors/sqlite_processor.py:66:41`

```python
columns_str = ", ".join(text_columns)
cursor.execute(f"SELECT {columns_str} FROM {table_name}")
```

**Issue:** String-based query construction can be vulnerable to SQL injection if `table_name` or `text_columns` contain user-controlled data.

**Recommendation:** 
- Validate `table_name` against a whitelist of allowed table names
- Ensure `text_columns` are validated or use parameterized queries where possible
- Note: Since this is processing SQLite files (not user input), the risk is lower, but validation is still recommended

---

### 3. B314: XML External Entity (XXE) Vulnerability (xml_processor.py:39)
**Severity:** Medium | **Confidence:** High | **CWE:** CWE-20

**Location:** `./file_processors/xml_processor.py:39:19`

```python
tree = ET.parse(file_path)
```

**Issue:** `xml.etree.ElementTree.parse` is vulnerable to XML attacks including XXE (XML External Entity) attacks when parsing untrusted XML data.

**Recommendation:** 
- Replace with `defusedxml.ElementTree.parse()` from the `defusedxml` package
- Or call `defusedxml.defuse_stdlib()` at application startup

---

## Low Severity Issues

### B101: Assert Used (499 occurrences)
**Severity:** Low | **Confidence:** High

Mostly in test files (`tests/`). Asserts are removed when Python is run with `-O` optimization flag.

**Recommendation:** Use proper test assertions (e.g., `unittest.assert*`) instead of bare `assert` statements in tests.

**Files with most occurrences:**
- `./tests/test_file_processors.py`: 133
- `./tests/test_statistics.py`: 59
- `./tests/test_privacy_dimensions.py`: 42

---

### B110: Try/Except/Pass (12 occurrences)
**Severity:** Low | **Confidence:** High | **CWE:** CWE-703

Silent exception handling can hide errors.

**Files affected:**
- `core/file_type_detector.py`: 3 occurrences
- `file_processors/ical_processor.py`: 1 occurrence
- `file_processors/mbox_processor.py`: 5 occurrences
- `file_processors/sqlite_processor.py`: 1 occurrence
- `file_processors/vcf_processor.py`: 1 occurrence

**Recommendation:** Log exceptions or handle them more specifically rather than silently passing.

---

### B112: Try/Except/Continue (3 occurrences)
**Severity:** Low | **Confidence:** High | **CWE:** CWE-703

Similar to B110, but with `continue` instead of `pass`.

**Files affected:**
- `file_processors/sqlite_processor.py`: 1 occurrence
- `file_processors/zip_processor.py`: 2 occurrences

**Recommendation:** Log exceptions before continuing to aid debugging.

---

### B405: XML Import (1 occurrence)
**Severity:** Low | **Confidence:** High | **CWE:** CWE-20

**Location:** `./file_processors/xml_processor.py:3:0`

```python
import xml.etree.ElementTree as ET
```

**Issue:** Using `xml.etree.ElementTree` for untrusted XML data is vulnerable to XML attacks.

**Recommendation:** Use `defusedxml` package instead (related to B314 above).

---

## Recommendations

### Immediate Actions (Medium Severity)

1. **Fix XML parsing vulnerability:**
   - Install `defusedxml`: `pip install defusedxml`
   - Replace `xml.etree.ElementTree` with `defusedxml.ElementTree` in `xml_processor.py`

2. **Validate SQL query construction:**
   - Add validation for `table_name` in `sqlite_processor.py`
   - Ensure table names come from a safe source (e.g., `sqlite_master` query results)

3. **Secure URL opening:**
   - Validate URL scheme in `check_licenses.py` to only allow `https://`

### Code Quality Improvements (Low Severity)

1. **Replace assert statements in tests:**
   - Use `unittest.TestCase.assert*` methods or pytest assertions

2. **Improve exception handling:**
   - Add logging for exceptions that are currently silently passed
   - Use more specific exception types where possible

---

## Files Scanned

- Total lines of code: 8,291
- Total lines skipped (#nosec): 0
- Files analyzed: All Python files in the project

---

## Notes

- Most Low severity issues are in test files and are acceptable for test code
- The Medium severity issues should be addressed, especially the XML parsing vulnerability
- The SQL injection risk is mitigated by the fact that SQLite files are being processed (not user input), but validation is still recommended
