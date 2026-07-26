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
# The toolchain's promise, stated as an env var: every tool the verifiers
# gate on is present here. Verifiers hard-fail on a missing tool only where
# this is set, so an outdated image degrades to a warning instead of
# failing every book, and a regression in this image cannot silently
# drop a gate.
ENV PRESS_TOOLCHAIN=1
# texlive-latex-extra below carries lettrine.sty, which chapter-opening drop
# caps require; texlive-luatex covers needspace. texlive-fonts-extra carries
# yfonts.sty and the yinit decorated-capital font, which the "ornate"
# chapter-opening style sets its initial in (\usefont{U}{yinit}{m}{n}). Do not
# drop any of these three collections.
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

# --- Real-ESRGAN upscaler for `press art enhance` -----------------------------
# Bakes the realesrgan-ncnn-vulkan CLI to /usr/local/bin and the remacri/
# ultrasharp ncnn models to /usr/local/share/realesrgan/models -- the exact
# binary name and paths press.art_enhance.find_upscaler() probes
# (_UPSCALER_PATHS[0] and _MODEL_DIRS[0]), so `press art enhance` upscales in
# the container the same way it does against Upscayl.app on a Mac. remacri-4x is
# the model the engraving profile asks for; ultrasharp-4x is the wash/photo one.
#
# This ONLY makes the tool available. Art is never generated in CI -- plates are
# committed by the author; absent this tool the command degrades to a plain
# resample and still finishes.
#
# CI runners have no GPU, so mesa-vulkan-drivers supplies the lavapipe *software*
# Vulkan device and inference runs on CPU (correct, just slow). realesrgan-ncnn-
# vulkan has no CPU-only path, so without a Vulkan ICD the binary would be
# present-but-unrunnable -- the same trap as the epubcheck/binfmt scar -- which
# is why the driver is not optional.
#
# The upstream ncnn release ships an x86_64 Linux binary only; there is no
# durable arm64 Linux build. The step is therefore guarded to amd64. On arm64
# the upscaler is simply absent and `press art enhance` resamples -- that must
# not fail the multi-arch image build, hence the guard rather than a hard fetch.
#
# Reproducible pins (all sha256-verified below):
#   binary: github.com/xinntao/Real-ESRGAN release v0.2.5.0,
#           realesrgan-ncnn-vulkan-20220424-ubuntu.zip
#   models: github.com/upscayl/upscayl @ v2.15.0
#           (commit 4f39acfc6f88260d105920a64deff8431d5e1544),
#           resources/models/{remacri-4x,ultrasharp-4x}.{param,bin}
#
# NEXT STEPS (operator, not the author -- the immutable-release-contract steps
# this change deliberately does NOT take): rebuild the multi-arch toolchain
# image, push it, then repin the toolchain image's @sha256 digest in
# .github/workflows/build.yml so a pinned book resolves the exact bytes that
# carry this upscaler. Until that repin lands, the baked tool lives only in a
# locally built image, not in the release contract.
ARG TARGETARCH
RUN set -eux; \
    if [ "${TARGETARCH:-amd64}" = "amd64" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        curl unzip ca-certificates libvulkan1 libgomp1 mesa-vulkan-drivers; \
      mkdir -p /usr/local/share/realesrgan/models /tmp/realesrgan; \
      cd /tmp/realesrgan; \
      curl -fsSL -o realesrgan.zip \
        https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip; \
      echo "e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96  realesrgan.zip" | sha256sum -c -; \
      unzip -q realesrgan.zip realesrgan-ncnn-vulkan; \
      install -m 0755 realesrgan-ncnn-vulkan /usr/local/bin/realesrgan-ncnn-vulkan; \
      models_base=https://raw.githubusercontent.com/upscayl/upscayl/4f39acfc6f88260d105920a64deff8431d5e1544/resources/models; \
      for f in remacri-4x.param remacri-4x.bin ultrasharp-4x.param ultrasharp-4x.bin; do \
        curl -fsSL -o "/usr/local/share/realesrgan/models/$f" "$models_base/$f"; \
      done; \
      cd /usr/local/share/realesrgan/models; \
      printf '%s\n' \
        "859ecba5b3592ecf3e76c93bed65e9f627b5236dd696aae5a84ecf8c93ab65ce  remacri-4x.param" \
        "a43be595c0d743314c30b50fe7ef188be0c61cc55c46ce81adb79ba4b3c3fb7a  remacri-4x.bin" \
        "0136ca83686809a8f17f7111f11b951e8db93610e24b7f4137c9ffe4dbc4a806  ultrasharp-4x.param" \
        "fb3e279d40d4cddb44db4e684d59e68d0aa39852c8cc14dc3f23ccc7e6eee9c1  ultrasharp-4x.bin" \
        | sha256sum -c -; \
      test -x /usr/local/bin/realesrgan-ncnn-vulkan; \
      rm -rf /tmp/realesrgan /var/lib/apt/lists/*; \
    else \
      echo "realesrgan-ncnn-vulkan: no upstream arm64 Linux build; press art enhance will resample on arm64"; \
    fi

WORKDIR /book
