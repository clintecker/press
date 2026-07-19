#!/usr/bin/env bash
# Smoke a locally built toolchain image: every promised binary
# executes (binfmt taught us existence and executability are different
# facts), epubcheck rejects a genuinely broken EPUB, and a minimal
# book builds and verifies with the press installed from this
# checkout. One script, called by both the PR smoke job and the
# publish job, so the two cannot drift.
#
# Usage: scripts/toolchain_smoke.sh <image-tag> <press-checkout-dir>
set -euo pipefail
image="${1:?usage: toolchain_smoke.sh <image-tag> <press-checkout>}"
press_dir="${2:?usage: toolchain_smoke.sh <image-tag> <press-checkout>}"

docker run --rm "$image" bash -euo pipefail -c '
  for tool in pandoc lualatex latexmk pdftoppm pdffonts pdfinfo pdftotext git make; do
    command -v "$tool" > /dev/null || { echo "missing: $tool"; exit 1; }
    "$tool" --version > /dev/null 2>&1 || "$tool" -v > /dev/null 2>&1 \
      || { echo "cannot execute: $tool"; exit 1; }
    echo "executes: $tool"
  done
  python3 -c "import PIL, yaml, pypdf; print(\"PIL\", PIL.__version__, \"pypdf\", pypdf.__version__)"
  fc-list : family > /tmp/fonts.txt
  grep -qi "Libertine" /tmp/fonts.txt && echo "Libertine faces present"
  test "$PRESS_TOOLCHAIN" = "1" && echo "PRESS_TOOLCHAIN promise set"
'

docker run --rm "$image" bash -euo pipefail -c '
  cd /tmp
  python3 - <<PY
import zipfile
with zipfile.ZipFile("broken.epub", "w") as z:
    z.writestr("mimetype", "application/epub+zip")
    z.writestr("META-INF/container.xml", "<container/>")
PY
  if epubcheck broken.epub > out.txt 2>&1; then
    echo "epubcheck approved a broken epub" && exit 1
  fi
  grep -qi "error" out.txt && echo "epubcheck executes and rejects"
'

docker run --rm -v "$press_dir":/press "$image" bash -euo pipefail -c '
  python3 -m pip install --break-system-packages -q /press
  cd /tmp && press new smoke-proof --author "Smoke Proof"
  cd smoke-proof
  press pdf && press verify
  press epub && press verify-formats
'

echo "toolchain smoke passed for $image"
