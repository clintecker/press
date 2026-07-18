"""A small press: the build, check, and verify pipeline for books.

Extracted from the production of one book so the next book starts with the
scars already paid for. Everything book-specific comes from the book
repository's config; nothing in here names a title.
"""

import importlib.metadata


def version() -> str:
    """The installed press version; pyproject.toml is the only stated copy."""

    try:
        return importlib.metadata.version("press")
    except importlib.metadata.PackageNotFoundError:
        return "unreleased"
