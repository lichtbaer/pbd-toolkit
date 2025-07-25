import argparse
import re
import os
import csv
import zipfile
import docx
import docx.opc
import docx.opc.exceptions
import docx.text
import docx.text.paragraph
import pdfminer
from pdfminer.layout import LTTextContainer
from pdfminer.high_level import extract_pages
import datetime
from enum import StrEnum
from bs4 import BeautifulSoup

""" Class for holding a singular found PII match.
"""
class PiiMatch:
    text: str
    file: str

    class PiiMatchType(StrEnum):
        REGEX_RVNR = "RegEx: Rentenversicherungsnummer"
        REGEX_IBAN = "RegEx: IBAN"
        REGEX_EMAIL = "RegEx: E-Mail-Adresse"
        REGEX_IPV4 = "RegEx: IPv4-Adresse"
        REGEX_WORDS = "RegEx: spezielle Wörter"

    type: PiiMatchType

    def __init__(self, text: str, file: str, type: PiiMatchType):
        self.text = text
        self.file = file
        self.type = type


""" Class for holding all PII matches found. The aim is to provide helpful functions for processing
    these matches, for example outputting them in groups by different criteria.

    This functionality isn't actually used at the moment. """
class PiiMatchContainer:
    pii_matches: list[PiiMatch] | None

    def __init__(self):
        self.pii_matches = []

    def by_file(self) -> dict[str, list[PiiMatch]]:
        files: list[str] = []
        files = [pm.file for pm in self.pii_matches if pm.file not in files]
        files_to_pms: dict[str, list[PiiMatch]] = {}

        for pm in self.pii_matches:
            if pm.file not in files_to_pms.keys():
                files_to_pms[pm.file] = [pm]
            else:
                files_to_pms[pm.file].append(pm)

        return files_to_pms

    def by_text() -> dict[str, list[PiiMatch]]:
        pass

""" Used to count how many files per extension have been found. This does *not* only count supported/qualified
    extensions but all of the ones contained in the root directory searched.
    Example: {".pdf": 42} indicates that there were 42 files with the extension ".pdf" in the root directory
    and its subdirectories. """
exts_found: dict[str, int] = {}

""" Used to hold information about special occurrences during analysis, such as files that could not be
    read due to an access violation or data corruption. The key contains the type of error, the value
    contains all files that produced that error.
    Example: { "file is password protected": ["a.pdf", "b.docx"]}"""
errors: dict[str, list[str]] = {}

""" Helper function for adding errors to the above dict without duplicating this branch all over the code. """
def add_error(msg: str, path: str) -> None:
    if msg not in errors.keys():
        errors[msg] = [path]
    else:
        errors[msg].append(path)

# All regular expressions used for analysis.
""" Regular expression for German Rentenversicherungsnummern (public pension insurance identity number).
    It consists of:
      * Word boundary
      * Two digits identifying the insurance provider, zero-padded (value range of [02, 89])
      * Day of birth of the insured person, zero-padded (value range of [01, 31])
      * Month of birth of the insured person, zero-padded (value range of [01, 12])
      * Year of birth of the insured person, last two digits (value range of [00, 99])
      * First letter of the insured person's first name (value range of [A, Z])
      * Two digits identifying the insured person's gender, zero-padded (value range of [00, 99])
      * One digit for integrity checking (value range of [0, 9])
      * Word boundary
    Example: 15070649C103 """
rxstr_rvnr: str = r"\b[0-8][0-9][0-3][0-9][0-1][0-9]{3}[A-Z][0-9]{3}\b"
""" Regular expression for IBAN banking account numbers. This is somewhat specific (but not absolutely exclusive)
    for German banking accounts.
    Consists of:
      * Word boundary
      * Two letters identifying the country
      * Two digits for integrity checking
      * Four sets of four digits which may optionally be separated by spaces from each other
        and other elements
      * One or two digits
      * Word boundary
    Example: DE11 2003 8978 4565 1232 00"""
rxstr_iban: str = r"\b[A-Z]{2}[0-9]{2}(?:[ ]?[0-9]{4}){4}(?:[ ]?[0-9]{1,2})?\b"
""" Regular expression for email addresses. Doesn't conform to the RFC and thus doesn't cover every single
    possible valid address but is intended as a "good enough" solution.
    Consists of:
      * Word boundary
      * A non-zero amount of word characters or dashes (-) or dots (.)
      * An at character (@)
      * A non-zero amount of word characters or dashes or dots which ends with one dot
      * Two to ten word characters
      * Word boundary
    Example: test@example.com """
rxstr_mail: str = r"\b[\w\-\.]+@(?:[\w+\-]+\.)+\w{2,10}\b"
""" Regular expression for IPv4 addresses
    Consists of:
      * Word boundary
      * Four groups of one to three digits in the range of [0, 255] which may optionally
        be zero-padded to three digits
      * Word boundary
    Example: 123.123.123.123 """
rxstr_ipv4: str = r"\b(?:(?:25[0-5]|(?:2[0-4]|1\d|[1-9]|)\d)\.?\b){4}\b"
""" Regular expression for special words that frequently appear in the context of
    personally-identifiable information """
rxstr_words: str = r"\b(?:Abmahnung|Bewerbung|Zeugnis|Entwicklungsbericht|Gutachten|Krankmeldung)\b"

# concatenate all regex strings so that we can scan each document just once instead of once per regex
rxstr_all: str = "(" + rxstr_rvnr + ")|(" + rxstr_iban + ")|(" + rxstr_mail + ")|(" + rxstr_ipv4 + ")|(" + rxstr_words + ")"
regex_all: re.Pattern = re.compile(rxstr_all)

pmc: PiiMatchContainer = PiiMatchContainer()

""" Helper function for adding matches to the matches container.
    Since we use a concatenated regex that contains multiple types of checks (e. g. bank account, email all in one)
    for efficiency reasons, we now have to figure out exactly which type of match it actually is."""
def add_matches(matches: re.Match | None, path: str) -> None:
    if matches is not None:
        type: PiiMatch.PiiMatchType | None = None

        if matches.groups()[0] is not None:
            type = PiiMatch.PiiMatchType.REGEX_RVNR
        elif matches.groups()[1] is not None:
            type = PiiMatch.PiiMatchType.REGEX_IBAN
        elif matches.groups()[2] is not None:
            type = PiiMatch.PiiMatchType.REGEX_EMAIL
        elif matches.groups()[3] is not None:
            type = PiiMatch.PiiMatchType.REGEX_IPV4
        elif matches.groups()[4] is not None:
            type = PiiMatch.PiiMatchType.REGEX_WORDS

        pm: PiiMatch = PiiMatch(text=matches.group(), file=path, type=type)
        pmc.pii_matches.append(pm)

parser = argparse.ArgumentParser(prog="HBDI-pbD-Toolkit")
parser.add_argument("--path", action="store", help="Stammpfad, der mit allen Unterverzeichnissen auf pbD überprüft werden soll")
parser.add_argument("--outname", action="store", help="optionaler Parameter, die hier angegebene Zeichenkette wird zur Benennung der erzeugten Output-Dateien verwendet")
args = parser.parse_args()

if args.path is None:
    exit("--path-Parameter kann nicht leer sein")

# construct name for output files. Default is date/time, optionally with the value from args.outname
outslug: str = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")

if args.outname is not None:
    outslug += " " + args.outname

# log all significant operations and findings
with open("./output/" + outslug + "_log.txt", "wt") as file_log:
    file_log.write("RegEx-Analyse\n")
    file_log.write("====================\n\n")
    file_log.write("Analyse gestartet um {}\n\n\n".format(datetime.datetime.now()))

    # if the file isn't flushed it would show up empty when opened during an ongoing analysis
    file_log.flush()

    # Number of files found during analysis
    num_files_all: int = 0
    # Number of files actually analyzed (supported file extension)
    num_files_checked: int = 0

    # walk all files and subdirs of the root path
    for root, dirs, files in os.walk(args.path):
        for filename in files:
            num_files_all += 1

            full_path: str = os.path.join(root, filename)
            ext: str = os.path.splitext(full_path)[1].lower()

            # keep count of how many files have been found per extension
            if ext not in exts_found.keys():
                exts_found[ext] = 1
            else:
                exts_found[ext] += 1

            print(str(num_files_all) + " " + full_path)

            # handle all file extensions that we want to support
            """ For PDF files, text is extracted from all pages using the pdfminer.six library.
                This currently only works for PDF files which have actual text embeddings. If a file
                contains images (for example from scanning a document without applying OCR), then
                no text will be extracted."""
            if ext == ".pdf":
                try:
                    # extract text page by page since that's not too memory-intensive
                    for page_layout in extract_pages(full_path):
                        for text_container in page_layout:
                            if isinstance(text_container, LTTextContainer):
                                text: str = text_container.get_text()

                                matches: re.Match = regex_all.search(text)
                                add_matches(matches, full_path)

                    num_files_checked += 1
                except pdfminer.psexceptions.PSEOF:
                    add_error("PDF Unexpected EOF", full_path)
                except pdfminer.pdfparser.PDFSyntaxError:
                    add_error("PDF Malformed PDF", full_path)
                except pdfminer.pdfdocument.PDFPasswordIncorrect:
                    add_error("PDF Password Protected", full_path)
                except Exception:
                    add_error("PDF Misc Exception", full_path)
            elif ext == ".docx":
                """ For DOCX files, we extract text using python-docx. Currently, this only takes a document's
                    paragraphs into account, with no regard for elements that aren't paragraphs (headers, footers, tables)."""
                try:
                    doc: docx.Document = docx.Document(full_path)
                    num_files_checked += 1

                    text: str = ""

                    paragraph: docx.text.paragraph
                    for paragraph in doc.paragraphs:
                        text += paragraph.text
                        matches: re.Match = regex_all.search(text)

                        add_matches(matches, full_path)
                except docx.opc.exceptions.PackageNotFoundError:
                    add_error("DOCX Empty Or Protected", full_path)
                except KeyError:
                    add_error("DOCX Corrupt Or Bad Data Structure", full_path)
                except zipfile.BadZipFile:
                    add_error("DOCX Bad Zip File", full_path)
            elif ext == ".html":
                """ For HTML files, we use BeautifulSoup4 to extract the text without markup. """
                with open(full_path) as doc:
                    try:
                        soup: BeautifulSoup = BeautifulSoup(doc, "html.parser")
                        num_files_checked += 1

                        text: str = soup.get_text()
                        matches: re.Match = regex_all.search(text)

                        add_matches(matches, full_path)
                    except UnicodeDecodeError:
                        add_error("HTML Unicode Decode Error", full_path)


    """ Output all results. """
    file_log.write("Statistiken\n")
    file_log.write("----------\n\n")
    file_log.write("Folgende Dateiendungen wurden gefunden:\n")
    [file_log.write("{:>10}: {:>10} Dateien\n".format(k, v)) for k, v in sorted(exts_found.items(), key=lambda item: item[1], reverse=True)]
    file_log.write("GESAMT: {} Dateien.\nQUALIFIZIERT: {} Dateien (unterstützte Dateiendungen)\n\n\n".format(num_files_all, num_files_checked))

    file_log.write("Funde\n")
    file_log.write("--------\n\n")
    """for k, v in pmc.by_file().items():
            file_log.write("\t{}\n".format(k))
            for f in v:
                file_log.write("\t\t{}\n".format(f.text))
    file_log.write("\n\n")"""
    file_log.write("--> siehe *_findings.csv\n\n\n")

    file_log.write("Fehler\n")
    file_log.write("------\n\n")
    for k, v in errors.items():
        file_log.write("\t{}\n".format(k))
        for f in v:
            file_log.write("\t\t{}\n".format(f.encode("utf-8", "replace")))

    file_log.write("\n\n")
    file_log.write("Analyse abgeschlossen um {}\n".format(datetime.datetime.now()))

with open("./output/" + outslug + "_findings.csv", "w") as csvfile:
    csvwriter = csv.writer(csvfile)
    csvwriter.writerow(["match", "file", "type"])

    for pm in pmc.pii_matches:
        csvwriter.writerow([pm.text, pm.file, pm.type.value])
