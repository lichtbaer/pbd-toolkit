# Suggested File Formats and Data Protection Dimensions

This document contains suggestions for additional file formats and data protection dimensions that could be added to the PII Toolkit.

## Suggested File Formats

### Archive Formats

#### ZIP (`.zip`)
**Priority**: High  
**Use Case**: Archives often contain sensitive documents. Need to scan contents recursively.

**Implementation Notes**:
- Extract and scan contents recursively
- Handle password-protected archives (report as error or prompt)
- Support nested archives
- Memory-efficient streaming extraction

**Processor**: `ZipProcessor`
- Use `zipfile` standard library
- Extract to temporary directory or stream
- Process each file within archive

#### 7Z (`.7z`)
**Priority**: Medium  
**Use Case**: Common archive format, especially in enterprise environments.

**Implementation Notes**:
- Requires `py7zr` library
- Similar to ZIP processing

#### TAR/GZIP (`.tar`, `.tar.gz`, `.tgz`)
**Priority**: Medium  
**Use Case**: Common on Linux/Unix systems, often used for backups.

**Implementation Notes**:
- Use `tarfile` standard library
- Handle compression (gzip, bzip2, xz)

#### RAR (`.rar`)
**Priority**: Low  
**Use Case**: Less common but still used, especially for large archives.

**Implementation Notes**:
- Requires `rarfile` or `unrar` system tool
- May have licensing considerations

### Database Formats

#### SQLite (`.sqlite`, `.sqlite3`, `.db`)
**Priority**: High  
**Use Case**: Many applications use SQLite for local data storage. May contain PII.

**Implementation Notes**:
- Use `sqlite3` standard library
- Extract text from all tables
- Handle BLOB fields (may contain images/documents)
- Support encrypted databases (report as error)

**Processor**: `SqliteProcessor`
- Query all tables
- Extract string/text columns
- Optionally scan BLOB fields if they contain text

#### CSV with Headers (Enhanced)
**Priority**: Low (already supported, but could be enhanced)  
**Use Case**: Better handling of structured CSV data with column awareness.

**Implementation Notes**:
- Detect column names
- Context-aware scanning (e.g., "Email" column more likely to contain emails)

### Document Formats

#### Markdown (`.md`, `.markdown`)
**Priority**: Medium  
**Use Case**: Documentation, README files, notes often contain PII.

**Implementation Notes**:
- Currently handled by TextProcessor
- Could have dedicated processor to strip markdown syntax more intelligently
- Preserve code blocks separately (may contain sensitive data)

#### EPUB (`.epub`)
**Priority**: Low  
**Use Case**: E-books may contain personal information.

**Implementation Notes**:
- EPUB is essentially a ZIP archive with HTML/XML content
- Extract and process HTML/XML files within

#### FB2 (`.fb2`)
**Priority**: Low  
**Use Case**: FictionBook format, less common.

**Implementation Notes**:
- XML-based format
- Can reuse XML processor logic

### Office Formats (Legacy)

#### DOC (`.doc`) - Microsoft Word 97-2003
**Priority**: High  
**Use Case**: Still common in many organizations, especially older documents.

**Implementation Notes**:
- Requires `python-docx2txt` or `antiword` or `textract`
- More complex than DOCX (binary format)
- May have compatibility issues

#### XLS (`.xls`) - Microsoft Excel 97-2003
**Priority**: High  
**Use Case**: Legacy Excel files still common.

**Implementation Notes**:
- Already partially supported (XlsProcessor exists)
- Verify implementation completeness
- May need `xlrd` library

#### PPT (`.ppt`) - Microsoft PowerPoint 97-2003
**Priority**: Medium  
**Use Case**: Legacy presentations.

**Implementation Notes**:
- Already partially supported (PptProcessor exists)
- Verify implementation completeness
- May need `python-pptx` or alternative

### Email Formats

#### MBOX (`.mbox`)
**Priority**: Medium  
**Use Case**: Unix mailboxes, Thunderbird exports, Gmail exports.

**Implementation Notes**:
- Text-based format with multiple emails
- Parse email boundaries
- Reuse EML processor logic for individual messages

#### PST (`.pst`) - Outlook Personal Storage
**Priority**: Low  
**Use Case**: Outlook data files, often used for email archives.

**Implementation Notes**:
- Binary format, complex
- Requires `libpff` or `pypff` library
- May have licensing considerations
- Very large files common

### Code/Configuration Formats

#### Properties Files (`.properties`)
**Priority**: Medium  
**Use Case**: Configuration files often contain credentials, API keys, database connections.

**Implementation Notes**:
- Simple key-value format
- Can reuse text processor but with context awareness
- Special attention to values (may contain PII)

#### INI Files (`.ini`, `.cfg`, `.conf`)
**Priority**: Medium  
**Use Case**: Configuration files with sensitive data.

**Implementation Notes**:
- Use `configparser` standard library
- Extract values, especially in [database], [api], [auth] sections

#### Environment Files (`.env`)
**Priority**: High  
**Use Case**: Often contain API keys, passwords, secrets.

**Implementation Notes**:
- Simple key-value format
- High priority for security scanning
- May want special handling (e.g., flag all values as potentially sensitive)

### Specialized Formats

#### VCF (`.vcf`) - vCard
**Priority**: High  
**Use Case**: Contact information files, often contain full PII (name, phone, email, address).

**Implementation Notes**:
- Structured contact data
- High PII density
- Use `vobject` library or parse manually

#### iCal (`.ics`, `.ical`)
**Priority**: Medium  
**Use Case**: Calendar files may contain meeting participants, locations, notes.

**Implementation Notes**:
- May contain names, emails, locations
- Use `icalendar` library

#### Log Files (`.log`)
**Priority**: High  
**Use Case**: Application logs often contain PII (user actions, IPs, emails, etc.).

**Implementation Notes**:
- Currently handled by TextProcessor
- Could have dedicated processor with:
  - Timestamp awareness
  - Log level filtering
  - Pattern recognition (e.g., "User logged in: email@example.com")

#### TSV (`.tsv`) - Tab-Separated Values
**Priority**: Low  
**Use Case**: Similar to CSV but tab-separated.

**Implementation Notes**:
- Can reuse CSV processor with different delimiter

### Image Formats (Additional)

#### HEIC/HEIF (`.heic`, `.heif`)
**Priority**: Medium  
**Use Case**: Modern iPhone images, increasingly common.

**Implementation Notes**:
- Requires `pillow-heif` or conversion
- Multimodal detection support

#### RAW Formats (`.raw`, `.cr2`, `.nef`, `.arw`, etc.)
**Priority**: Low  
**Use Case**: Professional photography, less common in document scanning.

**Implementation Notes**:
- Large file sizes
- Multimodal detection support
- May need specialized libraries

### Not Recommended (Low Priority)

- **LaTeX** (`.tex`): Usually code, low PII density
- **Source Code** (`.py`, `.js`, `.java`, etc.): Usually not PII, but could scan comments/strings
- **Binary Executables** (`.exe`, `.bin`): Very difficult, low value
- **Video/Audio**: Very large, complex, low PII density in most cases

## Suggested Data Protection Dimensions

### Regex-Based Dimensions

#### Social Security Numbers (US) - `REGEX_SSN`
**Priority**: High (if US market)  
**Format**: `XXX-XX-XXXX` or `XXXXXXXXX`  
**Pattern**: `\b\d{3}-?\d{2}-?\d{4}\b`  
**Validation**: Area number (first 3 digits) cannot be 000, 666, or 900-999

#### Driver's License Numbers (US) - `REGEX_DRIVERS_LICENSE`
**Priority**: Medium (if US market)  
**Format**: Varies by state, complex  
**Note**: Would need state-specific patterns or generic pattern

#### Passport Numbers - `REGEX_PASSPORT`
**Priority**: High  
**Format**: Varies by country  
**Pattern**: Generic pattern for common formats (e.g., 9 alphanumeric characters)

#### Medical Record Numbers - `REGEX_MRN`
**Priority**: High (Healthcare)  
**Format**: Varies by institution  
**Pattern**: Institution-specific or generic numeric patterns

#### License Plate Numbers - `REGEX_LICENSE_PLATE`
**Priority**: Low  
**Format**: Country-specific  
**Note**: Many false positives, context-dependent

#### MAC Addresses - `REGEX_MAC_ADDRESS`
**Priority**: Medium  
**Format**: `XX:XX:XX:XX:XX:XX` or `XX-XX-XX-XX-XX-XX`  
**Pattern**: `\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b`  
**Use Case**: Network device identification, can be PII in some contexts

#### UUID/GUID - `REGEX_UUID`
**Priority**: Low  
**Format**: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`  
**Note**: Often not PII, but can be used as identifiers

#### API Keys - `REGEX_API_KEY`
**Priority**: High  
**Format**: Varies (often long alphanumeric strings)  
**Pattern**: Context-dependent, look for keywords like "api_key", "apikey", "API_KEY"  
**Examples**: 
- AWS: `AKIA[0-9A-Z]{16}`
- GitHub: `ghp_[a-zA-Z0-9]{36}`
- Generic: Look near keywords

#### JWT Tokens - `REGEX_JWT`
**Priority**: Medium  
**Format**: `eyJ...` (base64-encoded, three parts separated by dots)  
**Pattern**: `\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*\b`  
**Use Case**: Authentication tokens, may contain PII in payload

#### Database Connection Strings - `REGEX_DB_CONNECTION`
**Priority**: High  
**Format**: Various (JDBC, connection strings)  
**Pattern**: Look for patterns like:
- `jdbc:mysql://...`
- `postgresql://user:pass@host:port/db`
- `mongodb://...`
- Often near keywords

#### German Personalausweis (ID Card) Number - `REGEX_PERSONALAUSWEIS`
**Priority**: High (German market)  
**Format**: 9 characters (letters and numbers)  
**Pattern**: `\b[CFGHJKLMNPRTVWXYZ0-9]{9}\b`  
**Note**: First character is always a letter, specific validation rules

#### German Führerschein (Driver's License) Number - `REGEX_FUEHRERSCHEIN`
**Priority**: Medium (German market)  
**Format**: Varies, but often contains birth date  
**Pattern**: Complex, format varies

#### Austrian Social Security Number - `REGEX_AUT_SSN`
**Priority**: Medium (Austrian market)  
**Format**: Specific format with checksum

#### Swiss Social Security Number (AHV) - `REGEX_CH_SSN`
**Priority**: Medium (Swiss market)  
**Format**: Specific format

### AI-NER Dimensions

#### Sexual Orientation - `NER_SEXUAL_ORIENTATION`
**Priority**: High (GDPR Article 9)  
**Relevance**: Special category data under GDPR  
**Use Case**: Detecting mentions of sexual orientation in documents  
**Note**: Sensitive, handle with care

#### Ethnic Origin / Race - `NER_ETHNIC_ORIGIN`
**Priority**: High (GDPR Article 9)  
**Relevance**: Special category data under GDPR  
**Use Case**: Detecting ethnic or racial information

#### Trade Union Membership - `NER_TRADE_UNION`
**Priority**: Medium (GDPR Article 9)  
**Relevance**: Special category data under GDPR  
**Use Case**: Employment-related documents

#### Criminal Convictions - `NER_CRIMINAL_CONVICTION`
**Priority**: High (GDPR Article 10)  
**Relevance**: Special category data under GDPR  
**Use Case**: Background checks, legal documents

#### Financial Information - `NER_FINANCIAL`
**Priority**: High  
**Relevance**: Highly sensitive financial data  
**Use Case**: Bank statements, financial records, income information  
**Note**: More specific than just "money" amounts

#### Medical Conditions - `NER_MEDICAL_CONDITION`
**Priority**: High (GDPR Article 9)  
**Relevance**: Health data, special category  
**Use Case**: Medical records, health insurance documents  
**Note**: More specific than generic "health data"

#### Medication / Prescription - `NER_MEDICATION`
**Priority**: High (GDPR Article 9)  
**Relevance**: Health data  
**Use Case**: Prescription records, medical documents

#### Insurance Policy Numbers - `NER_INSURANCE_POLICY`
**Priority**: Medium  
**Use Case**: Insurance documents

#### Vehicle Identification Number (VIN) - `NER_VIN`
**Priority**: Low  
**Format**: 17 characters  
**Note**: Can be PII if linked to owner

#### IP Address (IPv6) - `NER_IPV6`
**Priority**: Medium  
**Format**: IPv6 addresses  
**Note**: Complement to existing IPv4 detection

#### Username / User ID - `NER_USERNAME`
**Priority**: Medium  
**Use Case**: System usernames, user IDs in applications

#### Age / Date of Birth - `NER_AGE_DOB`
**Priority**: High  
**Use Case**: Detecting age mentions or date of birth in text  
**Note**: Complement to structured date detection

#### Nationality - `NER_NATIONALITY`
**Priority**: Medium  
**Use Case**: Immigration documents, applications

#### Marital Status - `NER_MARITAL_STATUS`
**Priority**: Medium  
**Use Case**: Legal documents, applications

#### Education / Qualifications - `NER_EDUCATION`
**Priority**: Medium  
**Use Case**: CVs, applications, certificates

#### Employment History - `NER_EMPLOYMENT`
**Priority**: Medium  
**Use Case**: CVs, employment records

### Scanner-Specific Recommendations

#### For Regex Engine Only
- Focus on structured, pattern-based data
- Credit card numbers (already implemented)
- Social Security Numbers
- Passport numbers
- API keys (with context)
- Database connection strings

#### For AI-NER Engines (GLiNER, spaCy, Ollama, PydanticAI)
- Focus on unstructured, context-dependent data
- Sexual orientation
- Ethnic origin
- Medical conditions
- Financial information (detailed)
- Employment history
- Education

#### For Multimodal Engines (Images)
- Handwritten text recognition
- Document photos (IDs, passports, driver's licenses)
- Screenshots with PII
- Forms and applications
- Medical records (scanned)

#### Not Recommended for Certain Engines

**Regex - Avoid**:
- Context-dependent concepts (sexual orientation, emotions)
- Unstructured descriptions
- Complex relationships

**AI-NER - Avoid**:
- Highly structured data (better with regex)
- Format-specific patterns (credit cards, IBANs)
- Magic numbers/identifiers without context

## Implementation Priority Matrix

### High Priority (Quick Wins)
1. **ZIP archives** - Common, high value
2. **SQLite databases** - Common, often contains PII
3. **VCF (vCard)** - High PII density
4. **Log files** (enhanced) - Often contain PII
5. **API keys** (regex) - Security critical
6. **Passport numbers** (regex) - High sensitivity
7. **Medical record numbers** (regex) - Healthcare critical

### Medium Priority (Moderate Effort)
1. **MBOX email archives** - Common format
2. **Markdown** (enhanced) - Documentation often has PII
3. **Properties/INI files** - Configuration with secrets
4. **iCal calendars** - Contact information
5. **MAC addresses** (regex) - Network context
6. **JWT tokens** (regex) - Authentication
7. **Sexual orientation** (AI-NER) - GDPR Article 9
8. **Ethnic origin** (AI-NER) - GDPR Article 9
9. **Medical conditions** (AI-NER) - Health data

### Low Priority (Complex or Niche)
1. **PST files** - Complex, licensing issues
2. **RAW images** - Large files, niche use case
3. **License plates** (regex) - Many false positives
4. **UUID** (regex) - Usually not PII
5. **Vehicle VIN** (AI-NER) - Low PII relevance

## Notes on GDPR Compliance

When adding new dimensions, consider:

1. **Article 9 Special Categories**:
   - Racial or ethnic origin
   - Political opinions
   - Religious or philosophical beliefs
   - Trade union membership
   - Genetic data
   - Biometric data (already implemented)
   - Health data (partially implemented)
   - Sex life or sexual orientation
   - Criminal convictions (Article 10)

2. **Sensitivity Levels**:
   - Mark special category data appropriately
   - Consider confidence thresholds
   - Provide clear warnings in documentation

3. **False Positive Handling**:
   - Some dimensions (like sexual orientation) are very sensitive
   - High false positive rates could cause issues
   - Consider making experimental or requiring high confidence

## Testing Considerations

For each new format/dimension:

1. **Test Data**: Create sample files with known PII
2. **False Positives**: Test with non-PII data
3. **Edge Cases**: Empty files, corrupted files, large files
4. **Performance**: Measure impact on processing speed
5. **Documentation**: Update user guides and examples
