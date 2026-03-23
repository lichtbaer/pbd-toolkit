"""Validation utilities for PII detection."""

import importlib

from validators.credit_card_validator import CreditCardValidator

__all__ = ["CreditCardValidator", "get_validator"]

# Lazy-loading validator registry: maps validation_type -> dotted import path
_VALIDATOR_REGISTRY: dict[str, str] = {
    "luhn": "validators.credit_card_validator.CreditCardValidator",
    "iban": "validators.iban_validator.IbanValidator",
    "tax_id": "validators.tax_id_validator.TaxIdValidator",
    "bic": "validators.bic_validator.BicValidator",
}

_loaded_validators: dict[str, type | None] = {}


def get_validator(validation_type: str) -> type | None:
    """Get a validator class by type name. Returns None if not available.

    Validators are lazily imported and cached on first access. If the
    underlying module is not installed, ``None`` is cached to avoid
    repeated import attempts.

    Args:
        validation_type: Key from ``_VALIDATOR_REGISTRY`` (e.g. "luhn").

    Returns:
        Validator class with a ``validate()`` static method, or ``None``.
    """
    if validation_type in _loaded_validators:
        return _loaded_validators[validation_type]

    dotted_path = _VALIDATOR_REGISTRY.get(validation_type)
    if dotted_path is None:
        return None

    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _loaded_validators[validation_type] = cls
        return cls
    except (ImportError, AttributeError):
        _loaded_validators[validation_type] = None  # cache the miss
        return None
