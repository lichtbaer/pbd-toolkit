*(Please note that this is a best effort translation; with regards to documentation and program output, we consider the German version to be the only authoritative one)*

The *pbD-Toolkit*[^1] was programmed by the Hessian Commissioner for Data Protection and Freedom of Information (HBDI) to facilitate searching large amounts of data. Its search features help identify indicators for the presence of personally identifiable data within. An example for data that the HBDI might want to search in would be a leaked data dump that might be made public on the so-called darknet.

The HBDI has decided t o share this tool with the public so that others may use it or contribute to its development.

Within the HBDI's organization, the tool is maintained by sub-department 3.2 (technical data protection audits). You can find the contact persons by looking up the HBDI's organization chart linked on [this page](https://datenschutz.hessen.de/ueber-uns/aufgaben-und-organisation). Press representatives can find their respective points of contact on [this page](https://datenschutz.hessen.de/presse-0). These pages might only be available in German.

[^1]: Using an abbreviation for the German translation of *Personally Identifiable Data*. Therefore, an anglicized version of the toolkit's name might be *PII Toolkit*.

Setup
============

* (optional) setup a virtual python environment:
```shell
python3 -m venv .venv
source .venv/bin/activate
```
* Install the requirements: `pip install -r requirements.txt`
* For using AI-based methods, it is recommended to download the model used ahead of analysis. Assuming that a HuggingFace has been registered and authenticated against (`pip install huggingface_hub[cli]`, `hf auth login`), the model can be downloaded via: `hf download urchade/gliner_medium-v2.1`

Usage
==========

The toolkit is run from the command line using `python main.py`. The command line argument `--path` always needs to be passed along. It contains the path to the root directory in which the search for personally identfiable data will start (all sub-directories will be searched as well). 

At least one of the parameters `--ner`/`--regex` must be set. `--regex` activates the search using regular expressions, while `--ner` activates the search using an AI-based Named Entity Recognition method.

An additional, optional command line argument `--name` can be used to be included in the naming of output files.

The optional parameter `--whitelist` gives the path to a text file containing one string per line used for excluding potential matches. For example, if a line contains the string "info@", then the findings.csv will not show any email addresses containing that string. This can be used to exclude known false positives, such as email addresses that would not be considered personally identifiable.

The optional parameter `--stop-count` can be used to stop analyses after a specific number of files, e. g. for testing purposes.

An example for a complete command line call would be: `python main.py --path /var/data-leak/ --name "Big Data Leak" --ner --regex --whitelist stopwords.txt --stop-count 200`

Features
===============

Currently, the toolkit is able to identify the following kinds of strings:
* Using regular expressions:
  * German public pension insurance fund IDs (*Deutsche Rentenversicherungsnummern*)
  * IBAN (specialized in formats that are common for German bank accounts)
  * Email addresses (common formats)
  * IPv4 adresses
  * specific signal words: "Abmahnung", "Bewerbung", "Zeugnis", "Entwicklungsbericht", "Gutachten", "Krankmeldung" (chosen as to be commonly seen in the context of personally identifiable data in German documents)
  * private pgp keys
* Using AI-based Named Entity Recognition:
  * Names of Persons
  * Locations
  * Health Data (experimental - questionable quality of results)
  * Passwords (experimental - questionable quality of results)

In the current version this tool only gives an estimate about the likelihood with which data found should actually be classified as personally identifiable data for the AI-based search method

Currently, the following file formats will be searched (as identified by the file extension given):
* .pdf
* .docx
* .html
* .txt (also includes files with no extension with a mime type of "text/plain")

On every run, two files will be created in the output/ sub-directory:
* [TIMESTAMP]_log.txt: Information about the tool's execution, such as the time and date of execution, file extensions found and possible errors encountered (e. g. files which could not be opened)
* [TIMESTAMP]_findings.csv: All results found during the tool's execution. This CSV file consists of the following three columns::
  * *match*: The string found
  * *file*: The path to the file in which the string was found
  * *type*: The type of string found (see above))
  * *ner_score*: Only for the AI-based search method: significance of the found match (self-assessed by the model)

Questions/Feedback/Patches
==========================

Feel free to submit any of these via openCode or direct them to the HBDI's sub-department 3.2 (technical data protection audits).

ToDo/Plans
==========

* i18n
* Support for identifying health insurance IDs (regex-based)
* Support for more file types
* Support for PDF files within embedded text (using OCR)
* Support for DOCX files that contain text in their header/footer/tables