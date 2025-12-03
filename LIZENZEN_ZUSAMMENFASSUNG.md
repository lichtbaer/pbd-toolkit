# Lizenz-Kompatibilitätsprüfung - Zusammenfassung

## Projektlizenz

Das Projekt verwendet **EUPL v1.2** (European Union Public Licence v1.2).

## Ergebnis der Prüfung

✅ **Alle 16 direkten Abhängigkeiten sind mit EUPL v1.2 kompatibel.**

### Übersicht

- **Gesamt**: 16 Abhängigkeiten
- **Kompatibel**: 16 (100%)
- **Problematisch**: 0
- **Unbekannt**: 0

### Lizenzverteilung

Die meisten Abhängigkeiten verwenden permissive Lizenzen:
- **MIT**: 9 Pakete (python-docx, beautifulsoup4, pdfminer.six, pytest, pytest-cov, openpyxl, python-pptx, PyYAML, spacy)
- **Apache-2.0**: 3 Pakete (gliner, odfpy, requests)
- **BSD**: 2 Pakete (striprtf, xlrd)
- **MPL-2.0 AND MIT**: 1 Paket (tqdm - dual-licensed)
- **GPL-3.0**: 1 Paket (extract-msg - explizit kompatibel mit EUPL)

### Wichtige Erkenntnisse

1. **Permissive Lizenzen (MIT, BSD, Apache-2.0)**: Diese stellen keine Kompatibilitätsprobleme dar, da sie keine Copyleft-Anforderungen haben.

2. **GPL-3.0 (extract-msg)**: GPL-3.0 ist explizit in der EUPL v1.2 Kompatibilitätsliste aufgeführt. Laut EUPL-Lizenztext können abgeleitete Werke unter der kompatiblen Lizenz (GPL-3.0) verteilt werden, wenn Werke kombiniert werden.

3. **Dual-Lizenzen**: 
   - `tqdm` bietet MPL-2.0 UND MIT - beide Optionen sind kompatibel
   - `odfpy` bietet Apache, GPL und LGPL - Apache-2.0 ist empfohlen

### Empfehlungen

1. ✅ **Keine sofortigen Maßnahmen erforderlich** - Alle direkten Abhängigkeiten sind kompatibel
2. ⚠️ **Transitive Abhängigkeiten prüfen** - Bei größeren Updates sollten auch indirekte Abhängigkeiten überprüft werden
3. 📝 **Lizenzwahl dokumentieren** - Bei dual-lizenzierten Paketen (tqdm, odfpy) sollte dokumentiert werden, welche Lizenzoption verwendet wird

### Detaillierter Bericht

Für eine vollständige Analyse siehe `LICENSE_COMPATIBILITY_REPORT.md` (englisch) oder `license_report.json` (maschinenlesbar).

### Verifizierung

Die Prüfung wurde mit einem automatisierten Skript (`check_licenses.py`) durchgeführt, das:
- Paket-Metadaten von PyPI abruft
- Lizenz-Expressions und Classifier prüft
- Lizenznamen zu SPDX-Identifikatoren normalisiert
- Kompatibilität mit EUPL v1.2 basierend auf der offiziellen EUPL-Kompatibilitätsliste verifiziert

---

**Fazit**: Das Projekt kann alle verwendeten Bibliotheken ohne Lizenzkonflikte nutzen.
