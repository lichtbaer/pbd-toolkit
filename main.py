import datetime
import gettext
import json
import mimetypes
import os
import re

import docx
import docx.opc
import docx.opc.exceptions
import docx.text
import docx.text.paragraph
import setup
from bs4 import BeautifulSoup
from gliner import GLiNER
import globals
from matches import PiiMatchContainer
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

lstr: str = os.environ.get("LANGUAGE")
lenv = lstr if lstr and lstr in ["de", "en"] else "de"

lang = gettext.translation("base", localedir="locales", languages=[lenv])
lang.install()
_ = lang.gettext


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
with open("config_types.json") as f:
    config = json.load(f)

regex = config["regex"]
regex_supported = []

for entry in regex:
    regex_supported.append(r"{}".format(entry["expression"]))

# concatenate all regex strings so that we can scan each document just once instead of once per regex
rxstr_all: str = "(" + ")|(".join(regex_supported) + ")"
regex_all: re.Pattern = re.compile(rxstr_all)

pmc: PiiMatchContainer = PiiMatchContainer()

# Used to list all entities for AI-based NER
ner_labels: list[str] = []

# TODO: move more stuff to globals
setup.setup()

if not globals.args.path:
    exit(_("--path parameter cannot be empty"))

if not globals.args.ner and not globals.args.regex:
    exit(_("Regex- and/or NER-based analysis must be turned on."))

if globals.args.ner == True:
    model: GLiNER = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")

    import json
    with open("config_types.json") as f:
        config = json.load(f)

    ner_labels = [c["term"] for c in config["ai-ner"]]

if globals.args.whitelist and os.path.isfile(globals.args.whitelist):
    with open(globals.args.whitelist, "r") as file:
        pmc.whitelist = file.read().splitlines()

time_start: datetime.datetime = datetime.datetime.now()
time_end: datetime.datetime
time_diff: datetime.timedelta

globals.logger.info(_("Analysis"))
globals.logger.info("====================\n")
globals.logger.info(_("Analysis started at {}\n").format(time_start))

if globals.args.regex == True:
    globals.logger.info(_("Regex-based search is active."))
else:
    globals.logger.info(_("Regex-based search is *not* active."))

if globals.args.ner == True:
    globals.logger.info(_("AI-based search is active."))
else:
    globals.logger.info(_("AI-based search is *not* active."))

globals.logger.info("\n")

# Number of files found during analysis
num_files_all: int = 0
# Number of files actually analyzed (supported file extension)
num_files_checked: int = 0

# walk all files and subdirs of the root path
for root, dirs, files in os.walk(globals.args.path):
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

                            """ Workaround for PDFs with messed-up text embeddings that only
                                consist of very short character sequences """
                            if len(text) < 10:
                                continue
                            else:
                                if globals.args.regex == True:
                                    matches: re.Match = regex_all.search(text)
                                    pmc.add_matches_regex(matches, full_path)

                                if globals.args.ner == True:
                                    entities = model.predict_entities(text, ner_labels, threshold=0.5)
                                    pmc.add_matches_ner(entities, full_path)

                num_files_checked += 1
            except Exception as excpt:
                add_error(str(excpt), full_path)
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

                    if globals.args.regex == True:
                        matches: re.Match = regex_all.search(text)
                        pmc.add_matches_regex(matches, full_path)

                    if globals.args.ner == True:
                        entities = model.predict_entities(text, ner_labels, threshold=0.5)
                        pmc.add_matches_ner(entities, full_path)
            except docx.opc.exceptions.PackageNotFoundError:
                add_error("DOCX Empty Or Protected", full_path)
            except Exception as excpt:
                add_error(str(excpt), full_path)
        elif ext == ".html":
            """ For HTML files, we use BeautifulSoup4 to extract the text without markup. """
            with open(full_path) as doc:
                try:
                    soup: BeautifulSoup = BeautifulSoup(doc, "html.parser")
                    num_files_checked += 1

                    text: str = soup.get_text()

                    if globals.args.regex == True:
                        matches: re.Match = regex_all.search(text)
                        pmc.add_matches_regex(matches, full_path)

                    if globals.args.ner == True:
                        entities = model.predict_entities(text, ner_labels, threshold=0.5)
                        pmc.add_matches_ner(entities, full_path)
                except UnicodeDecodeError:
                    add_error("HTML Unicode Decode Error", full_path)
        elif (ext == ".txt" or ext == "") and mimetypes.guess_type(full_path) == "text/plain":
            with open(full_path) as doc:
                try:
                    text: str = doc.read()

                    if globals.args.regex == True:
                        matches: re.Match = regex_all.search(text)
                        pmc.add_matches_regex(matches, full_path)

                    if globals.args.ner == True:
                        entities = model.predict_entities(text, ner_labels, threshold=0.5)
                        pmc.add_matches_ner(entities, full_path)
                except Exception as excpt:
                    add_error(str(excpt), full_path)

        if globals.args.stop_count and num_files_all == globals.args.stop_count:
            break
    if globals.args.stop_count and num_files_all == globals.args.stop_count:
        break

time_end = datetime.datetime.now()
time_diff = time_end - time_start

""" Output all results. """
globals.logger.info(_("Statistics"))
globals.logger.info("----------\n")
globals.logger.info(_("The following file extensions have been found:"))
[globals.logger.info("{:>10}: {:>10} Dateien".format(k, v)) for k, v in sorted(exts_found.items(), key=lambda item: item[1], reverse=True)]
globals.logger.info(_("TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n").format(num_files_all, num_files_checked))

globals.logger.info(_("Findings"))
globals.logger.info("--------\n")
globals.logger.info(_("--> see *_findings.csv\n\n"))

globals.logger.info(_("Errors"))
globals.logger.info("------\n")
for k, v in errors.items():
    globals.logger.info("\t{}".format(k))
    for f in v:
        globals.logger.info("\t\t{}".format(f.encode("utf-8", "replace")))

globals.logger.info("\n")
globals.logger.info(_("Analysis finished at {}").format(time_end))
globals.logger.info(_("Performance of analysis: {} analyzed files per second").format(round(num_files_checked / max(time_diff.seconds, 1), 2)))
