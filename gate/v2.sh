#!/usr/bin/env bash
# The v2 gate (meta REDESIGN-PLAN.md, from P1): build each site with --templates v2, build it
# again and compare (same input, same bytes), and check links, page weight (150 KB gzipped
# before photos and audio), the sitemap and the file count. With SPECIMEN_DIR set, the font
# specimen of each site is screenshotted there (needs google-chrome).
#
#   gate/v2.sh [site ...]
#
# Each site is built from the branch named in gate/v2/sites.txt (master: every site is on v2
# since 2026-11-19, and v2 is terradoc's only template set since 0.23.0).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
manifest="$here/v2/sites.txt"
python="${PYTHON:-python3.12}"
work="$(mktemp -d "${TMPDIR:-/tmp}/v2-gate.XXXXXX")"
trap 'rm -rf "$work"' EXIT

sites=("$@")
[ ${#sites[@]} -gt 0 ] || mapfile -t sites < <(grep -v '^#' "$manifest" | awk 'NF { print $1 }')
[ ${#sites[@]} -gt 0 ] || { echo "no sites to check ($manifest)" >&2; exit 2; }

"$python" -m venv "$work/venv"
"$work/venv/bin/pip" install -q --no-cache-dir -c "$root/gate/constraints.txt" "$root"
td="$work/venv/bin/terradoc"

status=0
for site in "${sites[@]}"; do
  ref="$(awk -v s="$site" '$1 == s { print $2 }' "$manifest")"
  if [ -z "$ref" ]; then echo "::error::$site: not in gate/v2/sites.txt"; status=1; continue; fi
  src="$work/$site"
  if ! git clone -q --depth 1 --branch "$ref" "https://github.com/plataformasindigenas/$site.git" "$src"; then
    echo "::error::$site: cannot fetch branch $ref"; status=1; continue
  fi
  build() {  # build <out>
    ( cd "$src" && "$td" build --config terradoc.yaml --templates v2 --out "$1" \
        --bundle-dir "$work/bundle-$site" --format github ) > "$1.log" 2>&1
  }
  if ! build "$work/out-$site"; then
    tail -n 30 "$work/out-$site.log"; echo "::error::$site@$ref: v2 build failed"; status=1; continue
  fi
  grep -E '^::(error|warning)' "$work/out-$site.log" || true
  echo "== $site@$ref ($(git -C "$src" rev-parse --short HEAD))"
  "$work/venv/bin/python" -m terradoc.sitecheck "$work/out-$site" || status=1
  if build "$work/again-$site" && diff -rq -x .release.json "$work/out-$site" "$work/again-$site" > "$work/$site.diff"; then
    echo "$site: a second build is byte-identical"
  else
    echo "::error::$site: a second build differs (sitepull would see every file as new)"
    head -n 20 "$work/$site.diff"; status=1
  fi
  if [ -n "${SPECIMEN_DIR:-}" ]; then
    mkdir -p "$SPECIMEN_DIR"
    for w in 390 1280; do
      google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
        --user-data-dir="$work/chrome" --window-size="$w,2000" \
        --screenshot="$SPECIMEN_DIR/$site-specimen-$w.png" "file://$work/out-$site/specimen.html" \
        > /dev/null 2>&1 || echo "::warning::$site: specimen screenshot failed"
    done
  fi
done
exit $status
