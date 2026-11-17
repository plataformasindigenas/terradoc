#!/usr/bin/env bash
# The v1 gate: v1 templates are frozen while v2 is built (meta REDESIGN-PLAN.md, P0).
#
#   gate/v1.sh check  [site ...]   build each site with this checkout and fail on any difference
#   gate/v1.sh freeze [site ...]   rewrite gate/v1/<site>.sha256 (only for a deliberate v1 fix,
#                                  in the same commit as the fix)
#
# Each site is built at the commit fixed in gate/v1/sites.txt, with --templates v1, Python 3.12
# and the dependencies in gate/constraints.txt, so the only thing that varies is terradoc itself.
# Every output file is hashed (except .release.json, which carries the version and commit).
set -euo pipefail

mode="${1:-}"; shift || true
case "$mode" in check|freeze) ;; *) echo "usage: $0 check|freeze [site ...]" >&2; exit 2 ;; esac

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
python="${PYTHON:-python3.12}"
work="$(mktemp -d "${TMPDIR:-/tmp}/v1-gate.XXXXXX")"
trap 'rm -rf "$work"' EXIT

sites=("$@")
[ ${#sites[@]} -gt 0 ] || mapfile -t sites < <(cut -d' ' -f1 "$here/v1/sites.txt")

"$python" -m venv "$work/venv"
"$work/venv/bin/pip" install -q --no-cache-dir -c "$here/constraints.txt" "$root"

status=0
for site in "${sites[@]}"; do
  commit="$(awk -v s="$site" '$1 == s { print $2 }' "$here/v1/sites.txt")"
  [ -n "$commit" ] || { echo "$site: not in gate/v1/sites.txt" >&2; exit 2; }
  src="$work/$site"
  git init -q "$src"
  git -C "$src" fetch -q --depth 1 "https://github.com/plataformasindigenas/$site.git" "$commit"
  git -C "$src" -c advice.detachedHead=false checkout -q FETCH_HEAD
  ( cd "$src" && "$work/venv/bin/terradoc" build --config terradoc.yaml --templates v1 \
      --out "$work/out-$site" --bundle-dir "$work/bundle-$site" > "$work/$site.log" 2>&1 ) \
    || { tail -n 30 "$work/$site.log"; echo "$site: build failed" >&2; status=1; continue; }
  ( cd "$work/out-$site" && find . -type f ! -path ./.release.json -print0 | LC_ALL=C sort -z \
      | xargs -0 sha256sum ) > "$work/$site.sha256"

  if [ "$mode" = freeze ]; then
    cp "$work/$site.sha256" "$here/v1/$site.sha256"
    echo "$site@${commit:0:7}: froze $(wc -l < "$work/$site.sha256") files"
  elif diff -u "$here/v1/$site.sha256" "$work/$site.sha256" > "$work/$site.diff"; then
    echo "$site@${commit:0:7}: v1 output identical ($(wc -l < "$work/$site.sha256") files)"
  else
    n=$(grep -c '^[+-][0-9a-f]' "$work/$site.diff" || true)
    echo "::error::$site: v1 output changed ($n manifest lines). v1 is frozen: if this is a deliberate"\
         "v1 fix, run 'gate/v1.sh freeze $site' and commit the manifest with the fix."
    grep '^[+-][0-9a-f]' "$work/$site.diff" | awk '{ print substr($1,1,1), $2 }' | head -n 60
    status=1
  fi
done
exit $status
