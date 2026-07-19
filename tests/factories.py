"""A composable book factory for isolated test scenarios.

A test needs a book, not the whole scaffold: exactly the files the
invariant under examination touches, and nothing inherited. BookFactory
builds minimal source-only books under a pytest temporary root, records
every fact it generated so a test never relies on a hidden default, and
hands back a BookHandle whose `use()` context isolates BOOK_ROOT, the
working directory, and every booklib cache. Two books built by the same
factory cannot contaminate one another; the suite proves it.

Presets (minimal, full, hostile_input, retail, override, portability,
release) name the common shapes so a test states its intent, not its
plumbing. Artifact building is deliberately separate: a factory makes
sources, and a test that wants dist/ output builds it explicitly, so no
prebuilt artifact is ever smuggled into an unrelated test.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@dataclass
class BookHandle:
    """A built book and every fact the factory put in it. Tests read
    these attributes instead of re-deriving them, so a change in factory
    defaults surfaces at the assertion, not as a silent mismatch."""

    root: Path
    slug: str
    metadata: dict
    chapters: dict[str, str] = field(default_factory=dict)
    appendices: dict[str, str] = field(default_factory=dict)
    sentinels: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    symlinks: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)

    @contextmanager
    def use(self):
        """Point the press at this book, with cwd, BOOK_ROOT, and every
        booklib cache isolated and restored afterward."""

        from press import selftest

        previous_cwd = Path.cwd()
        with selftest.borrow_book(self.root):
            os.chdir(self.root)
            try:
                yield self
            finally:
                os.chdir(previous_cwd)


@dataclass
class BookFactory:
    """Builds a book from declared parts. Every mutator returns self so
    a scenario reads as one statement; build() writes the files and
    returns the handle."""

    slug: str = "fixture-book"
    title: str = "A Fixture Book"
    author: str = "Fixture Author"
    _metadata: dict = field(default_factory=dict)
    _chapters: dict[str, str] = field(default_factory=dict)
    _appendices: dict[str, str] = field(default_factory=dict)
    _sentinels: list[str] = field(default_factory=list)
    _authorities: list[dict] | None = None
    _index_terms: list[dict] | None = None
    _front_matter: dict | None = None
    _aesthetic: dict | None = None
    _house_rules: dict | None = None
    _reader_css: str | None = None
    _extra_css: str | None = None
    _title_tex: str | None = None
    _secrets: dict[str, str] = field(default_factory=dict)
    _symlinks: dict[str, str] = field(default_factory=dict)
    _extras: dict[str, str] = field(default_factory=dict)

    def with_metadata(self, **keys) -> BookFactory:
        self._metadata.update(keys)
        return self

    def with_chapter(self, name: str, body: str) -> BookFactory:
        self._chapters[name] = body
        return self

    def with_appendix(self, name: str, body: str) -> BookFactory:
        self._appendices[name] = body
        return self

    def with_sentinels(self, *phrases: str) -> BookFactory:
        self._sentinels.extend(phrases)
        return self

    def with_authorities(self, entries: list[dict]) -> BookFactory:
        self._authorities = entries
        return self

    def with_index_terms(self, terms: list[dict]) -> BookFactory:
        self._index_terms = terms
        return self

    def with_front_matter(self, **keys) -> BookFactory:
        self._front_matter = keys
        return self

    def with_aesthetic(self, mapping: dict) -> BookFactory:
        self._aesthetic = mapping
        return self

    def with_house_rules(self, mapping: dict) -> BookFactory:
        self._house_rules = mapping
        return self

    def with_reader_css(self, css: str) -> BookFactory:
        self._reader_css = css
        return self

    def with_extra_css(self, css: str) -> BookFactory:
        self._extra_css = css
        return self

    def with_title_tex(self, tex: str) -> BookFactory:
        self._title_tex = tex
        return self

    def with_secret(self, name: str, body: str = "KEY=secret") -> BookFactory:
        self._secrets[name] = body
        return self

    def with_symlink(self, name: str, target: str) -> BookFactory:
        self._symlinks[name] = target
        return self

    def with_extra_file(self, relpath: str, body: str) -> BookFactory:
        self._extras[relpath] = body
        return self

    def _metadata_document(self) -> dict:
        base = {
            "title": self.title,
            "author": [self.author],
            "description": "A book built by the test factory.",
            "slug": self.slug,
            "lang": "en-US",
            "verify-sentinels": list(self._sentinels),
            "verify-min-pages": 1,
        }
        base.update(self._metadata)
        return base

    def build(self, root: Path) -> BookHandle:
        book = root / self.slug
        (book / "config").mkdir(parents=True)
        (book / "book" / "chapters").mkdir(parents=True)

        metadata = self._metadata_document()
        # Hostile metadata is written verbatim so a parser test sees the
        # raw bytes; a mapping is dumped as YAML.
        raw = self._metadata.get("__raw__")
        if raw is not None:
            (book / "config" / "metadata.yaml").write_text(raw, encoding="utf-8")
            metadata = {"__raw__": raw}
        else:
            (book / "config" / "metadata.yaml").write_text(
                yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
            )

        chapters = self._chapters or {"00-only.md": _default_chapter(self._sentinels)}
        for name, body in chapters.items():
            (book / "book" / "chapters" / name).write_text(body, encoding="utf-8")
        if self._appendices:
            (book / "book" / "appendices").mkdir()
            for name, body in self._appendices.items():
                (book / "book" / "appendices" / name).write_text(body, encoding="utf-8")

        self._write_optional(book)
        for name, body in self._secrets.items():
            (book / name).write_text(body, encoding="utf-8")
        for name, target in self._symlinks.items():
            (book / name).symlink_to(target)
        for relpath, body in self._extras.items():
            path = book / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

        return BookHandle(
            root=book,
            slug=self.slug,
            metadata=metadata,
            chapters=dict(chapters),
            appendices=dict(self._appendices),
            sentinels=list(self._sentinels),
            secrets=list(self._secrets),
            symlinks=list(self._symlinks),
            extras=list(self._extras),
        )

    def _write_optional(self, book: Path) -> None:
        config = book / "config"
        if self._authorities is not None:
            (config / "authorities.yaml").write_text(
                yaml.safe_dump(self._authorities, sort_keys=False), encoding="utf-8"
            )
        if self._index_terms is not None:
            (config / "index-terms.yaml").write_text(
                yaml.safe_dump(self._index_terms, sort_keys=False), encoding="utf-8"
            )
        if self._front_matter is not None:
            (config / "front-matter.yaml").write_text(
                yaml.safe_dump(self._front_matter, sort_keys=False), encoding="utf-8"
            )
        if self._aesthetic is not None:
            (config / "aesthetic.yaml").write_text(
                yaml.safe_dump(self._aesthetic, sort_keys=False), encoding="utf-8"
            )
        if self._house_rules is not None:
            (config / "house-rules.yaml").write_text(
                yaml.safe_dump(self._house_rules, sort_keys=False), encoding="utf-8"
            )
        if self._reader_css is not None or self._extra_css is not None:
            (book / "assets" / "web").mkdir(parents=True, exist_ok=True)
            if self._reader_css is not None:
                (book / "assets" / "web" / "reader.css").write_text(
                    self._reader_css, encoding="utf-8")
            if self._extra_css is not None:
                (book / "assets" / "web" / "extra.css").write_text(
                    self._extra_css, encoding="utf-8")
        if self._title_tex is not None:
            (book / "tex").mkdir(exist_ok=True)
            (book / "tex" / "title-page.tex").write_text(self._title_tex, encoding="utf-8")


def _default_chapter(sentinels: list[str]) -> str:
    line = sentinels[0] if sentinels else (
        "This chapter carries one honest plain sentence long enough to "
        "serve as a manuscript witness for the verifiers."
    )
    return f"# Only\n\n{line}\n"


# ---- named presets ----

def minimal() -> BookFactory:
    """The smallest book that is still a book: one chapter, one sentinel."""

    return BookFactory().with_sentinels(
        "the smallest book that is still honestly a book"
    ).with_chapter(
        "00-only.md",
        "# Only\n\nHere is the smallest book that is still honestly a book, "
        "carrying one true sentence.\n",
    )


def full() -> BookFactory:
    """Chapters, an appendix, authorities, index terms, front matter,
    and an aesthetic: the shape that exercises the generators."""

    claim = "movable type reorders the labor of the page"
    return (
        BookFactory(slug="full-book")
        .with_sentinels("the whole apparatus assembled", claim)
        .with_chapter("01-press.md", f"# The press\n\nHere the whole apparatus assembled, and {claim}.\n")
        .with_appendix("z-notes.md", "# Notes\n\nA closing note long enough to read as prose.\n")
        .with_authorities([
            {"claim": claim, "file": "book/chapters/01-press.md",
             "authority": "A Trade History (1900)"},
        ])
        .with_index_terms([{"term": "press", "match": ["press"]}])
        .with_front_matter(dedication="For the compositors.")
        .with_aesthetic({"name": "plain", "web-palette": {"ink": "#111111"}})
    )


def hostile_input() -> BookFactory:
    """A book whose metadata is deliberately malformed, for refusal
    tests."""

    return BookFactory(slug="hostile-book").with_metadata(__raw__='title: "unclosed\n')


def retail() -> BookFactory:
    """A book with the print and registrations blocks a retail run reads."""

    return (
        BookFactory(slug="retail-book")
        .with_sentinels("bound for the retail channel")
        .with_metadata(
            print={"paper": "cream"},
            registrations={"isbn": {"print": "978-0-306-40615-7"}},
            subtitle="A Retail Proof",
        )
    )


def override() -> BookFactory:
    """A book that overrides the house web and print look."""

    return (
        BookFactory(slug="override-book")
        .with_sentinels("this book owns its own look")
        .with_reader_css("/* my own everything */ html { all: unset; }")
        .with_extra_css("body { background: rebeccapurple; }")
        .with_aesthetic({"name": "loud", "typography": {"web-family": "Comic Sans MS"}})
    )


def portability() -> BookFactory:
    """A book carrying characters and shapes that stress the portable
    formats."""

    return (
        BookFactory(slug="portable-book")
        .with_sentinels("plain text must survive the crossing")
        .with_chapter(
            "00-only.md",
            "# Only\n\nHere plain text must survive the crossing intact, "
            "quotes and all.\n",
        )
    )


def release() -> BookFactory:
    """A book that satisfies the release witness gate: at least two
    sentinels and a real page floor."""

    return (
        BookFactory(slug="release-book")
        .with_sentinels("first witness of the release", "second witness of the release")
        .with_metadata(**{"verify-min-pages": 24})
        .with_chapter(
            "00-only.md",
            "# Only\n\nHere the first witness of the release stands, and the "
            "second witness of the release stands beside it.\n",
        )
    )


PRESETS = {
    "minimal": minimal,
    "full": full,
    "hostile_input": hostile_input,
    "retail": retail,
    "override": override,
    "portability": portability,
    "release": release,
}
