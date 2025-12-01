import re
from dataclasses import dataclass, field
from typing import Any
import json
import globals

# configure support match types
with open("config_types.json") as f:
    config = json.load(f)

config_ainer = config["ai-ner"]
config_regex = config["regex"]

config_regex_sorted: dict[str, dict] = {}

""" Since we use a concatenated regex that contains multiple types of checks (e. g. bank account, email all in one)
    for efficiency reasons, we now have to figure out exactly which type of match it actually is. This is only possible
    by looking at the position of the group storing the match within the overall regex.
    Sort the regex configuration by position accordingly. """

for conf in config_regex:
    config_regex_sorted[conf["regex_compiled_pos"]] = conf

""" And sort the AI NER configuration by matching terms. """
config_ainer_sorted: dict[str, dict] = {}

for conf in config_ainer:
    config_ainer_sorted[conf["term"]] = conf

""" Class for holding a singular found PII match.

    An __init__ method is implied by the @dataclass decorator. """
@dataclass
class PiiMatch:
    # The text that represents PII
    text: str
    # The file in which the represented PII was found
    file: str
    # The type of PII found. Only types explicitly supported by this application are valid.
    type: str
    # Only for PII found via AI-assisted NER: The likelihood with which a PII string represents a specific PII type, self-assessed by the model used.
    ner_score: float | None = None


""" Class for holding all PII matches found. The aim is to provide helpful functions for processing
    and managing these matches.

    An __init__ method is implied by the @dataclass decorator. """
@dataclass
class PiiMatchContainer:
    pii_matches: list[PiiMatch] = field(default_factory=list)
    # Whitelist used for excluding strings from being identified as PII
    whitelist: list[str] = field(default_factory=list)
    # Compiled regex pattern for efficient whitelist matching
    _whitelist_pattern: re.Pattern | None = field(default=None, init=False, repr=False)
    # CSV writer for output (injected dependency)
    _csv_writer: Any = field(default=None, init=False, repr=False)
    
    def set_csv_writer(self, csv_writer: Any) -> None:
        """Set the CSV writer for output.
        
        Args:
            csv_writer: CSV writer instance
        """
        self._csv_writer = csv_writer

    def by_file(self) -> dict[str, list[PiiMatch]]:
        """Group PII matches by file path.
        
        Returns:
            Dictionary mapping file paths to lists of PiiMatch objects found in each file.
        """
        results: dict[str, list[PiiMatch]] = {}

        for pm in self.pii_matches:
            if pm.file in results.keys():
                results[pm.file].append(pm)
            else:
                results[pm.file] = [pm]

        return results

    def _compile_whitelist_pattern(self) -> None:
        """Compile whitelist entries into a regex pattern for efficient matching."""
        if self.whitelist and self._whitelist_pattern is None:
            # Escape special regex characters and create pattern
            escaped_patterns = [re.escape(word) for word in self.whitelist if word]
            if escaped_patterns:
                self._whitelist_pattern = re.compile("|".join(escaped_patterns))

    """ Helper function for adding matches to the matches container. This generic, internal method is
        called by the other methods intended for public use, its aim is to reduce redundancy. """
    def __add_match(self, text: str, file: str, type: str, ner_score: float | None = None) -> None:
            whitelisted: bool = False

            # Use compiled regex pattern for efficient whitelist checking
            if self.whitelist:
                if self._whitelist_pattern is None:
                    self._compile_whitelist_pattern()
                if self._whitelist_pattern and self._whitelist_pattern.search(text):
                    whitelisted = True

            if not whitelisted:
                pm: PiiMatch = PiiMatch(text=text, file=file, type=type, ner_score=ner_score)
                self.pii_matches.append(pm)
                if self._csv_writer:
                    self._csv_writer.writerow([pm.text, pm.file, pm.type, pm.ner_score])

    """ Helper function for adding regex-based matches to the matches container. """
    def add_matches_regex(self, matches: re.Match | None, path: str) -> None:
        if matches is not None:
            type: str | None = None

            for idx, item in enumerate(matches.groups()):
                if item is not None:
                    type = config_regex_sorted[idx]["label"]

            self.__add_match(text=matches.group(), file=path, type=type)


    """ Helper function for adding AI-based NER matches to the matches container. """
    def add_matches_ner(self, matches: list[dict] | None, path: str) -> None:
        if matches is not None:
            for match in matches:
                type: str | None = None

                type = config_ainer_sorted[match["label"]]["label"]

                self.__add_match(text=match["text"], file=path, type=type, ner_score=match["score"])
