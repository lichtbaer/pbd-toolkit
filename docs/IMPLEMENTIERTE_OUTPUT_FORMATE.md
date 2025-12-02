# Implementierte Output-Formate

## Übersicht

Es wurden zwei zusätzliche Output-Formate implementiert:
- **JSON** - Strukturiertes JSON-Format mit Metadaten
- **XLSX** - Excel-Tabellenformat

Das CSV-Format bleibt Standard und ist weiterhin rückwärtskompatibel.

## Implementierte Features

### 1. `--format` Option

Neue CLI-Option zur Auswahl des Output-Formats:
- `--format csv` (Standard)
- `--format json`
- `--format xlsx`

**Beispiel**:
```bash
python main.py --path /data --regex --format json
python main.py --path /data --regex --format xlsx
```

### 2. JSON-Format

**Features**:
- Strukturierte Daten mit vollständigen Metadaten
- Enthält Statistiken, Fehlerinformationen und Dateiendungen
- Alle Treffer in einem `findings` Array
- Fehler gruppiert nach Typ
- UTF-8 Encoding mit Unicode-Unterstützung
- Pretty-printed mit 2-Space-Einrückung

**Struktur**:
```json
{
  "metadata": { ... },
  "statistics": { ... },
  "file_extensions": { ... },
  "findings": [ ... ],
  "errors": [ ... ]
}
```

### 3. Excel-Format (XLSX)

**Features**:
- Professionelle Formatierung mit gestylten Headern
- Automatisch angepasste Spaltenbreiten
- Kompatibel mit Microsoft Excel, LibreOffice Calc, Google Sheets
- UTF-8 Encoding-Unterstützung
- Fallback zu CSV, falls `openpyxl` nicht installiert ist

**Formatierung**:
- Header-Zeile: Blauer Hintergrund, weiße fette Schrift
- Spalten: Auto-angepasste Breiten (max. 100 Zeichen)
- Spalten: Match, File, Type, NER Score

## Geänderte Dateien

### `setup.py`
- `--format` Option hinzugefügt (csv, json, xlsx)
- Output-Datei-Pfad wird basierend auf Format gesetzt
- Für JSON/XLSX werden keine CSV-Writer erstellt

### `main.py`
- Output-Format wird an `PiiMatchContainer` übergeben
- JSON-Output wird am Ende geschrieben (alle Matches gesammelt)
- Excel-Output wird am Ende geschrieben (alle Matches gesammelt)
- Fallback zu CSV, falls `openpyxl` fehlt
- Zusammenfassung zeigt korrekten Dateinamen an

### `matches.py`
- `set_output_format()` Methode hinzugefügt
- Direktes Schreiben nur für CSV-Format
- Für JSON/XLSX werden Matches nur gesammelt

### `globals.py`
- `output_format` Variable hinzugefügt
- `output_file_path` Variable hinzugefügt

### `requirements.txt`
- `openpyxl~=3.1.0` hinzugefügt (für Excel-Support)

## Technische Details

### CSV-Format (unverändert)
- Wird inkrementell während der Verarbeitung geschrieben
- Header wird am Anfang geschrieben (außer mit `--no-header`)
- Jeder Treffer wird sofort geschrieben
- Datei bleibt während der gesamten Analyse geöffnet

### JSON-Format
- Matches werden im Speicher gesammelt
- Komplette JSON-Struktur wird am Ende geschrieben
- Enthält Metadaten, Statistiken, Fehler
- Pretty-printed für Lesbarkeit

### Excel-Format
- Matches werden im Speicher gesammelt
- Excel-Datei wird am Ende mit allen Matches erstellt
- Header-Zeile mit Styling
- Spaltenbreiten automatisch angepasst
- Fallback zu CSV bei fehlendem `openpyxl`

## Rückwärtskompatibilität

✅ **Vollständig rückwärtskompatibel**:
- CSV bleibt Standard-Format
- Bestehende Scripts funktionieren ohne Änderungen
- Alle bestehenden CLI-Optionen funktionieren mit allen Formaten
- `--no-header` betrifft nur CSV-Format
- Dateinamen folgen demselben Muster für alle Formate

## Verwendung

### Basis-Verwendung
```bash
# CSV (Standard, wie bisher)
python main.py --path /data --regex

# JSON
python main.py --path /data --regex --format json

# Excel
python main.py --path /data --regex --format xlsx
```

### Mit anderen Optionen
```bash
python main.py \
  --path /var/data-leak/ \
  --regex \
  --ner \
  --format json \
  --outname "Großes Datenleck" \
  --whitelist stopwords.txt \
  --output-dir ./results/ \
  --verbose
```

## Performance

- **CSV**: Schnellste, schreibt inkrementell, niedriger Speicherverbrauch
- **JSON**: Schnell, schreibt am Ende, moderater Speicherverbrauch
- **XLSX**: Langsamer, schreibt am Ende, moderater Speicherverbrauch

Für sehr große Ergebnis-Mengen (>100k Treffer) wird CSV-Format empfohlen.

## Fehlerbehandlung

### Fehlendes openpyxl für Excel-Format

Wenn `openpyxl` nicht installiert ist und Excel-Format angefordert wird:
- Fehlermeldung wird geloggt
- Automatischer Fallback zu CSV-Format
- CSV-Datei wird mit `.csv` Extension erstellt

**Installation**:
```bash
pip install openpyxl
# oder
pip install -r requirements.txt
```

## Testing

Die Implementierung wurde getestet:
- ✅ Syntax-Check: Alle Dateien kompilieren korrekt
- ✅ Linter: Keine Fehler
- ✅ Rückwärtskompatibilität: CSV bleibt Standard

Für vollständige Tests sollten Integrationstests mit echten Daten durchgeführt werden.

## Dokumentation

Siehe `OUTPUT_FORMATS.md` für detaillierte Dokumentation zu allen Output-Formaten.
