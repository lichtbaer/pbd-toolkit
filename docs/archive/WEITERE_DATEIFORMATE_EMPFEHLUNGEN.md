# Empfehlungen für weitere Dateiformate

## Aktueller Status

**Bereits implementiert (12 Formate):**
- ✅ PDF, DOCX, HTML, TXT, CSV, JSON, RTF, ODT, EML, XLSX, XLS, XML

## Priorisierte Empfehlungen

### 🔴 Höchste Priorität

#### 1. **MSG (Outlook Email Messages)** - `.msg`
- **Prävalenz**: ⭐⭐⭐⭐ Sehr häufig in E-Mail-bezogenen Datenleaks
- **PII-Gehalt**: ⭐⭐⭐⭐⭐ Extrem hoch - E-Mails enthalten umfangreiche persönliche Informationen
- **Implementierung**: ⭐⭐⭐ Mittel - spezialisierte Bibliothek erforderlich
- **Bibliothek**: `extract-msg` oder `msg-parser`
- **Warum wichtig**: 
  - Microsoft Outlook ist sehr verbreitet in Unternehmen
  - E-Mails enthalten oft: Namen, E-Mail-Adressen, Telefonnummern, Adressen, vertrauliche Informationen
  - Häufig in Datenleaks anzutreffen
- **Aufwand**: ~3-5 Tage
- **Dependency**: `extract-msg` oder `msg-parser`

**Empfehlung**: Als nächstes implementieren - sehr hoher ROI

---

### 🟡 Hohe Priorität

#### 2. **PPTX / PPT (PowerPoint Präsentationen)** - `.pptx`, `.ppt`
- **Prävalenz**: ⭐⭐⭐ Mittel - weniger häufig in Datenleaks, aber relevant
- **PII-Gehalt**: ⭐⭐⭐ Mittel - Präsentationen können persönliche Informationen enthalten
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `python-pptx` (für PPTX), für PPT: `python-pptx` oder `pywin32`
- **Warum wichtig**:
  - Präsentationen können Kundendaten, Projektinformationen, interne Strategien enthalten
  - Sollte Text aus Folien, Notizen und Kommentaren extrahieren
  - Komplettiert die Microsoft Office Suite (Word, Excel, PowerPoint)
- **Aufwand**: ~3-4 Tage
- **Dependency**: `python-pptx`

**Empfehlung**: Gute Ergänzung für vollständige Office-Suite-Abdeckung

#### 3. **ODS (OpenDocument Spreadsheet)** - `.ods`
- **Prävalenz**: ⭐⭐⭐ Mittel - Open-Source-Alternative zu Excel
- **PII-Gehalt**: ⭐⭐⭐⭐ Hoch - ähnlich wie Excel
- **Implementierung**: ⭐⭐⭐ Mittel - ähnlich wie ODT
- **Bibliothek**: `odfpy` (bereits vorhanden für ODT)
- **Warum wichtig**:
  - Wird von LibreOffice/OpenOffice verwendet
  - Ähnlich wie Excel in Bezug auf PII-Gehalt
  - Komplettiert die OpenDocument Suite (ODT, ODS)
- **Aufwand**: ~2-3 Tage (ähnlich wie ODT)
- **Dependency**: `odfpy` (bereits vorhanden!)

**Empfehlung**: Relativ einfach, da Bibliothek bereits vorhanden ist

---

### 🟢 Mittlere Priorität

#### 4. **YAML / YML** - `.yaml`, `.yml`
- **Prävalenz**: ⭐⭐⭐ Mittel - häufig in Konfigurationsdateien und einigen Datenexporten
- **PII-Gehalt**: ⭐⭐⭐ Mittel - kann persönliche Informationen enthalten
- **Implementierung**: ⭐⭐⭐⭐ Einfach
- **Bibliothek**: `PyYAML`
- **Warum wichtig**:
  - Moderne Konfigurationsdateien (Docker, Kubernetes, CI/CD)
  - Kann API-Keys, Credentials, persönliche Daten enthalten
  - Einfach zu implementieren
- **Aufwand**: ~1-2 Tage
- **Dependency**: `PyYAML`

**Empfehlung**: Schneller Win, moderate Relevanz

#### 5. **Markdown** - `.md`, `.markdown`
- **Prävalenz**: ⭐⭐ Niedrig - hauptsächlich Dokumentation
- **PII-Gehalt**: ⭐⭐ Niedrig - hauptsächlich technische Dokumentation
- **Implementierung**: ⭐⭐⭐⭐⭐ Sehr einfach - kann als Text behandelt werden
- **Bibliothek**: Built-in (kann als Text behandelt werden)
- **Warum wichtig**:
  - Kann als einfacher Text-Prozessor behandelt werden
  - Sehr einfach zu implementieren
  - Geringe Relevanz für Datenleaks, aber für Vollständigkeit
- **Aufwand**: ~1 Tag
- **Dependency**: Keine (kann als Text behandelt werden)

**Empfehlung**: Sehr einfach, aber geringe Priorität

---

### ⚪ Niedrige Priorität

#### 6. **EPUB (eBook Format)** - `.epub`
- **Prävalenz**: ⭐⭐ Niedrig - hauptsächlich E-Books
- **PII-Gehalt**: ⭐⭐ Niedrig - hauptsächlich veröffentlichte Inhalte
- **Implementierung**: ⭐⭐⭐ Mittel
- **Bibliothek**: `ebooklib` oder `zipfile` (EPUB ist ZIP-basiert)
- **Warum wichtig**:
  - Weniger relevant für Datenleak-Analysen
  - Könnte für Vollständigkeit nützlich sein
- **Aufwand**: ~2-3 Tage
- **Dependency**: `ebooklib`

**Empfehlung**: Nur wenn Vollständigkeit wichtig ist

---

## Zusammenfassung der Empfehlungen

### Top 3 für sofortige Implementierung:

1. **MSG** (`.msg`) - 🔴 Höchste Priorität
   - Sehr hoher PII-Gehalt
   - Häufig in Datenleaks
   - Moderate Komplexität

2. **PPTX** (`.pptx`, `.ppt`) - 🟡 Hohe Priorität
   - Komplettiert Office-Suite
   - Moderate Relevanz
   - Moderate Komplexität

3. **ODS** (`.ods`) - 🟡 Hohe Priorität
   - Bibliothek bereits vorhanden
   - Ähnlich wie Excel (hoher PII-Gehalt)
   - Relativ einfach

### Schnelle Wins (niedrige Priorität, aber einfach):

4. **YAML** (`.yaml`, `.yml`) - 🟢 Mittlere Priorität
   - Sehr einfach zu implementieren
   - Moderate Relevanz

5. **Markdown** (`.md`) - 🟢 Mittlere Priorität
   - Extrem einfach (kann als Text behandelt werden)
   - Geringe Relevanz für Datenleaks

## Implementierungsreihenfolge (Empfehlung)

1. **MSG** - Höchster ROI, sehr hoher PII-Gehalt
2. **ODS** - Einfach, da Bibliothek vorhanden
3. **PPTX** - Komplettiert Office-Suite
4. **YAML** - Schneller Win
5. **Markdown** - Sehr einfach, aber geringe Priorität
6. **EPUB** - Nur bei Bedarf

## Geschätzter Gesamtaufwand

- **MSG**: ~3-5 Tage
- **ODS**: ~2-3 Tage
- **PPTX**: ~3-4 Tage
- **YAML**: ~1-2 Tage
- **Markdown**: ~1 Tag
- **EPUB**: ~2-3 Tage

**Gesamt für Top 3**: ~8-12 Tage
**Gesamt für alle**: ~12-18 Tage

## Abhängigkeiten

Neue Dependencies, die hinzugefügt werden müssten:

```txt
extract-msg~=0.41.0      # Für MSG
python-pptx~=0.6.23      # Für PPTX
PyYAML~=6.0.1            # Für YAML
ebooklib~=0.18           # Für EPUB (optional)
```

**Hinweis**: `odfpy` ist bereits vorhanden für ODS!

## Fazit

Die **wichtigste Ergänzung** wäre **MSG** (Outlook E-Mails), da:
- Sehr hoher PII-Gehalt
- Häufig in Datenleaks
- Guter ROI

Danach **ODS** und **PPTX** für vollständige Office-Suite-Abdeckung.

Die anderen Formate (YAML, Markdown, EPUB) sind "nice to have", aber nicht kritisch.
