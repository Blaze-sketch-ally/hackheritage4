"""Centralized language registry for the multilingual architecture
(Milestone 1).

This is the SINGLE source of truth for which languages the application
knows about. It is mirrored field-for-field by
frontend/lib/i18n/languages.ts -- kept in sync by a parity test
(tests/test_language_registry.py). Never scatter language checks
(`if code == "hi": ...`) through the application; add or adjust a
language here instead.

Two independent flags, deliberately not conflated:

  * `enabled` -- whether the language has a static UI dictionary and can
    be chosen in the language selector. Milestone 1 enables exactly
    en/hi/bn; the other ten languages are registered (so adding one
    later is configuration-only, never an architecture change) but not
    yet selectable.

  * `capabilities` -- whether the REAL, configured BHASHINI pipeline has
    been verified to support that language for that task. As of this
    milestone no BHASHINI credentials/pipeline have been configured or
    verified against the live API (see
    docs/architecture/multilingual-architecture.md), so every
    capability below is False for every language, including en/hi/bn.
    `TRANSLATION_PROVIDER=mock` is what makes dynamic-content
    translation work in this milestone regardless of these flags --
    flip a capability to True only after verifying that exact
    (language, task) pair against the actual BHASHINI account/pipeline,
    never speculatively.
"""

from dataclasses import dataclass, field
from typing import Literal

LanguageCode = Literal[
    "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur"
]

Direction = Literal["ltr", "rtl"]


@dataclass(frozen=True)
class LanguageCapabilities:
    """Real BHASHINI infrastructure support for one language -- see this
    module's own docstring for why every field defaults to False."""

    translation: bool = False
    speech_to_text: bool = False
    text_to_speech: bool = False
    transliteration: bool = False


@dataclass(frozen=True)
class LanguageDefinition:
    code: LanguageCode
    name: str
    native_name: str
    locale: str
    direction: Direction
    enabled: bool
    capabilities: LanguageCapabilities = field(default_factory=LanguageCapabilities)


LANGUAGES: tuple[LanguageDefinition, ...] = (
    LanguageDefinition("en", "English", "English", "en-IN", "ltr", enabled=True),
    LanguageDefinition("hi", "Hindi", "हिन्दी", "hi-IN", "ltr", enabled=True),
    LanguageDefinition("bn", "Bengali", "বাংলা", "bn-IN", "ltr", enabled=True),
    LanguageDefinition("ta", "Tamil", "தமிழ்", "ta-IN", "ltr", enabled=False),
    LanguageDefinition("te", "Telugu", "తెలుగు", "te-IN", "ltr", enabled=False),
    LanguageDefinition("mr", "Marathi", "मराठी", "mr-IN", "ltr", enabled=False),
    LanguageDefinition("gu", "Gujarati", "ગુજરાતી", "gu-IN", "ltr", enabled=False),
    LanguageDefinition("kn", "Kannada", "ಕನ್ನಡ", "kn-IN", "ltr", enabled=False),
    LanguageDefinition("ml", "Malayalam", "മലയാളം", "ml-IN", "ltr", enabled=False),
    LanguageDefinition("or", "Odia", "ଓଡ଼ିଆ", "or-IN", "ltr", enabled=False),
    LanguageDefinition("pa", "Punjabi", "ਪੰਜਾਬੀ", "pa-IN", "ltr", enabled=False),
    LanguageDefinition("as", "Assamese", "অসমীয়া", "as-IN", "ltr", enabled=False),
    LanguageDefinition("ur", "Urdu", "اردو", "ur-IN", "rtl", enabled=False),
)

DEFAULT_LANGUAGE: LanguageCode = "en"

_BY_CODE: dict[str, LanguageDefinition] = {lang.code: lang for lang in LANGUAGES}


def get_language(code: str) -> LanguageDefinition | None:
    """One language definition by code, or None if unregistered. Never
    raises -- callers decide whether an unknown code means 'fall back to
    English' or 'reject the request'."""
    return _BY_CODE.get(code)


def is_supported(code: str) -> bool:
    """True only for a language that is both registered AND enabled --
    the check a caller almost always wants (e.g. validating a
    translation request's targetLanguage)."""
    lang = _BY_CODE.get(code)
    return lang is not None and lang.enabled


def enabled_languages() -> list[LanguageDefinition]:
    """Every language currently selectable in the UI (Milestone 1:
    en/hi/bn), in registry order."""
    return [lang for lang in LANGUAGES if lang.enabled]


def supported_codes() -> tuple[str, ...]:
    """Every registered code, enabled or not -- e.g. for validating a
    code against "is this a real language we know about at all"."""
    return tuple(lang.code for lang in LANGUAGES)
