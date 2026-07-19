#!/usr/bin/env bash
# The press release script the docs promise: pins, proves, tags, floats.
# Usage: scripts/release.sh vN.x.y
set -euo pipefail
tag="${1:?usage: scripts/release.sh vN.x.y}"
version="${tag#v}"
major="${tag%%.*}"
case "$tag" in v[0-9]*.[0-9]*.[0-9]*) ;; *) echo "tag must be vN.x.y"; exit 1;; esac

test -z "$(git status --porcelain)" || { echo "working tree not clean"; exit 1; }

# The integration gate must be green on HEAD before anything moves.
sha=$(git rev-parse HEAD)
for attempt in $(seq 1 40); do
  conclusion=$(gh api "repos/clintecker/press/commits/${sha}/check-runs" \
    --jq '[.check_runs[] | select(.name=="consumer")] | first | .conclusion // "pending"')
  case "$conclusion" in
    success) break ;;
    failure|cancelled|timed_out)
      echo "integration gate is '$conclusion' on HEAD; fix it first"; exit 1 ;;
    *) echo "waiting on the integration gate ($conclusion, attempt $attempt)"; sleep 30 ;;
  esac
done
[ "$conclusion" = "success" ] || { echo "gate never concluded on HEAD"; exit 1; }

# Pin the action ref to the tag being cut; the image sha stays as the
# last smoked build unless updated deliberately.
python3 - "$tag" "$version" <<'PY'
import re, sys
from pathlib import Path
tag, version = sys.argv[1], sys.argv[2]
b = Path(".github/workflows/build.yml")
b.write_text(re.sub(r"uses: clintecker/press@v[0-9.]+", f"uses: clintecker/press@{tag}", b.read_text()))
p = Path("pyproject.toml")
p.write_text(re.sub(r'version = "[0-9.]+"', f'version = "{version}"', p.read_text()))
PY

# The changelog must have a section for this version.
grep -q "^## \[$version\]" CHANGELOG.md || {
  echo "CHANGELOG.md has no [$version] section; roll [Unreleased] first"; exit 1; }

PYTHONPATH=src python3 -m press selftest > /dev/null

git add -A
git commit -m "Release $tag"
git push origin main
git tag "$tag"
git tag -f "$major"
git push origin "$tag"
git push -f origin "$major"
# A tag is what machines consume; the Release is what people read.
awk -v ver="$version" '
  $0 ~ "^## \\[" ver "\\]" {p=1; next}
  p && /^## \[/ {exit}
  p {print}
' CHANGELOG.md > /tmp/press-release-notes.md
gh release create "$tag" \
  --title "press $tag" \
  --notes-file /tmp/press-release-notes.md
echo "released $tag; the release-contract workflow now proves it"
