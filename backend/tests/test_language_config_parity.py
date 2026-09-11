"""Parity test: backend/app/translation/languages.py (the Python
registry) versus frontend/lib/i18n/languages.ts (the TypeScript mirror).

The two files are hand-maintained in two languages on purpose (no shared
build step exists between a Python backend and a Next.js frontend in
this project) -- this test is what keeps them from silently drifting.
It reads the ACTUAL TypeScript source text at test time and parses the
`LANGUAGES` array + `DEFAULT_LANGUAGE` constant out of it with regular
expressions; it never hand-copies a second set of expected values into
this file. If someone edits one registry and forgets the other, this
test is what catches it -- and if the parser itself can no longer find
anything (e.g. the TS file's shape changed enough that the regexes no
longer match), the sanity checks below fail loudly rather than letting
every real comparison vacuously pass against an empty list.

No network, no Supabase, no BHASHINI, no environment variables, no
Render -- purely a text-file comparison, deterministic every run.
"""

import re
from pathlib import Path

import pytest

from app.translation.languages import DEFAULT_LANGUAGE, LANGUAGES

FRONTEND_LANGUAGES_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "lib" / "i18n" / "languages.ts"
)

_BOOL_FIELDS = ("translation", "speechToText", "textToSpeech", "transliteration")


def _parse_bool_field(field: str, block: str) -> bool:
    match = re.search(rf"\b{field}\s*:\s*(true|false)", block)
    if match is None:
        raise AssertionError(
            f"Could not find boolean field {field!r} in capabilities block: {block!r}"
        )
    return match.group(1) == "true"


def _parse_capabilities_object(block: str) -> dict[str, bool]:
    """A `{ translation: false, speechToText: false, ... }` literal (or
    any object containing those four fields, in any order) -> a plain
    dict keyed by the TS field names."""
    return {field: _parse_bool_field(field, block) for field in _BOOL_FIELDS}


def _parse_capability_constants(source: str) -> dict[str, dict[str, bool]]:
    """Every top-level `const NAME[: Type] = { ...booleans... };` in the
    file, e.g. `NO_CAPABILITIES` -- resolved so a language entry that
    references one by name (`capabilities: NO_CAPABILITIES`) can be
    looked up, without assuming that constant is the only one that will
    ever exist (a later edit giving one language its own named
    capabilities constant is still handled)."""
    constants: dict[str, dict[str, bool]] = {}
    for match in re.finditer(r"const\s+(\w+)(?:\s*:\s*[\w<>\[\]]+)?\s*=\s*\{([^{}]*)\}", source):
        name, block = match.group(1), match.group(2)
        if all(field in block for field in _BOOL_FIELDS):
            constants[name] = _parse_capabilities_object(block)
    return constants


def _parse_frontend_registry() -> tuple[dict[str, dict], str]:
    """Returns (languages_by_code, default_language) parsed directly from
    the live frontend/lib/i18n/languages.ts source."""
    assert FRONTEND_LANGUAGES_TS.is_file(), (
        f"Frontend language registry not found at {FRONTEND_LANGUAGES_TS} -- "
        "has it moved? This test must be updated to match, not deleted."
    )
    source = FRONTEND_LANGUAGES_TS.read_text(encoding="utf-8")

    capability_constants = _parse_capability_constants(source)

    array_match = re.search(r"export const LANGUAGES[^=]*=\s*\[(.*?)\n\]\s*;", source, re.DOTALL)
    assert array_match is not None, (
        "Could not locate `export const LANGUAGES: ... = [...]` in "
        f"{FRONTEND_LANGUAGES_TS} -- the parser needs updating, not the assertions."
    )
    array_body = array_match.group(1)

    entries = re.findall(r"\{[^{}]*\}", array_body)
    assert entries, (
        "Found the LANGUAGES array but extracted zero language entries from it -- "
        "the object-literal parser needs updating."
    )

    default_match = re.search(
        r'export const DEFAULT_LANGUAGE[^=]*=\s*"(\w+)"\s*;', source
    )
    assert default_match is not None, "Could not find `export const DEFAULT_LANGUAGE = \"...\";\""
    default_language = default_match.group(1)

    by_code: dict[str, dict] = {}
    for entry in entries:
        code_match = re.search(r'code:\s*"(\w+)"', entry)
        name_match = re.search(r'\bname:\s*"([^"]*)"', entry)
        native_name_match = re.search(r'nativeName:\s*"([^"]*)"', entry)
        locale_match = re.search(r'locale:\s*"([^"]*)"', entry)
        direction_match = re.search(r'direction:\s*"(ltr|rtl)"', entry)
        enabled_match = re.search(r"enabled:\s*(true|false)", entry)
        capabilities_match = re.search(r"capabilities:\s*(\{[^}]*\}|\w+)", entry)

        assert code_match, f"Language entry missing `code`: {entry!r}"
        assert name_match, f"Language entry {code_match.group(1)!r} missing `name`"
        assert native_name_match, f"Language entry {code_match.group(1)!r} missing `nativeName`"
        assert locale_match, f"Language entry {code_match.group(1)!r} missing `locale`"
        assert direction_match, f"Language entry {code_match.group(1)!r} missing `direction`"
        assert enabled_match, f"Language entry {code_match.group(1)!r} missing `enabled`"
        assert capabilities_match, f"Language entry {code_match.group(1)!r} missing `capabilities`"

        cap_value = capabilities_match.group(1)
        if cap_value.startswith("{"):
            capabilities = _parse_capabilities_object(cap_value)
        else:
            assert cap_value in capability_constants, (
                f"Language entry {code_match.group(1)!r} references capabilities constant "
                f"{cap_value!r}, which was not found anywhere in {FRONTEND_LANGUAGES_TS}"
            )
            capabilities = capability_constants[cap_value]

        code = code_match.group(1)
        by_code[code] = {
            "code": code,
            "name": name_match.group(1),
            "native_name": native_name_match.group(1),
            "locale": locale_match.group(1),
            "direction": direction_match.group(1),
            "enabled": enabled_match.group(1) == "true",
            "capabilities": {
                "translation": capabilities["translation"],
                "speech_to_text": capabilities["speechToText"],
                "text_to_speech": capabilities["textToSpeech"],
                "transliteration": capabilities["transliteration"],
            },
        }

    return by_code, default_language


# Parsed once at collection time -- every test below reads from this,
# never re-parsing and never hand-copying a value.
_FRONTEND_LANGUAGES, _FRONTEND_DEFAULT_LANGUAGE = _parse_frontend_registry()
_BACKEND_BY_CODE = {lang.code: lang for lang in LANGUAGES}


# ============================================================
# Parser sanity -- these fail loudly if the parser itself breaks,
# instead of every comparison below vacuously passing against {}.
# ============================================================


def test_frontend_registry_file_exists():
    assert FRONTEND_LANGUAGES_TS.is_file()


def test_parser_found_a_plausible_number_of_languages():
    """Guards against the regex silently matching nothing (or only
    partially) after an unrelated formatting change to the TS file --
    13 is today's real count, but the important thing is "more than a
    couple", not an exact hardcoded expectation of the data itself."""
    assert len(_FRONTEND_LANGUAGES) >= 10, (
        f"Only parsed {len(_FRONTEND_LANGUAGES)} languages from "
        f"{FRONTEND_LANGUAGES_TS} -- the parser likely needs updating."
    )


def test_backend_registry_is_not_empty():
    assert len(LANGUAGES) >= 10


# ============================================================
# Structural parity
# ============================================================


def test_same_set_of_language_codes_on_both_sides():
    backend_codes = set(_BACKEND_BY_CODE)
    frontend_codes = set(_FRONTEND_LANGUAGES)
    only_backend = backend_codes - frontend_codes
    only_frontend = frontend_codes - backend_codes
    assert not only_backend, (
        f"Language code(s) {sorted(only_backend)} exist in "
        "backend/app/translation/languages.py but not in "
        "frontend/lib/i18n/languages.ts"
    )
    assert not only_frontend, (
        f"Language code(s) {sorted(only_frontend)} exist in "
        "frontend/lib/i18n/languages.ts but not in "
        "backend/app/translation/languages.py"
    )


def test_same_number_of_languages_on_both_sides():
    assert len(LANGUAGES) == len(_FRONTEND_LANGUAGES)


def test_default_language_matches():
    assert DEFAULT_LANGUAGE == _FRONTEND_DEFAULT_LANGUAGE, (
        f"backend DEFAULT_LANGUAGE={DEFAULT_LANGUAGE!r} != "
        f"frontend DEFAULT_LANGUAGE={_FRONTEND_DEFAULT_LANGUAGE!r}"
    )


# ============================================================
# Field-by-field parity, one language at a time
# ============================================================


@pytest.mark.parametrize("code", [lang.code for lang in LANGUAGES])
def test_language_fields_match_frontend(code):
    backend = _BACKEND_BY_CODE[code]
    assert code in _FRONTEND_LANGUAGES, f"{code!r} is missing from the frontend registry"
    frontend = _FRONTEND_LANGUAGES[code]

    assert backend.code == frontend["code"], f"{code}: code mismatch"
    assert backend.name == frontend["name"], (
        f"{code}: name mismatch -- backend={backend.name!r} frontend={frontend['name']!r}"
    )
    assert backend.native_name == frontend["native_name"], (
        f"{code}: native_name/nativeName mismatch -- "
        f"backend={backend.native_name!r} frontend={frontend['native_name']!r}"
    )
    assert backend.locale == frontend["locale"], (
        f"{code}: locale mismatch -- backend={backend.locale!r} frontend={frontend['locale']!r}"
    )
    assert backend.direction == frontend["direction"], (
        f"{code}: direction mismatch -- "
        f"backend={backend.direction!r} frontend={frontend['direction']!r}"
    )
    assert backend.enabled == frontend["enabled"], (
        f"{code}: enabled mismatch -- backend={backend.enabled!r} frontend={frontend['enabled']!r}"
    )


@pytest.mark.parametrize("code", [lang.code for lang in LANGUAGES])
def test_capabilities_match_frontend(code):
    backend = _BACKEND_BY_CODE[code].capabilities
    frontend = _FRONTEND_LANGUAGES[code]["capabilities"]

    assert backend.translation == frontend["translation"], f"{code}: capabilities.translation mismatch"
    assert backend.speech_to_text == frontend["speech_to_text"], (
        f"{code}: capabilities.speech_to_text/speechToText mismatch"
    )
    assert backend.text_to_speech == frontend["text_to_speech"], (
        f"{code}: capabilities.text_to_speech/textToSpeech mismatch"
    )
    assert backend.transliteration == frontend["transliteration"], (
        f"{code}: capabilities.transliteration mismatch"
    )
