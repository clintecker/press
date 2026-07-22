# Installing the press and its toolchain

The press is a Python package that drives external tools. `press
doctor` is the authority on any machine's readiness: it names every
dependency, distinguishes missing from present-but-broken, and says
what each absence costs. Run it first and after every step here.

If this is your first book, the
[quickstart](https://github.com/clintecker/press/blob/main/docs/QUICKSTART.md)
walks the whole path from here to a verified book; this page is the
per-platform toolchain detail it links into.

## The press itself

```sh
pip install "press @ git+https://github.com/clintecker/press@v2"
```

Pip-from-git at a tag is the supported installation channel; the
press is not published to PyPI, and nothing in its metadata should
imply otherwise (releases live on GitHub, and books consume the
composite action). `@v2` floats with the latest compatible release;
pin a three-part tag (`@v2.0.0`) for an immutable pipeline. A book
already on `@v1` keeps working and upgrades when it chooses, with
`press migrate` (see [migration](migration.html)). For
development, clone and `pip install -e .`.

## The toolchain by platform

Supported platforms are Linux (the container's Ubuntu 24.04 is the
reference) and macOS. Python 3.10 through 3.14 are tested on
every push (Linux across all five, macOS on 3.12); the container's
pandoc and TeX Live versions are the reference toolchain, proven by
its own smoke tests. CI runs everything inside
`ghcr.io/clintecker/press-toolchain`, which is the ground truth for
versions; local installs mirror it.

### macOS

```sh
brew install pandoc poppler
brew install --cask mactex-no-gui   # lualatex, latexmk, TeX Live
brew install epubcheck              # optional: the retail EPUB gate locally
```

Fonts: TeX Live carries Libertinus for the PDF; nothing else to
install.

### Debian and Ubuntu

The Dockerfile is the canonical package list; mirror it:

```sh
sudo apt-get install --no-install-recommends \
  make git pandoc python3 python3-pip poppler-utils \
  texlive-luatex texlive-latex-extra texlive-fonts-extra \
  fonts-linuxlibertine latexmk epubcheck
```

`fonts-linuxlibertine` is stated explicitly because Ubuntu has no
`fonts-libertinus` package and `--no-install-recommends` drops the
face otherwise. Note that Ubuntu's `epubcheck` launcher needs
binfmt jar support; inside containers, use a `java -jar` wrapper as
the Dockerfile does.

### The container (no local toolchain at all)

Any book's CI uses the prebuilt image; locally you can too:

```sh
docker run --rm -v "$PWD":/book ghcr.io/clintecker/press-toolchain:latest \
  bash -c "pip install --break-system-packages 'press @ git+https://github.com/clintecker/press@v2' && cd /book && press all"
```

The toolchain image is public: any repository, under any account, pulls
it with no grant and no configured secret. In a book's CI the pull is
authenticated with the workflow's own `GITHUB_TOKEN` (which works for a
public image, including on fork and Dependabot pull requests); locally
the `docker run` above pulls it anonymously.

## Optional capabilities

- `claude` (Claude Code CLI): enables the operator (`press improve`,
  `press research`, `press aesthetic "<brief>"`).
- `OPENAI_API_KEY`, `GEMINI_API_KEY`: enable `press art commission`.
- `epubcheck` locally: hardens the EPUB gate before push; CI always
  runs it regardless.

## Known first-run behavior

The first LuaLaTeX run on a fresh machine triggers a several-minute
font scan that looks like a hang. It is not a hang.
