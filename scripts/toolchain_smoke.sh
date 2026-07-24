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

# The plate upscaler for `press art enhance`. It is amd64-only (no durable
# upstream arm64 Linux build), so presence is asserted where present and its
# absence accepted on arm64, where the command degrades to a plain resample.
# Where present, the binary is EXECUTED, not merely stat-ed: it upscales a
# tiny PNG with remacri-4x through the exact argv art_enhance.upscale() builds.
# The binfmt scar says existence is not executability, and here that is the
# whole point -- a present binary with no working software-Vulkan device or a
# broken shared-lib/model load would let find_upscaler() return non-None, so
# enhance() takes the check=True upscale path and CRASHES an author's build
# instead of degrading to resample. Running it makes that failure surface at
# smoke time, not at first container use.
docker run --rm "$image" bash -euo pipefail -c '
  bin=/usr/local/bin/realesrgan-ncnn-vulkan
  models=/usr/local/share/realesrgan/models
  if [ -x "$bin" ]; then
    for m in remacri-4x ultrasharp-4x; do
      test -f "$models/$m.param" && test -f "$models/$m.bin" \
        || { echo "upscaler present but model $m missing"; exit 1; }
    done
    cd /tmp
    python3 - <<PY
from PIL import Image
Image.new("RGB", (8, 8), (90, 90, 90)).save("upin.png")
PY
    # Exactly the argv art_enhance.upscale() runs (-i/-o/-n/-m/-s), remacri-4x.
    "$bin" -i upin.png -o upout.png -n remacri-4x -m "$models" -s 4
    test -s upout.png \
      || { echo "upscaler ran but produced no output"; exit 1; }
    echo "realesrgan-ncnn-vulkan upscales with remacri (software Vulkan)"
  else
    echo "realesrgan-ncnn-vulkan absent (arm64 degrades to resample) -- ok"
  fi
'

docker run --rm -v "$press_dir":/press "$image" bash -euo pipefail -c '
  python3 -m pip install --break-system-packages -q /press
  cd /tmp && press new smoke-proof --author "Smoke Proof"
  cd smoke-proof
  press pdf && press verify
  press epub && press verify-formats
'

echo "toolchain smoke passed for $image"
