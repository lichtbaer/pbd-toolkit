"""Internationalization (i18n) helpers for the pbd-toolkit CLI.

The active locale is selected via the ``LANGUAGE`` environment variable at
the time :func:`get_translator` is called (not cached at import time), so
each CLI invocation picks up the current environment. Only ``de`` selects
the German catalog; any other value (including unset or an unsupported
locale such as ``fr``) falls back to English.
"""

import gettext
import os
from collections.abc import Callable
from pathlib import Path

SUPPORTED_LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "en"
_LOCALE_DIR = str(Path(__file__).resolve().parent.parent / "locales")


def resolve_language() -> str:
    """Resolve the active language code from the ``LANGUAGE`` env var.

    Returns:
        ``"de"`` if ``LANGUAGE=de`` is set; ``"en"`` in every other case
        (unset, empty, or an unsupported value).
    """
    lstr = os.environ.get("LANGUAGE")
    return lstr if lstr in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_translator(language: str | None = None) -> Callable[[str], str]:
    """Build a gettext translation function for the given (or active) language.

    Args:
        language: Explicit language code (``"de"`` or ``"en"``). Defaults to
            :func:`resolve_language` when omitted.

    Returns:
        A callable that translates a message id into the target language,
        falling back to the original string if no catalog is found.
    """
    lang_code = language if language in SUPPORTED_LANGUAGES else resolve_language()
    try:
        translation = gettext.translation(
            "base", localedir=_LOCALE_DIR, languages=[lang_code]
        )
    except OSError:
        return lambda message: message
    return translation.gettext
