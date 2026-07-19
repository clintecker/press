# Compatibility

The press has two runtime surfaces with different guarantees: the
Python package (which you install and run) and the toolchain (pandoc,
LuaLaTeX, Poppler, epubcheck) that turns markup into artifacts. This
page states what each supports and how a support change is governed.

## Python

The package targets Python 3.10 through 3.13. CI runs the fast package
tests on all four on Ubuntu, plus 3.12 on macOS, on every push. The
wheel declares `requires-python = ">=3.10"`; there is no upper cap
because a future minor usually works, but only 3.10 through 3.13 are
tested. `press doctor` warns when it runs on a version outside that
range. Running outside it is unproven, not forbidden.

## The toolchain

The supported toolchain is the pinned container image
`ghcr.io/clintecker/press-toolchain`, built from Ubuntu 24.04 and
carrying that release's pandoc, `texlive-luatex` and the LaTeX and
font extras, `poppler-utils`, and `epubcheck`. A three-part release
tag resolves an immutable `sha-` image, so a pinned book always
builds against the exact toolchain bytes the release was proven on.
That image is the compatibility contract: the exact tool versions are
whatever Ubuntu 24.04 shipped, frozen by the image digest.

For local authoring you need pandoc, a LuaLaTeX-capable TeX
distribution (TeX Live, or MacTeX on macOS), and Poppler; epubcheck is
optional and its absence softens EPUB verification to a warning rather
than failing the build. `press doctor` reports each tool as ok,
absent, missing, or present-but-broken, and names what each absence
costs.

## Operating systems

Linux (the Ubuntu 24.04 toolchain image) is the release and CI family:
every artifact is built and verified there before a tag ships. macOS
14 is supported for authoring and runs the package test suite in CI.
Windows is not tested.

## Unsupported combinations

An unsupported combination does not fail silently. A missing or broken
tool is named by `press doctor` with its cost and the install hint for
your platform; a Python version outside the tested range is flagged;
and the toolchain image pull fails loudly at container init when a
book repository has not been granted read access to the private
package.

## Governing a support change

Compatibility follows the versioning contract in
[ARCHITECTURE.md](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md):
the toolchain image is part of the pinned contract, so a change that
alters a valid book's output (a new pandoc or LuaLaTeX with different
layout) requires a new major, while a within-major fix may correct
broken output without changing a valid book. Each release records the
toolchain image digest it was proven against in its notes.
