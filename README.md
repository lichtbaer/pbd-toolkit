Installation
============

* (optional) virtuelle Umgebung erstellen:
```shell
python3 -m venv .venv
source .venv/bin/activate
```
* Abhängigkeiten installieren: `pip install -r requirements.txt`

Verwendung
==========

Das Toolkit wird über die Konsole mittels des Befehls `python main.py` gestartet. Der
Kommandozeilenparameter `--path` muss in jedem Fall an das Toolkit übergeben werden. Er enthält
den Pfad zu dem Stammverzeichnis, in dem und unterhalb von dem die Suche nach personenbezogenen
Daten gestartet wird. Es gibt einen weiteren, optional Parameter `--name`, der sich nur auf
die Benennung der Ausgabedateien auswirkt.

Beispiel für einen vollständigen Aufruf: `python main.py --path /var/data-leak/ --name "Großes Datenleck"`

Funktionsumfang
===============

Das Toolkit kann derzeit folgende Zeichenketten erkennen:
* Deutsche Rentenversicherungsnummern
* IBAN (Fokus auf bei deutschen Bankkonten übliche Formate)
* E-Mail-Adressen (übliche Formate)
* IPv4-Adressen
* bestimmte Signalwörter: "Abmahnung", "Bewerbung", "Zeugnis", "Entwicklungsbericht", "Gutachten", "Krankmeldung"

Im derzeitigen Stadium wird **keine** Aussage dazu getroffen, ob es sich dabei mit einer bestimmten
Wahrscheinlichkeit um personenbezogene Daten handelt. Es erfolgt keine semantische Betrachtung der
gefundenen Zeichenketten oder ihres Kontexts.

Derzeit wird eine Suche in folgenden Dateiformaten unterstützt, wobei die Auswahl von Dateien ausschließlich
aufgrund ihrer Dateiendung erfolgt:
* .pdf
* .docx
* .html

Bei jeder Ausführung werden im Unterverzeichnis output/ zwei Dateien erzeugt:
* [Zeitstempel]_log.txt: Enthält Informationen zur Ausführung wie z. B. Zeitpunkt, gefundene
  Dateiendungen und Fehler/Auffälligkeiten bei der Ausführung (z. B. Dateien, die nicht gelesen
  werden konnten)
* [Zeitstempel]_findings.csv: Enthält alle Funde von Zeichenketten aus diesem Durchlauf. Die
  CSV-Datei besteht aus drei Spalten:
  * *match*: Die gefundene Zeichenkette
  * *file*: Der Pfad zu der Datei, in der die Zeichenkette gefunden wurde
  * *type*: Der Typ von Zeichenkette, die gefunden wurde (s. o.)

Fragen/Kritik/Anregungen/Patches
================================

Gerne via openCode oder an das Referat 3.2 - technische Datenschutzprüfungen - des Hessischen
Beauftragten für Datenschutz und Informationsfreiheit.

ToDo/Pläne
==========

* Semantische Betrachtung von Funden, z. B. mittels LLM
* Unterstützung weiterer Dateiformate
* Unterstützung von PDF-Dateien ohne Texteinbettungen mittels OCR
* Unterstützung von DOCX-Dateien ausweiten auf Text in Header, Footer und in Tabellen
