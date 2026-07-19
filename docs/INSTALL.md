# Installing the press and its toolchain

The press is a Python package that drives external tools. `press
doctor` is the authority on any machine's readiness: it names every
dependency, distinguishes missing from present-but-broken, and says
what each absence costs. Run it first and after every step here.

## The press itself

```sh
pip install "press @ git+https://github.com/clintecker/press@v1"
```

Pip-from-git at a tag is the supported installation channel. `@v1`
floats with the latest compatible release; pin a three-part tag
(`@v1.6.0`) for an immutable pipeline. For development, clone and
`pip install -e .`.

## The toolchain by platform

Supported platforms are Linux (the container's Ubuntu 24.04 is the
reference) and macOS. CI runs everything inside
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
  bash -c "pip install --break-system-packages 'press @ git+https://github.com/clintecker/press@v1' && cd /book && press all"
```

The image is private by default; a repository needs a one-time read
grant under the package's Manage Actions access settings.

## Optional capabilities

- `claude` (Claude Code CLI): enables the operator (`press improve`,
  `press research`, `press aesthetic "<brief>"`).
- `OPENAI_API_KEY`, `GEMINI_API_KEY`: enable `press art commission`.
- `epubcheck` locally: hardens the EPUB gate before push; CI always
  runs it regardless.

## Known first-run behavior

The first LuaLaTeX run on a fresh machine triggers a several-minute
font scan that looks like a hang. It is not a hang.
