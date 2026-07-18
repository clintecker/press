FROM ubuntu:24.04

# Toolchain image for building and verifying books. CI pulls this instead of
# apt-installing two gigabytes of TeX Live on every run (about 2 minutes
# instead of 10). Rebuilt by .github/workflows/toolchain.yml when this file
# changes. It carries only open-source tools, never book or press content,
# so it can safely be a public package.
#
# fonts-linuxlibertine is stated explicitly: Ubuntu has no fonts-libertinus
# package, and --no-install-recommends will not pull the Libertine keyboard
# face in for you.

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
    gh \
    pandoc \
    python3 \
    python3-pip \
    poppler-utils \
    texlive-luatex \
    texlive-latex-extra \
    texlive-fonts-extra \
    fonts-linuxlibertine \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    "Pillow>=10.0" "PyYAML>=6.0" "pypdf>=4.0"

WORKDIR /book
