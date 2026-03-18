"""German Tax ID (Steuerliche Identifikationsnummer) validation.

The German Tax ID is an 11-digit number with a check digit computed using
ISO/IEC 7064, MOD 11,10.  Additionally, exactly one digit must appear twice
(or one digit three times) while the remaining digits are distinct.
"""

import re


class TaxIdValidator:
    """Validates German Tax Identification Numbers (Steuer-ID)."""

    @staticmethod
    def validate(tax_id: str) -> bool:
        """Validate a German Tax ID.

        Args:
            tax_id: 11-digit string.

        Returns:
            True if the Tax ID passes structural and check-digit validation.
        """
        cleaned = re.sub(r"\s", "", tax_id)

        if len(cleaned) != 11 or not cleaned.isdigit():
            return False

        # First digit must not be 0
        if cleaned[0] == "0":
            return False

        digits = [int(d) for d in cleaned]

        # Digit distribution check: among the first 10 digits, exactly one digit
        # must appear exactly twice (or one digit exactly three times), and the
        # rest must be unique. This means at most one digit is repeated.
        from collections import Counter

        freq = Counter(digits[:10])
        counts = sorted(freq.values(), reverse=True)
        # Valid distributions:
        #   [2, 1, 1, 1, 1, 1, 1, 1, 1] – one digit twice, 9 unique
        #   [3, 1, 1, 1, 1, 1, 1, 1]     – one digit three times, 8 unique
        if counts[0] not in (2, 3):
            return False
        if any(c > 1 for c in counts[1:]):
            return False

        # Check digit validation (ISO/IEC 7064, MOD 11,10)
        product = 10
        for i in range(10):
            total = (digits[i] + product) % 10
            if total == 0:
                total = 10
            product = (total * 2) % 11

        check_digit = (11 - product) % 10
        return check_digit == digits[10]
