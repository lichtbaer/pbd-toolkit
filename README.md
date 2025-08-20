*(If you're looking for an English README, check out the file [README_en.md in the docs/ sub-directory](./docs/README_en.md))*

Bei dem *pbD-Toolkit* handelt es sich um ein Tool, das der Hessische Beauftragte für Datenschutz und Informationsfreiheit (HBDI) programmiert hat, um große Datenmenge zu durchsuchen. Das Tool soll dabei Hinweise dafür suchen, ob in diesen Datenmengen personenbezogene Daten enthalten sein könnten. Ein Beispiel für große Datenmengen, die der HBDI damit durchsucht, sind Daten-Leaks, die etwa im sogenannten Darknet veröffentlicht werden.

Der HBDI teilt dieses Tool mit der Öffentlichkeit, damit es auch von anderen Stellen genutzt und vielleicht sogar weiterentwickelt werden kann.

Beim HBDI wird das Tool von dem Referat 3.2 - technische Datenschutzprüfungen - gepflegt. Die Ansprechpartner findet man zum Beispiel über das Organigramm, das der HBDI auf [dieser Seite](https://datenschutz.hessen.de/ueber-uns/aufgaben-und-organisation) veröffentlicht. Vertreter der Presse finden Ansprechpartner auf [dieser anderen Seite](https://datenschutz.hessen.de/presse-0).


Installation
============

* (optional) virtuelle Umgebung erstellen:
```shell
python3 -m venv .venv
source .venv/bin/activate
```
* Abhängigkeiten installieren: `pip install -r requirements.txt`
* Für die Verwendung KI-gestützer Verfahren sollte das verwendete Modell vorab heruntergeladen werden. Es wird vorausgesetzt, dass ein HuggingFace-Account registriert wurde und die Authentifizierung erfolgt ist (`pip install "huggingface_hub[cli]"`, `hf auth login`). Sodann Download des Models via: `hf download urchade/gliner_medium-v2.1`

Verwendung
==========

Das Toolkit wird über die Konsole mittels des Befehls `python main.py` gestartet. Der
Kommandozeilenparameter `--path` muss in jedem Fall an das Toolkit übergeben werden. Er enthält
den Pfad zu dem Stammverzeichnis, in dem und unterhalb von dem die Suche nach personenbezogenen
Daten gestartet wird.

Mindestens einer der Parameter `--ner`/`--regex` muss gesetzt sein. `--regex` aktiviert die Suche mittels regulärer Ausdrücke, `--ner` aktiviert die Suche mittels eines KI-basierten Named Entity Recognition-Verfahrens.

Ein weiterer, optionaler Parameter `--outname`, wirkt sich auf
die Benennung der Ausgabedateien aus.

Der optionale Parameter `--whitelist` enthält den Pfad zu einer Textdatei, die pro Zeile eine Zeichenkette enthält, die als Ausschlusskriterium für potentielle Treffer herangezogen wird. Steht in einer Zeile etwa die Zeichenkette "info@", so werden in der findings.csv keinerlei E-Mail-Adressen ausgegeben, welche diese Zeichenkette beinhalten. Das kann dazu genutzt werden, um falsch-positive Ergebnisse auszuschließen, z. B. bei solchen E-Mail-Adressen, die bekanntermaßen nicht personenbezogen sind.

Der optionale Parameter `--stop-count` kann benutzt werden, um die Analyse nach einer bestimmten Anzahl von Dateien abzubrechen, z. B. zu Erprobungszwecken.

Die Sprache des Programms kann über die Umgebungsvariable `LANGUAGE` beeinflusst werden, welche die Werte "de" und "en" akzeptiert. Der Standardwert ist "de".

Beispiel für einen vollständigen Aufruf: `python main.py --path /var/data-leak/ --outname "Großes Datenleck" --ner --regex --whitelist stopwords.txt --stop-count 200`

Funktionsumfang
===============

Das Toolkit kann derzeit folgende Zeichenketten erkennen:
* Suche mittels regulärer Ausdrücke:
  * Deutsche Rentenversicherungsnummern
  * IBAN (Fokus auf bei deutschen Bankkonten übliche Formate)
  * E-Mail-Adressen (übliche Formate)
  * IPv4-Adressen
  * bestimmte Signalwörter: "Abmahnung", "Bewerbung", "Zeugnis", "Entwicklungsbericht", "Gutachten", "Krankmeldung"
  * Private PGP-Schlüssel
* Suche mittels KI-basierter Named Entity Recognition:
  * Namen von Personen
  * Orte
  * Gesundheitsdaten (experimentell - schlechte Ergebnisqualität)
  * Passwörter (experimentell - schlechte Ergebnisqualität)

Im derzeitigen Stadium wird eine Aussage dazu, ob es sich dabei mit einer bestimmten
Wahrscheinlichkeit um personenbezogene Daten handelt, nur von der KI-basierten Suchmethode unterstützt. 

Derzeit wird eine Suche in folgenden Dateiformaten unterstützt, wobei die Auswahl von Dateien ausschließlich
aufgrund ihrer Dateiendung erfolgt:
* .pdf
* .docx
* .html
* .txt (auch Dateien ohne Dateiendung, wenn der Mime Type "text/plain" erkannt wird)

Bei jeder Ausführung werden im Unterverzeichnis output/ zwei Dateien erzeugt:
* [Zeitstempel]_log.txt: Enthält Informationen zur Ausführung wie z. B. Zeitpunkt, gefundene
  Dateiendungen und Fehler/Auffälligkeiten bei der Ausführung (z. B. Dateien, die nicht gelesen
  werden konnten)
* [Zeitstempel]_findings.csv: Enthält alle Funde von Zeichenketten aus diesem Durchlauf. Die
  CSV-Datei besteht aus drei Spalten:
  * *match*: Die gefundene Zeichenkette
  * *file*: Der Pfad zu der Datei, in der die Zeichenkette gefunden wurde
  * *type*: Der Typ von Zeichenkette, die gefunden wurde (s. o.)
  * *ner_score*: Bei der KI-basierten Suchmethode: Aussagekraft der Erkennung (Selbstbewertung des Modells)

Fragen/Kritik/Anregungen/Patches
================================

Gerne via openCode oder an das Referat 3.2 - technische Datenschutzprüfungen - des Hessischen
Beauftragten für Datenschutz und Informationsfreiheit.

ToDo/Pläne
==========

* i18n
* Unterstützung für Krankenversicherungsnummern (reguläre Ausdrücke)
* Unterstützung weiterer Dateiformate
* Unterstützung von PDF-Dateien ohne Texteinbettungen mittels OCR
* Unterstützung von DOCX-Dateien ausweiten auf Text in Header, Footer und in Tabellen
