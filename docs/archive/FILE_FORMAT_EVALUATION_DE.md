# Evaluierung zusätzlicher Dateiformate für PII-Erkennung

## Aktueller Status

Das Toolkit unterstützt derzeit folgende Dateiformate:
- `.pdf` - PDF-Dokumente
- `.docx` - Microsoft Word-Dokumente
- `.html` / `.htm` - HTML-Dateien
- `.txt` - Plain-Text-Dateien (inkl. Dateien ohne Endung mit MIME-Type "text/plain")

## Evaluierungskriterien

Bei der Bewertung neuer Dateiformate werden folgende Kriterien berücksichtigt:
1. **Häufigkeit in Datenleaks** - Wie häufig sind diese Formate in geleakten Daten?
2. **PII-Wahrscheinlichkeit** - Wie wahrscheinlich enthalten diese Formate personenbezogene Daten?
3. **Implementierungskomplexität** - Wie schwierig ist die Textextraktion?
4. **Bibliotheksverfügbarkeit** - Gibt es zuverlässige Python-Bibliotheken?
5. **Dateigröße** - Können diese Dateien effizient verarbeitet werden?

## Empfohlene Dateiformate (nach Priorität)

### Höchste Priorität

#### 1. **XLSX / XLS (Excel-Tabellen)**
- **Häufigkeit**: ⭐⭐⭐⭐⭐ Sehr häufig in Geschäftskontexten und Datenleaks
- **PII-Gehalt**: ⭐⭐⭐⭐⭐ Extrem hoch - Tabellen enthalten oft Datenbanken mit persönlichen Informationen
- **Implementierung**: ⭐⭐⭐⭐ Mittel - etablierte Bibliotheken verfügbar
- **Bibliothek**: `openpyxl` (für XLSX), `xlrd` (für XLS, älteres Format)
- **Hinweise**: 
  - Excel-Dateien enthalten häufig strukturierte persönliche Daten (Namen, Adressen, Telefonnummern, etc.)
  - Sollte Text aus allen Zellen extrahieren, inklusive mehrerer Tabellenblätter
  - Formeln berücksichtigen (berechnete Werte extrahieren, nicht die Formeln selbst)

#### 2. **CSV (Comma-Separated Values)**
- **Häufigkeit**: ⭐⭐⭐⭐⭐ Extrem häufig in Datenexporten und Leaks
- **PII-Gehalt**: ⭐⭐⭐⭐⭐ Sehr hoch - strukturiertes Datenformat, oft für persönliche Informationsdatenbanken verwendet
- **Implementierung**: ⭐⭐⭐⭐⭐ Sehr einfach - Pythons eingebautes `csv` Modul
- **Bibliothek**: Eingebautes `csv` Modul
- **Hinweise**:
  - Sehr häufiges Format für Daten-Dumps
  - Sollte verschiedene Trennzeichen handhaben (Komma, Semikolon, Tab)
  - Sollte verschiedene Encodings handhaben
  - Möglicherweise Anführungszeichen und Escape-Sequenzen berücksichtigen

#### 3. **RTF (Rich Text Format)**
- **Häufigkeit**: ⭐⭐⭐⭐ Häufig, besonders in älteren Dokumenten
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - Dokumentformat ähnlich DOCX
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `striprtf` oder `pyth` (RTF-Parser)
- **Hinweise**:
  - Älteres Format, aber noch weit verbreitet
  - Ähnlicher Inhalt wie DOCX-Dateien
  - Textextraktion ist unkompliziert

#### 4. **ODT (OpenDocument Text)**
- **Häufigkeit**: ⭐⭐⭐ Mittel - Open-Source-Alternative zu DOCX
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - ähnlich DOCX
- **Implementierung**: ⭐⭐⭐⭐ Einfach - ähnliche Struktur wie DOCX
- **Bibliothek**: `odfpy` oder `python-odf`
- **Hinweise**:
  - OpenDocument-Format (verwendet von LibreOffice, OpenOffice)
  - Ähnliche Struktur wie DOCX (ZIP-basiertes XML)
  - Sollte Text aus Absätzen, Kopf-/Fußzeilen, Tabellen extrahieren

#### 5. **MSG (Outlook E-Mail-Nachrichten)**
- **Häufigkeit**: ⭐⭐⭐⭐ Häufig in E-Mail-bezogenen Datenleaks
- **PII-Gehalt**: ⭐⭐⭐⭐⭐ Sehr hoch - E-Mails enthalten umfangreiche persönliche Informationen
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `extract-msg` oder `msg-parser`
- **Hinweise**:
  - Microsoft Outlook E-Mail-Format
  - Sollte extrahieren: Betreff, Body, Absender, Empfänger, Anhang-Metadaten
  - Kann eingebettete Anhänge enthalten (könnten separat verarbeitet werden)

#### 6. **EML (E-Mail-Nachrichtendateien)**
- **Häufigkeit**: ⭐⭐⭐⭐ Häufig in E-Mail-Exporten
- **PII-Gehalt**: ⭐⭐⭐⭐⭐ Sehr hoch - Standard-E-Mail-Format
- **Implementierung**: ⭐⭐⭐⭐ Einfach - Standard-E-Mail-Format
- **Bibliothek**: Eingebautes `email` Modul
- **Hinweise**:
  - Standard-E-Mail-Format (RFC 822)
  - Kann Pythons eingebautes `email` Modul verwenden
  - Sollte extrahieren: Header, Body (Plain-Text und HTML-Teile)

#### 7. **JSON (JavaScript Object Notation)**
- **Häufigkeit**: ⭐⭐⭐⭐⭐ Sehr häufig in modernen Datenleaks und API-Dumps
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - strukturierte Daten enthalten oft persönliche Informationen
- **Implementierung**: ⭐⭐⭐⭐⭐ Sehr einfach - eingebautes `json` Modul
- **Bibliothek**: Eingebautes `json` Modul
- **Hinweise**:
  - Sehr häufig in API-Antworten und modernen Datenformaten
  - Sollte alle String-Werte extrahieren (Schlüssel und Werte)
  - Möglicherweise verschachtelte Strukturen handhaben
  - Große JSON-Dateien effizient verarbeiten

### Mittlere Priorität

#### 8. **XML (eXtensible Markup Language)**
- **Häufigkeit**: ⭐⭐⭐⭐ Häufig in strukturierten Datenexporten
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - strukturiertes Format, oft für persönliche Daten verwendet
- **Implementierung**: ⭐⭐⭐⭐ Einfach - eingebautes `xml.etree.ElementTree`
- **Bibliothek**: Eingebautes `xml.etree.ElementTree` oder `lxml`
- **Hinweise**:
  - Sollte Text aus allen Elementen und Attributen extrahieren
  - Möglicherweise Namespaces handhaben
  - Große XML-Dateien berücksichtigen (Streaming-Parser)

#### 9. **PPTX / PPT (PowerPoint-Präsentationen)**
- **Häufigkeit**: ⭐⭐⭐ Mittel - weniger häufig in Datenleaks, aber dennoch relevant
- **PII-Gehalt**: ⭐⭐⭐ Mittel - Präsentationen können persönliche Informationen enthalten
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `python-pptx` (für PPTX), `python-pptx` oder `pywin32` (für PPT)
- **Hinweise**:
  - Sollte Text aus Folien, Notizen und Kommentaren extrahieren
  - Weniger kritisch als Word/Excel, aber dennoch nützlich

#### 10. **ODS (OpenDocument Spreadsheet)**
- **Häufigkeit**: ⭐⭐⭐ Mittel - Open-Source-Alternative zu Excel
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - ähnlich Excel
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `odfpy` oder `ezodf`
- **Hinweise**:
  - OpenDocument-Tabellenformat
  - Ähnlich Excel in Bezug auf PII-Gehalt

#### 11. **YAML / YML**
- **Häufigkeit**: ⭐⭐⭐ Mittel - häufig in Konfigurationsdateien und einigen Datenexporten
- **PII-Gehalt**: ⭐⭐⭐ Mittel - kann persönliche Informationen enthalten
- **Implementierung**: ⭐⭐⭐⭐ Einfach
- **Bibliothek**: `PyYAML`
- **Hinweise**:
  - Sollte alle String-Werte extrahieren
  - Weniger häufig in Datenleaks, aber dennoch nützlich

### Niedrigere Priorität

#### 12. **Markdown (.md, .markdown)**
- **Häufigkeit**: ⭐⭐ Niedrig - hauptsächlich Dokumentation
- **PII-Gehalt**: ⭐⭐ Niedrig - hauptsächlich technische Dokumentation
- **Implementierung**: ⭐⭐⭐⭐⭐ Sehr einfach - hauptsächlich Plain-Text
- **Bibliothek**: Eingebaut (kann als Text behandelt werden) oder `markdown` für strukturierte Extraktion
- **Hinweise**:
  - Kann größtenteils als Plain-Text behandelt werden
  - Weniger wahrscheinlich PII in Datenleaks zu enthalten

#### 13. **EPUB (eBook-Format)**
- **Häufigkeit**: ⭐⭐ Niedrig - hauptsächlich E-Books
- **PII-Gehalt**: ⭐⭐ Niedrig - hauptsächlich veröffentlichte Inhalte
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `ebooklib` oder `zipfile` (EPUB ist ZIP-basiert)
- **Hinweise**:
  - Weniger relevant für Datenleak-Analysen
  - Könnte für Vollständigkeit nützlich sein

## Implementierungsempfehlungen

### Phase 1 (Sofortiger hoher Wert)
1. **CSV** - Sehr einfach zu implementieren, extrem häufig
2. **JSON** - Sehr einfach zu implementieren, sehr häufig in modernen Datenleaks
3. **XLSX** - Hoher Wert, mittlere Komplexität

### Phase 2 (Hoher Wert, mittlere Komplexität)
4. **RTF** - Häufiges Format, mittlere Komplexität
5. **ODT** - Ähnlich DOCX, gute Abdeckung
6. **EML** - Häufiges E-Mail-Format, einfach zu implementieren

### Phase 3 (Spezialisierte Formate)
7. **MSG** - E-Mail-Format, erfordert spezialisierte Bibliothek
8. **XML** - Strukturierte Daten, sollte große Dateien handhaben
9. **PPTX** - Niedrigere Priorität, aber dennoch nützlich

### Phase 4 (Vollständigkeit)
10. **ODS** - Open-Source-Tabellenformat
11. **YAML** - Konfigurations-/Datenformat
12. **Markdown** - Kann als Text behandelt werden
13. **EPUB** - Niedrigere Priorität

## Technische Überlegungen

### Bibliotheksabhängigkeiten
Neue Formate erfordern zusätzliche Abhängigkeiten. Zu berücksichtigen:
- **openpyxl** - Für XLSX-Dateien
- **xlrd** - Für ältere XLS-Dateien (Hinweis: xlrd 2.0+ unterstützt nur .xls, nicht .xlsx)
- **striprtf** oder **pyth** - Für RTF-Dateien
- **odfpy** oder **python-odf** - Für ODT/ODS-Dateien
- **extract-msg** oder **msg-parser** - Für MSG-Dateien
- **PyYAML** - Für YAML-Dateien
- **python-pptx** - Für PPTX-Dateien

### Performance-Überlegungen
- Einige Formate (besonders Tabellen) können sehr groß sein
- Streaming/Chunk-Verarbeitung für große Dateien in Betracht ziehen
- CSV- und JSON-Dateien können sehr groß sein - möglicherweise spezielle Behandlung erforderlich
- XML-Dateien benötigen möglicherweise Streaming-Parser für große Dateien

### Fehlerbehandlung
- Einige Formate können beschädigt oder passwortgeschützt sein
- Encoding-Probleme sollten elegant behandelt werden
- Nicht unterstützte oder problematische Dateien sollten protokolliert werden

## Zusammenfassung

Die wertvollsten Ergänzungen wären:
1. **CSV** - Einfach, extrem häufig, hoher PII-Gehalt
2. **JSON** - Einfach, sehr häufig in modernen Leaks, hoher PII-Gehalt
3. **XLSX/XLS** - Mittlere Komplexität, sehr häufig, extrem hoher PII-Gehalt
4. **RTF** - Mittlere Komplexität, häufig, hoher PII-Gehalt
5. **EML/MSG** - E-Mail-Formate, hoher PII-Gehalt

Diese fünf Formate würden die Abdeckung des Toolkits für häufige Datenleak-Szenarien erheblich erweitern und dabei eine angemessene Implementierungskomplexität beibehalten.
