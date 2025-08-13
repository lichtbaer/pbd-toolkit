from enum import StrEnum
import re
from dataclasses import dataclass


""" Class for holding a singular found PII match.

    An __init__ method is implied by the @dataclass decorator. """
@dataclass
class PiiMatch:
    # The text that represents PII
    text: str
    # The file in which the represented PII was found
    file: str

    class PiiMatchType(StrEnum):
        REGEX_RVNR = "RegEx: Rentenversicherungsnummer"
        REGEX_IBAN = "RegEx: IBAN"
        REGEX_EMAIL = "RegEx: E-Mail-Adresse"
        REGEX_IPV4 = "RegEx: IPv4-Adresse"
        REGEX_WORDS = "RegEx: spezielle Wörter"
        REGEX_PGPPRV = "RegEx: privater PGP-Schlüssel"
        NER_PERSON = "KI-NER: Person"
        NER_LOCATION = "KI-NER: Ort"
        NER_HEALTH = "KI-NER: Gesundheitsdaten (exp.)"
        NER_PASSWORD = "KI-NER: Passwörter (exp.)"

    # The type of PII found. Only types explicitly supported by this application are valid.
    type: PiiMatchType
    # Only for PII found via AI-assisted NER: The likelihood with which a PII string represents a specific PII type, self-assessed by the model used.
    ner_score: float | None = None


""" Class for holding all PII matches found. The aim is to provide helpful functions for processing
    and managing these matches.

    An __init__ method is implied by the @dataclass decorator. """
@dataclass
class PiiMatchContainer:
    pii_matches: list[PiiMatch] = []
    # Whitelist used for excluding strings from being identified as PII
    whitelist: list[str] = []

    """ Helper function for adding matches to the matches container. This generic, internal method is
        called by the other methods intended for public use, its aim is to reduce redundancy. """
    def __add_match(self, text: str, file: str, type: PiiMatch.PiiMatchType, ner_score: float | None = None) -> None:
            whitelisted: bool = False

            # TODO: performance could be improved by creating a regex from the whitelist entries and matching against that.
            # That way, no loop would be necessary.
            for word in self.whitelist:
                if word in text:
                    whitelisted = True
                    break;
            
            if whitelisted == False:
                pm: PiiMatch = PiiMatch(text=text, file=file, type=type, ner_score=ner_score)
                self.pii_matches.append(pm)

    """ Helper function for adding regex-based matches to the matches container. """
    def add_matches_regex(self, matches: re.Match | None, path: str) -> None:
        if matches is not None:
            type: PiiMatch.PiiMatchType | None = None

            """ Since we use a concatenated regex that contains multiple types of checks (e. g. bank account, email all in one)
                for efficiency reasons, we now have to figure out exactly which type of match it actually is. This is only possible
                by looking at the position of the group storing the match within the overall regex. """
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
            elif matches.groups()[5] is not None:
                type = PiiMatch.PiiMatchType.REGEX_PGPPRV

            self.__add_match(text=matches.group(), file=path, type=type)


    """ Helper function for adding AI-based NER matches to the matches container. """
    def add_matches_ner(self, matches, path: str) -> None:
        if matches is not None:
            for match in matches:
                type: PiiMatch.PiiMatchType | None = None

                if match["label"] == "Person's Name":
                    type = PiiMatch.PiiMatchType.NER_PERSON
                elif match["label"] == "Location":
                    type = PiiMatch.PiiMatchType.NER_LOCATION
                elif match["label"] == "Health Data":
                    type = PiiMatch.PiiMatchType.NER_HEALTH
                elif match["label"] == "Password":
                    type = PiiMatch.PiiMatchType.NER_PASSWORD

                self.__add_match(text=match["text"], file=path, type=type, ner_score=match["score"])