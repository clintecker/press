"""The press checking itself: press selftest.

Documentation drift is a checker's job, not a promise (checkers over
conventions). This target fails when the CLI grows a target the usage
text or README does not name, when a documented target loses its route,
or when the arithmetic the pipeline trusts (ISBN, ISSN, EAN-13) stops
agreeing with the canonical examples. CI runs it on every push to the
press.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

MODULES = [
    "press.art", "press.art_commission", "press.barcode", "press.booklib",
    "press.build", "press.check_source", "press.check_the_checkers",
    "press.gen_authorities", "press.gen_coverwrap", "press.gen_front_matter",
    "press.gen_index", "press.instruments", "press.jargon_lint",
    "press.operator", "press.package_source", "press.publish",
    "press.registrations", "press.scaffold", "press.style_audit",
    "press.verify_formats", "press.verify_pdf", "press.wordcount",
]


def check_imports() -> None:
    for name in MODULES:
        importlib.import_module(name)


def check_arithmetic() -> None:
    from . import barcode, registrations

    assert barcode.validate("978-0-306-40615-7") == "9780306406157"
    pattern = barcode.modules("9780306406157")
    assert len(pattern) == 95 and pattern[:3] == pattern[-3:] == "101"
    assert pattern[45:50] == "01010"
    assert registrations.issn_valid("0378-5955")
    assert not registrations.issn_valid("0378-5954")
    assert not registrations.issn_valid("123X-5678")


def check_docs() -> None:
    from . import __main__ as cli

    here = Path(__file__).resolve().parent
    source = (here / "__main__.py").read_text(encoding="utf-8")
    readme = (here.parent.parent / "README.md")
    usage_words = set(re.findall(r"[a-z-]{2,}", cli.USAGE.split("usage:")[1]))
    routed = set(re.findall(r'target == "([a-z-]+)"', source)) | set(cli.FORMATS)
    missing_from_usage = sorted(routed - usage_words)
    if missing_from_usage:
        raise SystemExit(f"targets routed but absent from usage text: {missing_from_usage}")
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        undocumented = sorted(
            t for t in routed if not re.search(rf"\b{re.escape(t)}\b", text)
        )
        if undocumented:
            raise SystemExit(f"targets absent from README: {undocumented}")


def main() -> int:
    check_imports()
    check_arithmetic()
    check_docs()
    print(f"Selftest passed: {len(MODULES)} modules import, arithmetic agrees "
          "with the canonical examples, usage and README name every target")
    return 0
