Supported match types are controlled by the file config_types.json.
This file contains a json object with two keys: "regex" for all match types based on regular expressions and "ai-ner" for all
match types supported by AI-based Named Entity Recognition.

The key "regex" holds a list of objects with the following keys supported:
* "label": an internal descriptor for the type of finding
* "value": a descriptive value for the type of finding, e. g. rendered in the csv output
* "regex_compiled_pos": an integer that is incremented from 0 and used for enumeration the regex based match types
* "expression": the regular expression used for matching

Example:
```json
{
    "label": "REGEX_RVNR",
    "value": "Regex: Pension Insurance Fond ID",
    "regex_compiled_pos": 0,
    "expression": "\\b[0-8][0-9][0-3][0-9][0-1][0-9]{3}[A-Z][0-9]{3}\\b"            
}
```

The default regex match types supported are as follows:

```python
""" Regular expression for German Rentenversicherungsnummern (public pension insurance identity number).
    It consists of:
      * Word boundary
      * Two digits identifying the insurance provider, zero-padded (value range of [02, 89])
      * Day of birth of the insured person, zero-padded (value range of [01, 31])
      * Month of birth of the insured person, zero-padded (value range of [01, 12])
      * Year of birth of the insured person, last two digits (value range of [00, 99])
      * First letter of the insured person's first name (value range of [A, Z])
      * Two digits identifying the insured person's gender, zero-padded (value range of [00, 99])
      * One digit for integrity checking (value range of [0, 9])
      * Word boundary
    Example: 15070649C103 """
rxstr_rvnr: str = r"\b[0-8][0-9][0-3][0-9][0-1][0-9]{3}[A-Z][0-9]{3}\b"
""" Regular expression for IBAN banking account numbers. This is somewhat specific (but not absolutely exclusive)
    for German banking accounts.
    Consists of:
      * Word boundary
      * Two letters identifying the country
      * Two digits for integrity checking
      * Four sets of four digits which may optionally be separated by spaces from each other
        and other elements
      * One or two digits
      * Word boundary
    Example: DE11 2003 8978 4565 1232 00"""
rxstr_iban: str = r"\b[A-Z]{2}[0-9]{2}(?:[ ]?[0-9]{4}){4}(?:[ ]?[0-9]{1,2})?\b"
""" Regular expression for email addresses. Doesn't conform to the RFC and thus doesn't cover every single
    possible valid address but is intended as a "good enough" solution.
    Consists of:
      * Word boundary
      * A non-zero amount of word characters or dashes (-) or dots (.)
      * An at character (@)
      * A non-zero amount of word characters or dashes or dots which ends with one dot
      * Two to ten word characters
      * Word boundary
    Example: test@example.com """
rxstr_mail: str = r"\b[\w\-\.]+@(?:[\w+\-]+\.)+\w{2,10}\b"
""" Regular expression for IPv4 addresses
    Consists of:
      * Word boundary
      * Four groups of one to three digits in the range of [0, 255] which may optionally
        be zero-padded to three digits
      * Word boundary
    Example: 123.123.123.123 """
rxstr_ipv4: str = r"\b(?:(?:25[0-5]|(?:2[0-4]|1\d|[1-9]|)\d)\.?\b){4}\b"
""" Regular expression for special words that frequently appear in the context of
    personally-identifiable information """
rxstr_words: str = r"\b(?:Abmahnung|Bewerbung|Zeugnis|Entwicklungsbericht|Gutachten|Krankmeldung)\b"
rxstr_pgpprv: str = r"(?:BEGIN PGP PRIVATE KEY)"
```

The key "ai-ner" holds a list of objects with the following keys supported:
* "label": an internal descriptor for the type of finding
* "value": a descriptive value for the type of finding, e. g. rendered in the csv output
* "term": the term used for matching by the AI NER model used

Example:
```json
{
    "label": "NER_PERSON",
    "value": "AI-NER: Person",
    "term": "Person's Name"
}
```
