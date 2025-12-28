# Whitelist Usage

The whitelist feature allows you to exclude known false positives from the analysis results.

## Overview

A whitelist is a text file containing exclusion patterns. Any finding that contains one of these patterns will be excluded from the output.

## Creating a Whitelist File

Create a plain text file with one pattern per line:

```
info@
noreply@
example.com
test@example
do-not-reply
```

**Important**: Patterns are matched as substrings. If a finding contains the pattern anywhere, it will be excluded.

## Usage

Specify the whitelist file with the `--whitelist` option:

```bash
python main.py scan /data --regex --whitelist stopwords.txt
```

## Common Use Cases

### Excluding System Email Addresses

```
info@
noreply@
no-reply@
donotreply@
system@
automated@
```

### Excluding Test Data

```
test@example.com
example.com
sample@
dummy@
```

### Excluding Public Domains

```
example.com
test.com
localhost
127.0.0.1
```

### Excluding Specific Patterns

```
info@company.com
support@company.com
```

## Pattern Matching

The whitelist uses substring matching:

- `info@` matches: `info@example.com`, `user-info@test.com`
- `example.com` matches: `user@example.com`, `admin@sub.example.com`
- `test` matches: `test@example.com`, `testuser@domain.com`

**Case sensitivity**: Matching is case-sensitive.

## Best Practices

1. **Start small**: Begin with a few common patterns and expand as needed
2. **Be specific**: Use specific patterns to avoid excluding legitimate findings
3. **Test patterns**: Verify that patterns work as expected
4. **Document patterns**: Maintain a separate documentation file (comments inside the whitelist file are not supported)
5. **Regular updates**: Review and update whitelist based on false positive analysis

## Examples

### Basic Whitelist

`whitelist.txt`:
```
info@
noreply@
example.com
```

Usage:
```bash
python main.py scan /data --regex --whitelist whitelist.txt
```

### Comprehensive Whitelist

`comprehensive_whitelist.txt`:
```
info@
noreply@
no-reply@
donotreply@
system@
automated@

example.com
test.com
localhost

info@company.com
support@company.com
```

Usage:
```bash
python main.py scan /data --regex --ner --whitelist comprehensive_whitelist.txt
```

## Performance Impact

Whitelist filtering is performed during processing and has minimal performance impact. Patterns are pre-compiled for efficiency.

## Limitations

- **Substring matching only**: Cannot use regex patterns
- **Case-sensitive**: Matching is case-sensitive
- **No wildcards**: Cannot use wildcard patterns like `*@example.com`
- **All matches excluded**: If a finding matches any pattern, it's excluded entirely

## Troubleshooting

### Too Many Findings Excluded

- Review whitelist patterns
- Make patterns more specific
- Check for overly broad patterns

### Too Few Findings Excluded

- Add more patterns
- Check pattern spelling
- Verify case sensitivity

### Pattern Not Working

- Check file path is correct
- Verify file encoding (UTF-8 recommended)
- Ensure pattern is on its own line
- Check for trailing whitespace
