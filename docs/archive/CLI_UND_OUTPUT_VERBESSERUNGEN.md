# CLI-Optionen und Output-Verbesserungsvorschläge

## Aktuelle CLI-Optionen

### Erforderliche Optionen
- `--path`: Stammverzeichnis für rekursive Suche (erforderlich)

### Optionale Optionen
- `--regex`: Regex-basierte PII-Erkennung aktivieren (mindestens eine von `--regex`/`--ner` erforderlich)
- `--ner`: KI-basierte Named Entity Recognition aktivieren (mindestens eine von `--regex`/--ner` erforderlich)
- `--verbose` / `-v`: Ausführliche Ausgabe mit detailliertem Logging
- `--outname`: String für Ausgabedateinamen
- `--whitelist`: Pfad zu Textdatei mit Ausschlussmustern (eine pro Zeile)
- `--stop-count`: Analyse nach N Dateien abbrechen (für Tests)

## Aktueller Output-Format

### Konsolen-Ausgabe (nur im Verbose-Modus)
- Analyse-Start/Ende
- Aktivierungsstatus von Regex/NER
- Statistiken (Dateiendungen, Gesamtanzahl)
- Fehlerliste
- Performance-Metriken

### Datei-Ausgaben
1. **Log-Datei**: `[timestamp]_log.txt`
   - Alle Log-Informationen
   - Timestamps, Log-Level, Nachrichten

2. **CSV-Datei**: `[timestamp]_findings.csv`
   - Spalten: `match`, `file`, `type`, `ner_score`
   - UTF-8 kodiert
   - **Aktuell ohne Header-Zeile**

## Verbesserungsvorschläge

### 1. CLI-Optionen (Hoch-Priorität)

#### 1.1 `--version` / `-V` hinzufügen
**Vorschlag**: Versionsinformation anzeigen
```python
parser.add_argument("--version", "-V", action="version", version="%(prog)s 1.0.0")
```

#### 1.2 `--output-dir` hinzufügen
**Vorschlag**: Eigenes Ausgabeverzeichnis wählen
```python
parser.add_argument("--output-dir", action="store", default="./output/",
                    help="Verzeichnis für Ausgabedateien (Standard: ./output/)")
```

#### 1.3 `--config` hinzufügen
**Vorschlag**: Eigenen Config-Dateipfad angeben
```python
parser.add_argument("--config", action="store", default="config_types.json",
                    help="Pfad zur Konfigurationsdatei (Standard: config_types.json)")
```

#### 1.4 `--quiet` / `-q` hinzufügen
**Vorschlag**: Alle Ausgaben außer Fehlern unterdrücken
```python
parser.add_argument("--quiet", "-q", action="store_true",
                    help="Alle Ausgaben außer Fehlern unterdrücken")
```

#### 1.5 Verbesserte Validierung
**Vorschlag**: 
- Validierung dass mindestens eine von `--regex`/`--ner` gesetzt ist
- Validierung dass `--whitelist` existiert, falls angegeben
- Validierung dass `--stop-count` positiv ist, falls angegeben

### 2. Output-Format (Hoch-Priorität)

#### 2.1 CSV-Header hinzufügen
**Aktuelles Problem**: CSV-Datei hat keine Header-Zeile

**Vorschlag**:
- Header-Zeile standardmäßig hinzufügen: `match,file,type,ner_score`
- Option `--no-header` für Rückwärtskompatibilität
- **Rückwärtskompatibilität**: Die meisten CSV-Reader können mit Headern umgehen, aber `--no-header` Flag für strikte Kompatibilität

**Implementierung**:
```python
# In setup.py, nach CSV-Erstellung:
if not args.no_header:
    globals.csvwriter.writerow(["match", "file", "type", "ner_score"])
```

#### 2.2 Zusammenfassung immer anzeigen
**Aktuelles Problem**: Zusammenfassung nur im Verbose-Modus sichtbar

**Vorschlag**: 
- Zusammenfassung immer am Ende anzeigen (auch ohne `--verbose`)
- Format:
  ```
  ========================================
  Analyse-Zusammenfassung
  ========================================
  Dateien verarbeitet:    1.234
  Dateien analysiert:     567
  Treffer gefunden:       89
  Fehler:                 12
  Ausführungszeit:        2m 34s
  Durchsatz:              3,7 Dateien/Sek
  ========================================
  ```

#### 2.3 Fortschrittsanzeige verbessern
**Aktuelles Problem**: Fortschrittsbalken nur im Verbose-Modus

**Vorschlag**:
- Fortschrittsbalken auch ohne Verbose für lange Operationen anzeigen
- ETA (geschätzte verbleibende Zeit) hinzufügen
- Durchsatz (MB/s, Dateien/s) anzeigen

### 3. Output-Format (Mittel-Priorität)

#### 3.1 Fehler-Zusammenfassung
**Vorschlag**: 
- Fehler nach Typ gruppieren mit Anzahl
- Beispiel:
  ```
  Errors
  ------
  Permission denied: 5 Dateien
      /path/to/file1.pdf
      /path/to/file2.docx
      ...
  File too large: 2 Dateien
      ...
  ```

#### 3.2 Strukturierte Konsolen-Ausgabe
**Vorschlag**: 
- Konsistente Formatierung
- Klare Abschnitte
- Farbausgabe (optional mit `--color` Flag)

#### 3.3 Zusätzliche CSV-Spalten (optional)
**Vorschlag**:
- `timestamp`: Zeitpunkt des Fundes
- `line_number`: Zeilennummer (falls verfügbar)
- `context`: Umgebender Text (optional)

**Rückwärtskompatibilität**: Neue Spalten nur am Ende hinzufügen, nie bestehende Spalten ändern

### 4. Output-Format (Niedrig-Priorität / Zukunft)

#### 4.1 JSON-Output
**Vorschlag**: `--format json` für maschinenlesbare Ausgabe
```json
{
  "metadata": {...},
  "statistics": {...},
  "findings": [...],
  "errors": [...]
}
```

#### 4.2 HTML-Report
**Vorschlag**: `--format html` für interaktiven Report
- Dashboard mit Zusammenfassung
- Interaktiver Dateibrowser
- Treffer-Hervorhebung
- Diagramme/Grafiken

## Rückwärtskompatibilität

### Wichtige Prinzipien

1. **CSV-Format**: 
   - Header standardmäßig hinzufügen (meiste Tools können damit umgehen)
   - `--no-header` Flag für strikte Kompatibilität
   - Spaltenreihenfolge nie ändern
   - Neue Spalten nur am Ende hinzufügen

2. **Ausgabeverzeichnis**: 
   - Standard `./output/` beibehalten
   - `--output-dir` als Option

3. **Dateinamen**: 
   - Aktuelles Timestamp-Format beibehalten
   - `--outname` Funktionalität beibehalten

4. **Log-Format**: 
   - Aktuelles Format als Standard beibehalten
   - Neue Formate als Optionen

5. **Konsolen-Ausgabe**: 
   - Aktuelle Ausgabe beibehalten
   - Zusätzliche Zusammenfassung hinzufügen (nicht ersetzen)

### Migrationspfad

**Phase 1** (Sofort - Rückwärtskompatibel):
- ✅ CSV-Header hinzufügen (mit `--no-header` Flag)
- ✅ Zusammenfassung immer anzeigen
- ✅ `--version` Flag
- ✅ `--output-dir` Flag
- ✅ Fortschrittsbalken verbessern

**Phase 2** (Zukunft - Optional):
- JSON/XML Output-Formate
- HTML-Report
- Strukturiertes Logging
- Farbausgabe

## Implementierungs-Priorität

### Hoch-Priorität (Einfach, hoher Nutzen)
1. ✅ CSV-Header hinzufügen (mit `--no-header` für Kompatibilität)
2. ✅ `--version` Flag
3. ✅ `--output-dir` Flag
4. ✅ Zusammenfassung immer anzeigen
5. ✅ Fortschrittsbalken verbessern

### Mittel-Priorität (Moderater Aufwand, gute UX)
1. `--config` Flag
2. `--max-file-size` Flag
3. Fehler-Zusammenfassung mit Anzahl
4. Strukturierte Konsolen-Ausgabe
5. `--quiet` Flag

### Niedrig-Priorität (Zukunfts-Erweiterungen)
1. JSON/XML Output-Formate
2. HTML-Report
3. Farbausgabe
4. Context-Spalte in CSV
5. Zeilennummern zu Treffern

## Zusammenfassung

Die aktuellen CLI-Optionen und Output-Formate sind funktional, können aber verbessert werden durch:

1. **Bessere Benutzerfreundlichkeit**: 
   - Versionsinformation
   - Eigenes Ausgabeverzeichnis
   - Bessere Validierung

2. **Besserer Output**: 
   - CSV-Header für bessere Lesbarkeit
   - Immer sichtbare Zusammenfassung
   - Strukturierte Fehlerausgabe

3. **Mehr Flexibilität**: 
   - Eigenes Config-File
   - Verschiedene Output-Formate (Zukunft)

4. **Bessere UX**: 
   - Fortschrittsanzeige auch ohne Verbose
   - Strukturierte Zusammenfassungen

**Alle Verbesserungen müssen rückwärtskompatibel sein** - bestehende Scripts und Workflows müssen weiterhin funktionieren.
