#!/usr/bin/env bash
# The press release script the docs promise: pins, proves, tags,
# proves the tag's contract, floats the major, publishes the Release.
#
# Publication is a sequence of remote mutations, so the script is a
# resumable state machine: every step checks the remote state first
# and skips work already correctly done, a preflight refuses
# conflicting state before the first mutation, and the floating major
# does not move until the immutable tag's release contract is green.
# Rerunning after any failure is the recovery procedure.
#
# Usage: scripts/release.sh vN.x.y
#        scripts/release.sh --check-tag vN.x.y   (validate only, no network)
set -euo pipefail

valid_tag() {
  [[ "$1" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
}

if [ "${1:-}" = "--check-tag" ]; then
  candidate="${2:?usage: release.sh --check-tag vN.x.y}"
  if valid_tag "$candidate"; then
    echo "valid: $candidate"
    exit 0
  fi
  echo "invalid: $candidate (exactly vN.x.y, nonnegative integers, no suffixes)"
  exit 1
fi

tag="${1:?usage: scripts/release.sh vN.x.y}"
valid_tag "$tag" || {
  echo "tag must be exactly vN.x.y (nonnegative integers, no suffixes): $tag"
  exit 1
}
version="${tag#v}"
major="${tag%%.*}"

step() { printf '\n== %s\n' "$1"; }

# ---- Preflight: every refusal happens before the first mutation ----
step "preflight"
test -z "$(git status --porcelain)" || { echo "working tree not clean"; exit 1; }
grep -q "^## \[$version\]" CHANGELOG.md || {
  echo "CHANGELOG.md has no [$version] section; roll [Unreleased] first"; exit 1; }

remote_tag_sha=$(git ls-remote origin "refs/tags/$tag" | cut -f1)
release_commit=""
if [ -n "$remote_tag_sha" ]; then
  echo "immutable tag $tag already exists at ${remote_tag_sha:0:9}; resuming from it"
  release_commit="$remote_tag_sha"
  pinned=$(git show "$remote_tag_sha:.github/workflows/build.yml" | grep -o "clintecker/press@$tag" || true)
  [ -n "$pinned" ] || {
    echo "existing tag $tag does not pin itself in build.yml; it is not a release"
    echo "commit of this script's making. Refusing to touch it."
    exit 1
  }
fi

release_exists() { gh release view "$tag" > /dev/null 2>&1; }

# ---- Step 1: the release commit on main ----
step "release commit"
if [ -n "$release_commit" ]; then
  echo "already published as the tag; skipping"
else
  current_version=$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)
  if [ "$current_version" = "$version" ] && grep -q "clintecker/press@$tag" .github/workflows/build.yml; then
    echo "HEAD is already the release commit for $tag; skipping the edit"
  else
    # The integration gate must be green on the commit being released.
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
    python3 - "$tag" "$version" <<'PY'
import re, sys
from pathlib import Path
tag, version = sys.argv[1], sys.argv[2]
b = Path(".github/workflows/build.yml")
b.write_text(re.sub(r"uses: clintecker/press@v[0-9.]+", f"uses: clintecker/press@{tag}", b.read_text()))
p = Path("pyproject.toml")
# Anchored to the line start and limited to one hit: an unanchored
# pattern once rewrote [tool.mypy]'s python_version to the release
# number, and mypy silently fell back to the running interpreter.
p.write_text(re.sub(r'^version = "[0-9.]+"', f'version = "{version}"', p.read_text(), count=1, flags=re.M))
PY
    PYTHONPATH=src python3 -m press selftest > /dev/null
    git add -A
    git commit -m "Release $tag"
  fi
  git push origin main
  release_commit=$(git rev-parse HEAD)
fi

# ---- Step 2: the immutable tag ----
step "immutable tag"
if [ -n "$remote_tag_sha" ]; then
  echo "$tag already at ${remote_tag_sha:0:9}; nothing to do"
else
  git tag -f "$tag" "$release_commit"
  git push origin "$tag"
  echo "pushed $tag at ${release_commit:0:9}"
fi

# ---- Step 3: the tag's own contract must prove before anything floats ----
step "release contract on $tag"
for attempt in $(seq 1 50); do
  verdict=$(gh api "repos/clintecker/press/commits/${release_commit}/check-runs" \
    --jq '[.check_runs[] | select(.name=="contract")] | first | .conclusion // "pending"')
  case "$verdict" in
    success) echo "contract green"; break ;;
    failure|cancelled|timed_out)
      echo "release contract is '$verdict' on $tag."
      echo "published so far: main commit, immutable tag. The major has NOT moved"
      echo "and no Release exists. Fix the contract (a new patch tag), then rerun."
      exit 1 ;;
    *) echo "waiting on the release contract ($verdict, attempt $attempt)"; sleep 30 ;;
  esac
done
[ "$verdict" = "success" ] || { echo "contract never concluded on $tag"; exit 1; }

# ---- Step 4: float the major (only now) ----
step "floating major $major"
current_major=$(git ls-remote origin "refs/tags/$major" | cut -f1)
if [ "$current_major" = "$release_commit" ]; then
  echo "$major already points at $tag; nothing to do"
else
  git tag -f "$major" "$release_commit"
  git push -f origin "$major"
  echo "moved $major to $tag"
fi

# ---- Step 5: the GitHub Release ----
step "github release"
if release_exists; then
  echo "Release $tag already exists; nothing to do"
else
  # A tag is what machines consume; the Release is what people read.
  awk -v ver="$version" '
    $0 ~ "^## \\[" ver "\\]" {p=1; next}
    p && /^## \[/ {exit}
    p {print}
  ' CHANGELOG.md > /tmp/press-release-notes.md
  gh release create "$tag" \
    --title "press $tag" \
    --notes-file /tmp/press-release-notes.md
fi

echo
echo "released $tag: commit ${release_commit:0:9}, immutable tag, contract green, $major floated, Release published"
