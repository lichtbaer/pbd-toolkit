"""Property-based tests for the checksum validators.

The validators are the false-positive backbone of the structured PII types:
``--structured-validation`` drops IBAN / credit-card / BIC / tax-ID findings
from *every* engine when they fail here. They previously had no dedicated
tests. Each property generates values that are valid by construction (from
the published algorithm), asserts acceptance, then applies a single-character
mutation and asserts rejection where the algorithm guarantees detection.
"""

from __future__ import annotations

import re
import string

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from validators import get_validator
from validators.bic_validator import _VALID_COUNTRY_CODES, BicValidator
from validators.credit_card_validator import CreditCardValidator
from validators.iban_validator import IbanValidator
from validators.tax_id_validator import TaxIdValidator

# ---------------------------------------------------------------------------
# Reference implementations (independent of the code under test)
# ---------------------------------------------------------------------------


def _iban_numeric(s: str) -> int:
    return int("".join(str(ord(c) - 55) if c.isalpha() else c for c in s))


def _make_iban(country: str, bban: str) -> str:
    """Build a valid IBAN for *country* from its BBAN using ISO 13616."""
    check = 98 - _iban_numeric(bban + country + "00") % 97
    return f"{country}{check:02d}{bban}"


def _luhn_checksum_digit(payload: str) -> str:
    """Return the digit that makes ``payload + digit`` pass Luhn."""
    total = 0
    for i, ch in enumerate(reversed(payload)):
        n = int(ch)
        if i % 2 == 0:  # positions that get doubled once the check digit is appended
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - total % 10) % 10)


def _tax_id_check_digit(first_ten: list[int]) -> int:
    product = 10
    for d in first_ten:
        total = (d + product) % 10
        if total == 0:
            total = 10
        product = (total * 2) % 11
    return (11 - product) % 10


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_iban_countries = sorted(IbanValidator._IBAN_LENGTHS)


@st.composite
def valid_ibans(draw):
    country = draw(st.sampled_from(_iban_countries))
    length = IbanValidator._IBAN_LENGTHS[country]
    alphabet = string.digits + string.ascii_uppercase
    bban = draw(st.text(alphabet=alphabet, min_size=length - 4, max_size=length - 4))
    return _make_iban(country, bban)


@st.composite
def valid_card_numbers(draw):
    length = draw(st.integers(min_value=13, max_value=19))
    payload = draw(
        st.text(alphabet=string.digits, min_size=length - 1, max_size=length - 1)
    )
    assume(payload.strip("0"))  # all-zero numbers are degenerate
    return payload + _luhn_checksum_digit(payload)


@st.composite
def valid_tax_ids(draw):
    # Ten leading digits: nine distinct digits plus one repeat (or 8 + triple).
    digits = list(range(10))
    draw(st.randoms()).shuffle(digits)
    triple = draw(st.booleans())
    if triple:
        base = digits[:8]
        repeated = draw(st.sampled_from(base))
        first_ten = base + [repeated, repeated]
    else:
        base = digits[:9]
        repeated = draw(st.sampled_from(base))
        first_ten = base + [repeated]
    draw(st.randoms()).shuffle(first_ten)
    assume(first_ten[0] != 0)
    return "".join(map(str, first_ten)) + str(_tax_id_check_digit(first_ten))


_bic_countries = sorted(_VALID_COUNTRY_CODES)


@st.composite
def valid_bics(draw):
    bank = draw(st.text(alphabet=string.ascii_uppercase, min_size=4, max_size=4))
    country = draw(st.sampled_from(_bic_countries))
    alnum = string.ascii_uppercase + string.digits
    location = draw(st.text(alphabet=alnum, min_size=2, max_size=2))
    branch = draw(
        st.one_of(st.just(""), st.text(alphabet=alnum, min_size=3, max_size=3))
    )
    return bank + country + location + branch


# ---------------------------------------------------------------------------
# IBAN
# ---------------------------------------------------------------------------


class TestIbanProperties:
    @given(valid_ibans())
    @settings(max_examples=300)
    def test_generated_ibans_are_accepted(self, iban):
        assert IbanValidator.validate(iban)

    @given(valid_ibans())
    def test_spacing_and_case_are_normalised(self, iban):
        spaced = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
        assert IbanValidator.validate(spaced)
        assert IbanValidator.validate(iban.lower())

    @given(valid_ibans(), st.data())
    @settings(max_examples=300)
    def test_single_digit_change_is_rejected(self, iban, data):
        """Mod-97 detects every single-character substitution."""
        digit_positions = [i for i, c in enumerate(iban) if c.isdigit()]
        pos = data.draw(st.sampled_from(digit_positions))
        replacement = data.draw(
            st.sampled_from([d for d in string.digits if d != iban[pos]])
        )
        mutated = iban[:pos] + replacement + iban[pos + 1 :]
        assert not IbanValidator.validate(mutated)

    @given(valid_ibans(), st.data())
    def test_adjacent_digit_transposition_is_rejected(self, iban, data):
        """Mod-97 detects all adjacent transpositions of differing digits."""
        candidates = [
            i
            for i in range(4, len(iban) - 1)
            if iban[i].isdigit() and iban[i + 1].isdigit() and iban[i] != iban[i + 1]
        ]
        assume(candidates)
        i = data.draw(st.sampled_from(candidates))
        mutated = iban[:i] + iban[i + 1] + iban[i] + iban[i + 2 :]
        assert not IbanValidator.validate(mutated)

    @given(valid_ibans())
    def test_wrong_length_for_country_is_rejected(self, iban):
        assert not IbanValidator.validate(iban + "0")
        assert not IbanValidator.validate(iban[:-1])

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "DE",
            "DE89",
            "1234567890",
            "DE89 3704 0044 0532 0130 0!",
            "D389370400440532013000",
        ],
    )
    def test_structural_rejections(self, bad):
        assert not IbanValidator.validate(bad)

    def test_known_good_and_bad(self):
        assert IbanValidator.validate("DE89 3704 0044 0532 0130 00")
        assert IbanValidator.validate("GB82 WEST 1234 5698 7654 32")
        assert not IbanValidator.validate("DE89 3704 0044 0532 0130 01")


# ---------------------------------------------------------------------------
# Credit card (Luhn)
# ---------------------------------------------------------------------------


class TestLuhnProperties:
    @given(valid_card_numbers())
    @settings(max_examples=300)
    def test_generated_numbers_pass(self, number):
        assert CreditCardValidator.luhn_check(number)
        ok, _ = CreditCardValidator.validate(number)
        assert ok

    @given(valid_card_numbers(), st.data())
    @settings(max_examples=300)
    def test_single_digit_change_fails(self, number, data):
        pos = data.draw(st.integers(min_value=0, max_value=len(number) - 1))
        replacement = data.draw(
            st.sampled_from([d for d in string.digits if d != number[pos]])
        )
        mutated = number[:pos] + replacement + number[pos + 1 :]
        assert not CreditCardValidator.luhn_check(mutated)

    @given(valid_card_numbers(), st.data())
    def test_adjacent_transposition_fails_except_09_90(self, number, data):
        """Luhn catches every adjacent transposition except 09 <-> 90."""
        candidates = [
            i
            for i in range(len(number) - 1)
            if number[i] != number[i + 1] and {number[i], number[i + 1]} != {"0", "9"}
        ]
        assume(candidates)
        i = data.draw(st.sampled_from(candidates))
        mutated = number[:i] + number[i + 1] + number[i] + number[i + 2 :]
        assert not CreditCardValidator.luhn_check(mutated)

    @given(valid_card_numbers())
    def test_separators_are_ignored(self, number):
        grouped = "-".join(number[i : i + 4] for i in range(0, len(number), 4))
        assert CreditCardValidator.validate(grouped)[0]
        assert CreditCardValidator.normalize(grouped) == number

    @given(st.text(alphabet=string.digits, min_size=0, max_size=12))
    def test_too_short_is_rejected(self, digits):
        assert not CreditCardValidator.luhn_check(digits)
        assert CreditCardValidator.validate(digits) == (False, None)

    @given(st.text(alphabet=string.digits, min_size=20, max_size=30))
    def test_too_long_is_rejected(self, digits):
        assert CreditCardValidator.validate(digits) == (False, None)

    @pytest.mark.parametrize(
        "number,card_type",
        [
            ("4111111111111111", "visa"),
            ("5500000000000004", "mastercard"),
            ("340000000000009", "amex"),
            ("6011000000000004", "discover"),
            ("3530111333300000", "jcb"),
        ],
    )
    def test_known_test_numbers_and_types(self, number, card_type):
        assert CreditCardValidator.validate(number) == (True, card_type)

    def test_valid_luhn_but_unknown_scheme_has_no_type(self):
        payload = "9" * 15
        number = payload + _luhn_checksum_digit(payload)
        assert CreditCardValidator.validate(number) == (True, None)

    def test_non_digits_are_rejected(self):
        assert CreditCardValidator.validate("4111 1111 1111 111a") == (False, None)


# ---------------------------------------------------------------------------
# German tax ID (ISO 7064 MOD 11,10 + digit distribution)
# ---------------------------------------------------------------------------


class TestTaxIdProperties:
    @given(valid_tax_ids())
    @settings(max_examples=300)
    def test_generated_ids_are_accepted(self, tax_id):
        assert TaxIdValidator.validate(tax_id)

    @given(valid_tax_ids(), st.data())
    @settings(max_examples=300)
    def test_wrong_check_digit_is_rejected(self, tax_id, data):
        wrong = data.draw(
            st.sampled_from([d for d in string.digits if d != tax_id[-1]])
        )
        assert not TaxIdValidator.validate(tax_id[:-1] + wrong)

    @given(valid_tax_ids())
    def test_whitespace_is_ignored(self, tax_id):
        assert TaxIdValidator.validate(
            f"{tax_id[:2]} {tax_id[2:5]} {tax_id[5:8]} {tax_id[8:]}"
        )

    @given(st.permutations(list(string.digits)))
    def test_all_distinct_leading_digits_are_rejected(self, digits):
        """The rule requires exactly one repeated digit among the first ten."""
        prefix = "".join(digits)
        check = _tax_id_check_digit([int(c) for c in prefix])
        assert not TaxIdValidator.validate(prefix + str(check))

    def test_leading_zero_is_rejected(self):
        first_ten = [0, 1, 2, 3, 4, 5, 6, 7, 8, 1]
        tax_id = "".join(map(str, first_ten)) + str(_tax_id_check_digit(first_ten))
        assert not TaxIdValidator.validate(tax_id)

    @pytest.mark.parametrize(
        "bad", ["", "1234567890", "123456789012", "1234567890a", "11111111111"]
    )
    def test_structural_rejections(self, bad):
        assert not TaxIdValidator.validate(bad)


# ---------------------------------------------------------------------------
# BIC
# ---------------------------------------------------------------------------


class TestBicProperties:
    @given(valid_bics())
    @settings(max_examples=300)
    def test_generated_bics_are_accepted(self, bic):
        assert BicValidator.validate(bic)
        assert BicValidator.validate(f"  {bic.lower()} ")

    @given(valid_bics(), st.data())
    def test_unknown_country_is_rejected(self, bic, data):
        country = data.draw(
            st.text(alphabet=string.ascii_uppercase, min_size=2, max_size=2)
        )
        assume(country not in _VALID_COUNTRY_CODES)
        assert not BicValidator.validate(bic[:4] + country + bic[6:])

    @given(valid_bics(), st.data())
    def test_digit_in_bank_code_is_rejected(self, bic, data):
        pos = data.draw(st.integers(min_value=0, max_value=3))
        digit = data.draw(st.sampled_from(string.digits))
        assert not BicValidator.validate(bic[:pos] + digit + bic[pos + 1 :])

    @given(valid_bics())
    def test_wrong_lengths_are_rejected(self, bic):
        assert not BicValidator.validate(bic + "A")  # 9 or 12 chars
        assert not BicValidator.validate(bic[:7])

    def test_known_values(self):
        assert BicValidator.validate("DEUTDEFF")
        assert BicValidator.validate("DEUTDEFF500")
        assert not BicValidator.validate("DEUTZZFF")
        assert not BicValidator.validate("D3UTDEFF")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestValidatorRegistry:
    @pytest.mark.parametrize(
        "name,cls",
        [
            ("luhn", CreditCardValidator),
            ("iban", IbanValidator),
            ("tax_id", TaxIdValidator),
            ("bic", BicValidator),
        ],
    )
    def test_known_validators_resolve_and_are_cached(self, name, cls):
        assert get_validator(name) is cls
        assert get_validator(name) is cls

    def test_unknown_validator_returns_none(self):
        assert get_validator("does-not-exist") is None

    def test_import_failure_is_cached_as_none(self, monkeypatch):
        import validators as pkg

        monkeypatch.setitem(pkg._VALIDATOR_REGISTRY, "broken", "validators.nope.Nope")
        monkeypatch.delitem(pkg._loaded_validators, "broken", raising=False)
        assert get_validator("broken") is None
        assert pkg._loaded_validators["broken"] is None

    def test_every_registered_validator_exposes_validate(self):
        import validators as pkg

        for name in pkg._VALIDATOR_REGISTRY:
            cls = get_validator(name)
            assert cls is not None and callable(cls.validate)
            assert re.match(r"^[a-z_]+$", name)
