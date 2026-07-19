"""Property-based proofs for the press's pure scalar functions.

Example tests remember cases; these prove laws across the input space
where path escapes, escaping errors, and check-digit arithmetic
mistakes actually live. Every function under test is genuinely pure (no
book on disk, no environment, no clock): the strategies below build
their own inputs and the invariants must hold for all of them.

Determinism is a requirement, not a nicety: `derandomize=True` fixes
hypothesis's seed so a failure reproduces from the printed example, and
`deadline=None` removes the only time-dependent signal. Budgets are
work counts (`max_examples`), never elapsed seconds.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from press import aesthetic, barcode, booklib, registrations, verify_formats
from press.verify_pages import CSS_URL

DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=200)

# Characters that a CSS url() body and the token-substitution format can
# carry without colliding with the parser's own delimiters.
_URL_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/:"
_IDENT_ALPHABET = "abcdefghijklmnopqrstuvwxyz-"
_VALUE_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789#"


# --------------------------------------------------------------------------
# booklib.validate_slug  (INV-config-slug)
# --------------------------------------------------------------------------

@pytest.mark.invariant("INV-config-slug")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(slug=st.from_regex(booklib.SLUG_PATTERN, fullmatch=True))
def test_validate_slug_accepts_kebab_and_is_idempotent(slug):
    """Every strict-kebab string is accepted unchanged, and re-validating
    an accepted slug is a fixed point."""

    assert booklib.validate_slug(slug) == slug
    assert booklib.validate_slug(booklib.validate_slug(slug)) == slug


@pytest.mark.invariant("INV-config-slug")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(value=st.text(max_size=40))
def test_validate_slug_accepts_iff_strict_kebab_and_only_raises_systemexit(value):
    """The slug is accepted exactly when it fullmatches the pattern, and
    a rejection is always a SystemExit -- never a bare traceback."""

    matches = booklib.SLUG_PATTERN.fullmatch(value) is not None
    try:
        result = booklib.validate_slug(value)
    except SystemExit:
        assert not matches
    except Exception as exc:  # pragma: no cover - proves absence
        pytest.fail(f"validate_slug({value!r}) raised {exc!r}, not SystemExit")
    else:
        assert matches
        assert result == value


# --------------------------------------------------------------------------
# barcode check-digit arithmetic  (INV-config-registrations)
# --------------------------------------------------------------------------

_TWELVE = st.lists(st.integers(min_value=0, max_value=9), min_size=12, max_size=12)


def _isbn_from(first_twelve):
    digits = list(first_twelve)
    digits.append(barcode.check_digit(digits))
    return "".join(str(d) for d in digits)


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(first_twelve=_TWELVE)
def test_ean13_check_digit_is_a_pure_function_and_number_stays_valid(first_twelve):
    """The check digit is a single-valued function of the first twelve
    digits, lands in 0..9, and the number it completes validates to its
    own thirteen digits."""

    cd = barcode.check_digit(first_twelve)
    assert cd == barcode.check_digit(first_twelve)
    assert 0 <= cd <= 9
    isbn = _isbn_from(first_twelve)
    assert barcode.validate(isbn) == isbn


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(first_twelve=_TWELVE, data=st.data())
def test_ean13_single_digit_corruption_is_caught(first_twelve, data):
    """Corrupting exactly one digit of a valid EAN-13 always breaks the
    check-digit arithmetic (weights 1 and 3 are both coprime enough that
    no single change survives)."""

    isbn = _isbn_from(first_twelve)
    position = data.draw(st.integers(min_value=0, max_value=12))
    original = int(isbn[position])
    replacement = data.draw(st.integers(min_value=0, max_value=9).filter(lambda d: d != original))
    corrupted = isbn[:position] + str(replacement) + isbn[position + 1:]
    with pytest.raises(SystemExit):
        barcode.validate(corrupted)


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(first_twelve=_TWELVE)
def test_barcode_runs_partition_the_module_pattern(first_twelve):
    """runs() is a lossless run-length encoding of modules(): the counts
    sum to the full 95 modules, adjacent runs alternate ink and space,
    and re-expanding the runs reproduces the pattern exactly."""

    isbn = _isbn_from(first_twelve)
    pattern = barcode.modules(isbn)
    runs = barcode.runs(isbn)
    assert sum(count for _, count in runs) == 95
    assert len(pattern) == 95
    assert runs[0][0] == "ink"  # EAN-13 opens with the 101 guard
    for (a, _), (b, _) in zip(runs, runs[1:]):
        assert a != b
    rebuilt = "".join(("1" if kind == "ink" else "0") * count for kind, count in runs)
    assert rebuilt == pattern


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(count=st.integers(min_value=0, max_value=25).filter(lambda n: n != 13))
def test_digits_of_refuses_wrong_length(count):
    """Anything but thirteen digits is a named refusal, not an IndexError."""

    with pytest.raises(SystemExit):
        barcode.digits_of("0" * count)


# --------------------------------------------------------------------------
# registrations.issn_valid / lccn_plausible  (INV-config-registrations)
# --------------------------------------------------------------------------

_SEVEN = st.lists(st.integers(min_value=0, max_value=9), min_size=7, max_size=7)


def _issn_from(first_seven):
    total = sum(d * w for d, w in zip(first_seven, range(8, 1, -1)))
    check = (11 - total % 11) % 11
    tail = "X" if check == 10 else str(check)
    return "".join(str(d) for d in first_seven) + tail


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(first_seven=_SEVEN)
def test_valid_issn_passes_with_or_without_hyphen(first_seven):
    """A correctly computed ISSN check digit passes, and the hyphen the
    registry prints is ignored by the validator."""

    issn = _issn_from(first_seven)
    assert registrations.issn_valid(issn)
    assert registrations.issn_valid(issn[:4] + "-" + issn[4:])


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(first_seven=_SEVEN, data=st.data())
def test_issn_single_digit_corruption_is_caught(first_seven, data):
    """Changing one of the seven data digits of a valid ISSN always fails
    the mod-11 check."""

    issn = _issn_from(first_seven)
    position = data.draw(st.integers(min_value=0, max_value=6))
    original = int(issn[position])
    replacement = data.draw(st.integers(min_value=0, max_value=9).filter(lambda d: d != original))
    corrupted = issn[:position] + str(replacement) + issn[position + 1:]
    assert not registrations.issn_valid(corrupted)


@pytest.mark.invariant("INV-config-registrations")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(
    letters=st.integers(min_value=0, max_value=3),
    digits=st.integers(min_value=8, max_value=12),
)
def test_lccn_shape_accepts_in_range_and_rejects_out_of_range(letters, digits):
    """An LCCN is shape only: up to three letters then eight-to-twelve
    digits pass; a digit count outside that band fails."""

    body = "a" * letters + "0" * digits
    assert registrations.lccn_plausible(body)
    assert not registrations.lccn_plausible("a" * letters + "0" * 7)
    assert not registrations.lccn_plausible("a" * letters + "0" * 13)


# --------------------------------------------------------------------------
# verify_formats.normalized  (INV-format-witness)
# --------------------------------------------------------------------------

_CURLY = "‘’“”"


@pytest.mark.invariant("INV-format-witness")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(text=st.text(max_size=120))
def test_normalized_is_idempotent_and_folds_case_and_quotes(text):
    """normalized() is a fixed point of itself, its output is already
    case-folded, and it never leaves a curly quote behind."""

    once = verify_formats.normalized(text)
    assert verify_formats.normalized(once) == once
    assert once == once.casefold()
    assert not any(ch in once for ch in _CURLY)


@pytest.mark.invariant("INV-format-witness")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(text=st.text(max_size=120))
def test_normalized_folds_surrounding_and_internal_whitespace(text):
    """Extra whitespace around or inside the text collapses away: the
    witness match cannot be defeated by reflowing."""

    padded = "  \t\n " + text.replace(" ", "  \t ") + " \n\t "
    assert verify_formats.normalized(padded) == verify_formats.normalized(text)


@pytest.mark.invariant("INV-format-witness")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(text=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=80))
def test_normalized_is_case_insensitive_on_ascii(text):
    """On plain ASCII, upper- and lower-cased inputs normalize identically."""

    assert verify_formats.normalized(text.upper()) == verify_formats.normalized(text.lower())


# --------------------------------------------------------------------------
# verify_pages.CSS_URL  (INV-pages-refs)
# --------------------------------------------------------------------------

_URL_TOKEN = st.text(alphabet=_URL_ALPHABET, min_size=1, max_size=60)


@pytest.mark.invariant("INV-pages-refs")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(token=_URL_TOKEN)
def test_css_url_extraction_round_trips(token):
    """A url() body round-trips through the extraction regex whether it is
    bare, single-, or double-quoted."""

    assert CSS_URL.findall(f"url({token})") == [token]
    assert CSS_URL.findall(f'url("{token}")') == [token]
    assert CSS_URL.findall(f"url('{token}')") == [token]


@pytest.mark.invariant("INV-pages-refs")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(tokens=st.lists(_URL_TOKEN, min_size=1, max_size=6))
def test_css_url_extracts_every_reference_in_order(tokens):
    """Every url() in a stylesheet body is recovered, in source order."""

    blob = " ".join(f"url({token})" for token in tokens)
    assert CSS_URL.findall(blob) == tokens


# --------------------------------------------------------------------------
# aesthetic._substitute_tokens  (no ledger invariant; a pure text law)
# --------------------------------------------------------------------------

_IDENT = st.text(alphabet=_IDENT_ALPHABET, min_size=1, max_size=20)
_VALUE = st.text(alphabet=_VALUE_ALPHABET, min_size=1, max_size=20)


@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(text=st.text(max_size=200))
def test_substitute_tokens_empty_palette_is_identity(text):
    """An empty (or absent) palette changes nothing byte-for-byte."""

    assert aesthetic._substitute_tokens(text, {}) == text
    assert aesthetic._substitute_tokens(text, None) == text


@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(token=_IDENT, old=_VALUE, new=_VALUE)
def test_substitute_tokens_replaces_declared_value(token, old, new):
    """A declared token's value is replaced by the palette value, which
    then appears verbatim in the output; re-applying is a fixed point."""

    text = f"--{token}: {old};"
    once = aesthetic._substitute_tokens(text, {token: new})
    assert once == f"--{token}: {new};"
    assert new in once
    assert aesthetic._substitute_tokens(once, {token: new}) == once


@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(token=_IDENT, other=_IDENT, old=_VALUE, new=_VALUE)
def test_substitute_tokens_leaves_undeclared_tokens_alone(token, other, old, new):
    """Substituting a token that is not declared in the text is identity."""

    if token == other:
        return
    text = f"--{other}: {old};"
    assert aesthetic._substitute_tokens(text, {token: new}) == text
