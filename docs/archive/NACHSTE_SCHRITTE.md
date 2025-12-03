# Nächste Schritte - Refactoring Roadmap

## Status: Phase 1 abgeschlossen ✅

Alle Sofort-Prioritäten wurden erfolgreich umgesetzt:
- ✅ Output-Writer extrahiert
- ✅ Custom Exception Types
- ✅ Exit Codes implementiert
- ✅ Quiet-Mode hinzugefügt
- ✅ main.py refactored

---

## Phase 2: Core Refactoring (Empfohlen als Nächstes)

### Priorität: Hoch | Aufwand: 15-20 Stunden | Risiko: Mittel

### 1. Scanner-Logik extrahieren

**Problem**: File-Walking-Logik ist direkt in `main.py` (Zeilen 236-325)

**Lösung**: 
- Neue Datei: `core/scanner.py`
- Klasse: `FileScanner`
- Methode: `scan(path: str) -> ScanResult`

**Vorteile**:
- ✅ Bessere Testbarkeit
- ✅ Klare Separation of Concerns
- ✅ Einfacher zu erweitern (z.B. parallele Verarbeitung)

**Konkrete Schritte**:
1. `core/scanner.py` erstellen
2. File-Walking-Logik aus `main.py` extrahieren
3. `ScanResult` Dataclass erstellen (für Rückgabewerte)
4. Tests schreiben
5. `main.py` anpassen, um Scanner zu verwenden

**Geschätzter Aufwand**: 4-6 Stunden

---

### 2. Processor-Logik extrahieren

**Problem**: Text-Processing-Logik ist direkt in `main.py` (Zeilen 150-208)

**Lösung**:
- Neue Datei: `core/processor.py`
- Klasse: `TextProcessor`
- Methode: `process_text(text: str, file_path: str) -> list[PiiMatch]`

**Vorteile**:
- ✅ Isolierte Verarbeitungslogik
- ✅ Einfacher zu testen
- ✅ Kann später für parallele Verarbeitung verwendet werden

**Konkrete Schritte**:
1. `core/processor.py` erstellen
2. `process_text()` Funktion extrahieren
3. Thread-Locks in Processor verschieben
4. Tests schreiben
5. `main.py` anpassen

**Geschätzter Aufwand**: 3-4 Stunden

---

### 3. Statistics-Tracking extrahieren

**Problem**: Statistics-Logik ist über mehrere Stellen verteilt

**Lösung**:
- Neue Datei: `core/statistics.py`
- Klasse: `Statistics` (erweitert `NerStats`)
- Zentralisiert alle Statistik-Tracking

**Vorteile**:
- ✅ Zentrale Statistik-Verwaltung
- ✅ Einfacher zu erweitern
- ✅ Klare API

**Konkrete Schritte**:
1. `core/statistics.py` erstellen
2. `Statistics` Klasse erweitern (NerStats integrieren)
3. Alle Statistik-Operationen zentralisieren
4. Tests schreiben

**Geschätzter Aufwand**: 2-3 Stunden

---

### 4. Application Context einführen (Kritisch)

**Problem**: `globals.py` verwendet globale Variablen, erschwert Testing

**Lösung**:
- Neue Datei: `core/context.py`
- Klasse: `ApplicationContext` (dataclass)
- Enthält: config, logger, output_writer, statistics, error_collector
- Factory-Method: `from_cli_args(args) -> ApplicationContext`

**Vorteile**:
- ✅ Eliminiert globale Variablen
- ✅ Deutlich bessere Testbarkeit
- ✅ Klare Dependency-Graph
- ✅ Thread-Safe

**Konkrete Schritte**:
1. `core/context.py` erstellen
2. `ApplicationContext` Dataclass definieren
3. Factory-Method implementieren
4. `globals.py` Verwendungen durch Context ersetzen
5. `setup.py` anpassen, um Context zu erstellen
6. `main.py` anpassen, um Context zu verwenden
7. Tests anpassen

**Geschätzter Aufwand**: 6-8 Stunden

**Risiko**: Mittel-Hoch (viele Dateien betroffen)

---

## Phase 3: Erweiterte Features (Optional)

### Priorität: Mittel | Aufwand: 20-30 Stunden | Risiko: Niedrig-Mittel

### 5. Plugin-System

**Ziel**: Auto-Discovery von File Processors via Entry Points

**Vorteile**:
- ✅ Processors können als separate Packages installiert werden
- ✅ Einfacher zu erweitern
- ✅ Bessere Modularisierung

**Aufwand**: 4-6 Stunden

---

### 6. Event-System

**Ziel**: Event-basierte Architektur für Hooks

**Vorteile**:
- ✅ Plugins können auf Events reagieren
- ✅ Erweiterte Funktionalität ohne Core-Änderungen
- ✅ Flexiblere Architektur

**Aufwand**: 8-10 Stunden

---

### 7. Vollständige Type Hints

**Ziel**: Alle `Any` durch konkrete Types ersetzen

**Aufwand**: 4-6 Stunden

---

## Empfohlene Reihenfolge

### Option A: Schrittweise (Empfohlen)

1. **Scanner-Logik extrahieren** (4-6h)
   - Niedriges Risiko
   - Sofortiger Nutzen
   - Gute Basis für weitere Refactorings

2. **Processor-Logik extrahieren** (3-4h)
   - Niedriges Risiko
   - Klare Verbesserung
   - Macht Application Context einfacher

3. **Statistics-Tracking extrahieren** (2-3h)
   - Niedriges Risiko
   - Schnell umsetzbar
   - Gute Vorbereitung für Context

4. **Application Context einführen** (6-8h)
   - Mittel-Hoch Risiko
   - Sehr hoher Nutzen
   - Fundamentale Verbesserung

**Gesamtaufwand**: 15-21 Stunden

### Option B: Direkt zu Application Context

1. **Application Context einführen** (6-8h)
   - Größter Nutzen
   - Macht weitere Refactorings einfacher
   - Aber höheres Risiko

2. **Dann Scanner/Processor extrahieren** (7-10h)
   - Mit Context bereits einfacher

**Gesamtaufwand**: 13-18 Stunden

---

## Konkrete nächste Schritte (Empfehlung)

### Sofort starten mit: Scanner-Logik extrahieren

**Warum**:
- ✅ Niedriges Risiko
- ✅ Sofortiger Nutzen
- ✅ Macht main.py deutlich kleiner
- ✅ Gute Basis für weitere Refactorings

**Was wird gemacht**:
1. `core/scanner.py` erstellen
2. `FileScanner` Klasse mit `scan()` Methode
3. `ScanResult` Dataclass für Rückgabewerte
4. File-Walking-Logik aus `main.py` extrahieren
5. Tests schreiben
6. `main.py` vereinfachen

**Erwartetes Ergebnis**:
- `main.py` wird von ~420 auf ~300 Zeilen reduziert
- Klare Separation: Scanner vs. Orchestration
- Bessere Testbarkeit

---

## Metriken-Ziele

### Aktuell:
- main.py: ~420 Zeilen
- Globale Variablen: 6 (in globals.py)
- Test-Coverage: Unbekannt

### Nach Phase 2:
- main.py: < 200 Zeilen ✅
- Globale Variablen: 0 ✅
- Test-Coverage: > 70% ✅

---

## Entscheidungshilfe

**Wähle Option A (Schrittweise) wenn**:
- Du sicher gehen willst
- Du kleine, testbare Schritte bevorzugst
- Du Zeit hast für mehrere Commits

**Wähle Option B (Direkt Context) wenn**:
- Du den größten Nutzen schnell willst
- Du bereit bist für größere Änderungen
- Du die Abhängigkeiten gut verstehst

---

## Fragen zur Klärung

Bevor wir starten, sollten wir klären:

1. **Welche Option bevorzugst du?** (A: Schrittweise, B: Direkt Context)
2. **Sollen wir Tests parallel schreiben?** (Empfohlen: Ja)
3. **Soll jeder Schritt ein separater Commit sein?** (Empfohlen: Ja)
4. **Gibt es spezielle Anforderungen?** (z.B. Rückwärtskompatibilität)

---

**Bereit zum Start?** Sage einfach, welche Option du bevorzugst, und ich beginne mit der Umsetzung!
