FROM ubuntu:26.04

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
# The toolchain's promise, stated as an env var: every tool the verifiers
# gate on is present here. Verifiers hard-fail on a missing tool only where
# this is set, so an outdated image degrades to a warning instead of
# failing every book, and a regression in this image cannot silently
# drop a gate.
ENV PRESS_TOOLCHAIN=1
# texlive-latex-extra below carries lettrine.sty, which chapter-opening drop
# caps require; texlive-luatex covers needspace. Do not drop either collection.
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
    gh \
    pandoc \
    python3 \
    python3-pip \
    poppler-utils \
    epubcheck \
    texlive-luatex \
    texlive-latex-extra \
    texlive-fonts-extra \
    fonts-linuxlibertine \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu's epubcheck launcher runs the jar through binfmt_misc, which is
# not registered inside containers: the command exists but dies with
# "Exec format error". A plain java wrapper keeps the toolchain's
# promise honest.
RUN printf '#!/bin/sh\nexec java -jar /usr/share/java/epubcheck.jar "$@"\n' \
    > /usr/local/bin/epubcheck && chmod +x /usr/local/bin/epubcheck

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    "Pillow>=10.0" "PyYAML>=6.0" "pypdf>=4.0"

WORKDIR /book
