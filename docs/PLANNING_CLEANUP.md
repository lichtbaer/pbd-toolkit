# Planungs- und Review-Dateien: Aufräum-Empfehlung

## Empfehlung: Dateien ins Archiv verschieben

Die folgenden Dateien sind abgeschlossen und könnten ins `archive/` Verzeichnis verschoben werden, um die Hauptdokumentation übersichtlicher zu halten:

### Phase-Dokumentation (historisch, aber nützlich)
Diese dokumentieren den Fortschritt während der Refactoring-Phasen:
- `PHASE2_SCHRITT1_ABGESCHLOSSEN.md` → `archive/`
- `PHASE2_SCHRITT2_ABGESCHLOSSEN.md` → `archive/`
- `PHASE2_SCHRITT3_ABGESCHLOSSEN.md` → `archive/`
- `PHASE2_SCHRITT4_ABGESCHLOSSEN.md` → `archive/`
- `UMGESETZTE_SOFORT_PRIORITAETEN.md` → `archive/`

### Abgeschlossene Analysen
- `ANALYTICAL_ENGINES_EXTENSION_ANALYSIS.md` → `archive/` (detaillierte Analyse, abgeschlossen)
- `ANALYTICAL_ENGINES_ZUSAMMENFASSUNG.md` → `archive/` (Zusammenfassung, abgeschlossen)
- `IMPLEMENTATION_ENGINES_EXTENSION.md` → `archive/` (Implementierung abgeschlossen)

### Redundante Zusammenfassungen
- `REFACTORING_ZUSAMMENFASSUNG.md` → `archive/` (redundant zu `REFACTORING_ABGESCHLOSSEN.md`)

## Behalten im Hauptverzeichnis

### Status-Dokumente (aktuell)
- `FINAL_STATUS.md` - Finaler Status nach allen Phasen
- `REFACTORING_ABGESCHLOSSEN.md` - Vollständige Refactoring-Zusammenfassung
- `VERBESSERUNGS_CHECKLISTE_AKTUELL.md` - Aktuelle Checkliste (wird aktualisiert)

### Architektur-Dokumente (aktuell)
- `ARCHITEKTUR_ANALYSE_AKTUELL.md` - Detaillierte Architektur-Analyse
- `ARCHITEKTUR_ZUSAMMENFASSUNG_AKTUELL.md` - Architektur-Zusammenfassung

### Übersichts-Dokumente
- `README_REFACTORING.md` - Übersicht der Refactoring-Dokumentation
- `PLANNING_README.md` - Übersicht der Planungsdokumentation (neu)

### Feature-Dokumentation
- `EXIT_CODES.md` - Exit Code Dokumentation (aktuell)
- `CONFIG_FILE_EXAMPLE.yaml` - Config File Beispiel (aktuell)
- `CONFIG_FILE_EXAMPLE.json` - Config File Beispiel (aktuell)

## Vorgehen

1. **Option A (Empfohlen)**: Dateien ins Archiv verschieben
   - Behält alle Dokumente für historische Referenz
   - Macht Hauptverzeichnis übersichtlicher
   - Verweis in `PLANNING_README.md` auf Archiv

2. **Option B**: Dateien löschen
   - Nur wenn sicher, dass sie nicht mehr benötigt werden
   - Nicht empfohlen, da historische Dokumentation wertvoll sein kann

## Aktionsplan

```bash
# Verschiebe Phase-Dokumentation ins Archiv
mv docs/PHASE2_SCHRITT*.md docs/archive/
mv docs/UMGESETZTE_SOFORT_PRIORITAETEN.md docs/archive/

# Verschiebe abgeschlossene Analysen ins Archiv
mv docs/ANALYTICAL_ENGINES_EXTENSION_ANALYSIS.md docs/archive/
mv docs/ANALYTICAL_ENGINES_ZUSAMMENFASSUNG.md docs/archive/
mv docs/IMPLEMENTATION_ENGINES_EXTENSION.md docs/archive/

# Verschiebe redundante Zusammenfassung
mv docs/REFACTORING_ZUSAMMENFASSUNG.md docs/archive/
```

## Nach dem Verschieben

- `PLANNING_README.md` aktualisieren mit Verweisen auf Archiv
- `README_REFACTORING.md` aktualisieren falls nötig
