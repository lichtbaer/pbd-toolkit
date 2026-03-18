"""IBAN validation using the ISO 13616 check digit algorithm (modulo 97)."""

import re


class IbanValidator:
    """Validates International Bank Account Numbers using the modulo-97 check."""

    # ISO 3166-1 alpha-2 country codes that use IBAN
    _IBAN_LENGTHS: dict[str, int] = {
        "AL": 28, "AD": 24, "AT": 20, "AZ": 28, "BH": 22, "BY": 28,
        "BE": 16, "BA": 20, "BR": 29, "BG": 22, "CR": 22, "HR": 21,
        "CY": 28, "CZ": 24, "DK": 18, "DO": 28, "TL": 23, "EE": 20,
        "FO": 18, "FI": 18, "FR": 27, "GE": 22, "DE": 22, "GI": 23,
        "GR": 27, "GL": 18, "GT": 28, "HU": 28, "IS": 26, "IQ": 23,
        "IE": 22, "IL": 23, "IT": 27, "JO": 30, "KZ": 20, "XK": 20,
        "KW": 30, "LV": 21, "LB": 28, "LI": 21, "LT": 20, "LU": 20,
        "MK": 19, "MT": 31, "MR": 27, "MU": 30, "MC": 27, "MD": 24,
        "ME": 22, "NL": 18, "NO": 15, "PK": 24, "PS": 29, "PL": 28,
        "PT": 25, "QA": 29, "RO": 24, "SM": 27, "SA": 24, "RS": 22,
        "SC": 31, "SK": 24, "SI": 19, "ES": 24, "SE": 24, "CH": 21,
        "TN": 24, "TR": 26, "UA": 29, "AE": 23, "GB": 22, "VA": 22,
        "VG": 24,
    }

    @staticmethod
    def validate(iban: str) -> bool:
        """Validate an IBAN using the modulo-97 algorithm.

        Args:
            iban: IBAN string (may contain spaces).

        Returns:
            True if the IBAN is valid.
        """
        # Normalize: remove spaces and convert to uppercase
        cleaned = re.sub(r"\s", "", iban).upper()

        # Must be at least 5 chars (2-letter country + 2-digit check + 1 BBAN char)
        if len(cleaned) < 5:
            return False

        country = cleaned[:2]
        if not country.isalpha():
            return False

        # Validate country-specific length if known
        if country in IbanValidator._IBAN_LENGTHS:
            if len(cleaned) != IbanValidator._IBAN_LENGTHS[country]:
                return False

        # Modulo 97 check (ISO 13616):
        # 1. Move first 4 chars to end
        rearranged = cleaned[4:] + cleaned[:4]

        # 2. Replace letters with two-digit numbers (A=10, B=11, ..., Z=35)
        numeric_str = ""
        for ch in rearranged:
            if ch.isdigit():
                numeric_str += ch
            elif ch.isalpha():
                numeric_str += str(ord(ch) - ord("A") + 10)
            else:
                return False

        # 3. Compute remainder mod 97
        try:
            return int(numeric_str) % 97 == 1
        except (ValueError, OverflowError):
            return False
